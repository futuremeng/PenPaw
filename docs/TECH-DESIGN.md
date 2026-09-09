# PenPaw 神经矢量引擎 技术设计文档 (TDD)

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-09-09 |
| 上游文档 | [PRD v1.5](PRD-v1.5.md)（需求基准，冲突时以 PRD 为准并走修订流程） |
| 状态 | M1 已完成，本文档为 M2~M5 实施基准 |

## 1. 总体架构

### 1.1 组件与进程模型

```
                        ┌────────────────────────────────────────────┐
                        │                部署拓扑（云端）              │
                        └────────────────────────────────────────────┘

 浏览器 ──HTTP/SSE──► [api 进程 ×N 无状态] ──► [资产存储]  (M1 本地盘 / M4 S3)
                        │  快路径：进程内直调 pipeline（asyncio.to_thread）
                        │  慢路径：M1 进程内线程 / M3 Celery worker
                        ▼
                 [pipeline 包]  Stage1 → Stage2 → Stage3   ← 设备无关（device 注入）
                        ▲
  M3: [worker-gpu 进程 ×M] ──Celery+Redis──► 同上（独占 T4）

 桌面端（V2 方案 B）：Tauri 壳 + Python sidecar 进程内嵌同一份 pipeline 包，
  device 注入 mps/cuda/cpu，前端注入 LocalClient（见 PRD 附录 E）。
```

**进程职责**：

| 进程 | 职责 | 状态 | 扩缩容 |
|------|------|------|--------|
| api | 路由、校验、快路径推理调度、SSE、导出 | 无状态（任务状态 M1 在内存，M3 迁 Redis） | 水平扩 |
| worker-gpu（M3） | Stage 3 DiffVG 优化 | 无状态 | 按 GPU 数扩 |
| web（nginx） | 静态资源 + /api 反代 | 无状态 | 水平扩 |

**关键设计决策**（与 M1 实现一致）：

1. `packages/pipeline` 是唯一的模型代码位置，api 与 worker 都 import 它——保证云端/桌面/评估脚本三处行为一致；
2. 快路径 M1 走 api 进程内 `asyncio.to_thread`（mock 无 GPU 争用）；**M2 接入真实模型后，快路径推理移入 worker-gpu**（避免 api 进程持有 GPU 上下文），api 只负责调度——接口不变；
3. 慢路径 M1 进程内线程 + 内存 TaskRegistry；M3 切 Celery + Redis，TaskRegistry 读 Redis，SSE 端点不变。

### 1.2 数据流

**快路径（交互态，PRD §4.2）**：

```
前端 debounce 300ms
  → POST /assets/{id}/preview {regions, smoothness, detail, version}
  → api：资产校验（TTL）→ 会话锁（每资产 1）→ to_thread(pipeline.fast_path)
      Stage1: SAM(Mask) + DINOv2(特征) + 方向场(切线流)
      Stage2: 生成 SVG 命令序列（M2a 规则式 / M2b Flow-Matching）
  → 存 preview.svg + intermediate（meta.extra）
  → 返回 {svg, control_points, confidence, version}
前端：version 过期则丢弃响应
```

**慢路径（导出态）**：

```
前端 → POST /assets/{id}/optimize → 创建 task（queued）→ 立即返回 task_id
worker：running → pipeline.slow_path(Stage2 intermediate)
  Stage3: DiffVG 光栅化 + 梯度下降（视觉还原 + λ_c + λ_p）
  进度回调 → TaskRegistry（M1 内存 / M3 Redis）
前端：EventSource /tasks/{id}/events 每 0.2s 收状态
终态：succeeded（存 optimized.svg）/ degraded（超时 10s / OOM / 区域>15，返回 Stage 2 结果）/ failed
前端：succeeded → 自动下载 optimized.svg；degraded → 提示"已跳过终极优化"
```

**降级决策表**（PRD §4.2 / R2）：

| 触发条件 | 行为 | 任务状态 | 计入导出成功 |
|----------|------|---------|-------------|
| Stage 3 超时 > 10s | 返回 Stage 2 结果 | degraded(stage3_timeout) | 是 |
| CUDA OOM | 返回 Stage 2 结果 | degraded(stage3_oom) | 是 |
| 区域数 > 15 | 跳过 Stage 3 | degraded(region_count_exceeded) | 是 |
| 用户重试 1 次后再降级 | 置灰"精细优化"按钮 | degraded | 是 |
| Stage 1/2 异常 | 返回 500，不产生任务 | failed | 否 |

## 2. API 契约

Base URL：`/api/v1`。所有响应 JSON（UTF-8），错误体 `{"detail": "..."}`。

### 2.1 端点总览

| 方法 | 路径 | 说明 | 成功码 |
|------|------|------|--------|
| GET | `/healthz` | 健康检查 | 200 |
| POST | `/uploads` | 上传图像（multipart，字段 `file`） | 200 |
| POST | `/assets/{asset_id}/preview` | 快路径预览 | 200 |
| POST | `/assets/{asset_id}/optimize` | 触发慢路径优化 | 200 |
| GET | `/tasks/{task_id}` | 任务状态 | 200 |
| GET | `/tasks/{task_id}/events` | SSE 进度流 | 200 |
| GET | `/assets/{asset_id}/export?optimized=bool` | 导出 SVG | 200 |

### 2.2 数据模型

```jsonc
// AssetInfo
{ "asset_id": "0b3ae6c9...", "width": 800, "height": 600,
  "downsampled": false, "expires_at": "1789039712.8" }

// PreviewRequest
{ "regions": [{ "x": 100, "y": 80, "width": 400, "height": 350, "label": "subject" }],
  "smoothness": 70, "detail": 60, "version": 1 }
// regions 为空数组 = 全图语义解析（PRD §4.1 默认行为）
// smoothness/detail ∈ [0,100]，默认 50

// PreviewResult
{ "svg": "<!-- PenPaw SVG ... -->\n<svg ...>", "control_points": 37,
  "confidence": 0.95, "version": 1 }

// TaskInfo
{ "task_id": "2f2c445a...", "asset_id": "0b3ae6c9...",
  "status": "queued|running|succeeded|degraded|failed",
  "progress": 0.0-1.0, "error": null | "stage3_timeout|stage3_oom|region_count_exceeded|...",
  "control_points": 23 }
```

### 2.3 SSE 事件格式

`GET /tasks/{task_id}/events`，`Content-Type: text/event-stream`：

```
data: {"task_id":"...","asset_id":"...","status":"running","progress":0.4,"error":null,"control_points":null}

data: {"task_id":"...","asset_id":"...","status":"succeeded","progress":1.0,"error":null,"control_points":23}
（终态后流关闭）
```

- 推送间隔 0.2s；客户端断线重连后应改轮询 `GET /tasks/{id}`（M1 不维护事件回放）；
- nginx 已配置 `proxy_buffering off`（见 infra/docker/nginx.conf）。

### 2.4 错误码

| 码 | 场景 |
|----|------|
| 400 | 图像解析失败 / 内容安全拦截 |
| 404 | 资产/任务不存在 |
| 409 | 无预览结果就请求优化/导出 |
| 410 | 资产过期（24h TTL） |
| 413 | 文件 > 10MB |
| 415 | 非 JPG/PNG/WebP |
| 500 | 流水线内部异常（M2+ 需补充 503 GPU 繁忙） |

### 2.5 会话与限流

- 快路径：每 `asset_id` 一把 asyncio 锁（并发 1）；前端 300ms debounce + version 丢弃过期响应；
- 慢路径：M1 无全局队列限制；**M3 引入 Redis 队列深度 20，排队 > 60s 返回 429 + 预计等待时间**（PRD §4.2）；
- 认证：MVP 匿名（PRD §6.2），M3 起按 IP 限流（上传 10/min，预览 30/min）。

## 3. 数据模型与存储

### 3.1 资产目录结构（M1 本地盘，M4 迁 S3 保持同构）

```
{storage_dir}/{asset_id}/
├── meta.json        # {width, height, downsampled, created_at, ttl_seconds, image_file, extra}
├── image.png        # 原图或降采样后（统一转 RGB/PNG 存储）
├── preview.svg      # 最新 Stage 2 结果
├── optimized.svg    # Stage 3 结果（可选）
└── baseline/        # M4：VTracer 预计算结果 + 指标缓存
    ├── vtracer.svg
    └── metrics.json
```

- `meta.extra` 承载 Stage 2 `intermediate`（区域 + 滑块参数）与 `confidence`，供 Stage 3 复用——**M2 起 intermediate 结构变更需带 `schema_version` 字段**；
- TTL：`created_at + ttl_seconds`（默认 24h）。访问时校验（过期 → 删除 + 410）；api 启动时全量清理一次；**M4 增加后台定时清理（每 1h）+ S3 生命周期规则双保险**；
- S3 迁移（M4）：`AssetStore` 接口不变，新增 `S3AssetStore` 实现（boto3），`PENPAW_STORAGE_BACKEND=s3|local` 切换。

### 3.2 任务状态机

```
queued ──► running ──► succeeded
                  ├──► degraded   （timeout / oom / region_count_exceeded）
                  └──► failed     （未预期异常）
```

- M1：内存 `TaskRegistry`（进程重启丢失，可接受——MVP 无账号体系）；
- M3：Redis Hash（`task:{id}` → TaskInfo JSON，TTL 1h），Celery 任务结果回写。

## 4. 模型接入方案（M2 / M3）

### 4.1 Stage 1 感知（M2）

三个子模块（PRD §5.1），统一接口：

```python
class Stage1Perception:
    def __init__(self, device: str): ...          # 设备注入（附录 E.1）
    def run(self, image: np.ndarray, roi_hints: list[RoiBox]) -> Stage1Output: ...
```

| 子模块 | 模型 | 选型 | 许可证 | T4 延迟预算 |
|--------|------|------|--------|------------|
| 语义分割 | SAM | `segment-anything`，**先 ViT-B（375MB）后评估 ViT-H**；ROI 交互用 `predict`（点/框），全图模式用 `automatic_mask_generator`（`max_num_masks=15`，对齐 R2 分档） | Apache-2.0 | 150~300ms（B）/ 400~600ms（H） |
| 语义特征 | DINOv2 | `torch.hub` ViT-B/14（~340MB）；取 patch tokens 做区域内均值池化 → 色块聚类 + 置信度 | 代码 Apache-2.0 / 权重 CC-BY-4.0 | 50~100ms |
| 方向场估计器 | 分两期 | **M2a（规则式）**：Canny/Sobel 梯度方向 + 各向异性扩散平滑（无训练，立即可用）；**M2b（学习型）**：轻量 FPN-CNN 预测逐像素方向角（sin/cos 回归），训练数据见 §4.4 | 自研（Apache-2.0） | 50ms（a）/ 100ms（b） |

**置信度计算**（PRD §5.2，M3 前定稿）：
`confidence = w1·SAM_mask_score均值 + w2·DINOv2_区域特征一致性 + w3·方向场一致性`，初值 w=(0.4, 0.3, 0.3)，阈值 0.7 触发"建议人工精修"。

**R1 门禁**（方向场单独验收）：Golden Test Set 简单图形集上方向角误差 < 15° 的像素占比 > 85%；M2a 不达标则 M2b 提前启动，仍不达标则 Stage 2 退化为纯 Mask + 边缘输入（PRD R1 预案）。

### 4.2 Stage 2 生成（M2，分两期）

**M2a 规则式生成器（先落地，保证全链路真实可用）**：

```
Mask 轮廓提取（cv2.findContours）
  → 轮廓点按方向场排序/平滑（切线流引导起点与走向）
  → 滑动窗口贝塞尔拟合（3 点定 1 段二次贝塞尔，平滑度滑块控制窗口大小）
  → 细节保留度滑块控制：区域内部二次分割阈值（DINOv2 特征聚类数 = detail//25）
  → 输出 SVG 命令序列（附录 B 规范）
```

- 延迟预算 < 100ms；
- 作用：① 真实感知 + 规则生成的完整 MVP 能力；② 为 M2b 提供蒸馏教师。

**M2b Flow-Matching 生成器（PRD 核心创新，研究性里程碑）**：

- 架构：潜空间连续 flow-matching（条件 = 方向场 + Mask + DINOv2 特征 + 滑块参数），采样 4~8 步（蒸馏后），离散化解码器输出命令序列；
- 训练数据：① 合成图形（程序化生成 icon/几何体，无版权风险）；② 自绘 + 已授权素材（PRD 附录 C 同源）；③ M2a + VTracer 输出作为弱标签（仅用于预训练，最终评估不依赖）；
- 验收：同等 LPIPS 下控制点数 ≤ M2a 的 70%（对齐 PRD §7.2 对 VTracer -30% 的目标留余量）；
- **风险**：M2b 是研究性工作量（预估 4~6 人周），若 M3 前未达标，MVP 以 M2a 上线，M2b 转 V2（需 PRD 变更评审）。

### 4.3 Stage 3 优化（M3，DiffVG）

```python
# 单区域优化循环（伪代码）
rasterizer = diffvg.Rasterize(csize, device)
for region in regions:                       # R2 分档：≤5 全量 / 6~15 分批
    paths = region.paths                      # Stage 2 输出
    for it in range(max_iters):               # 初值 100，按区域复杂度自适应
        img = rasterizer(paths)
        loss = L1(img, target_roi)            # 视觉还原（主项）
             + λ_c * curvature_penalty(paths) # 平滑（附录 A）
             + λ_p * n_control_points(paths)  # 精简（附录 A）
             + λ_topo * topology_penalty      # MVP 放宽（PRD R0），监控自交叉率
        loss.backward(); optimizer.step()
    progress_cb(it / max_iters)
```

- 依赖：`diffvg`（MIT）+ PyTorch CUDA；
- 超时：worker 侧硬超时 10s（看门狗线程），OOM 捕获 `torch.cuda.OutOfMemoryError` → 降级；
- 自交叉检测：优化后贝塞尔段相交检测（< 200ms），结果写入 confidence 复合分（PRD §5.2）；
- 队列：Celery + Redis，队列深度 20，排队 > 60s 返回 429 + 预计等待时间（PRD §4.2）。

### 4.4 训练与数据（M2b / 方向场）

| 项 | 方案 |
|----|------|
| 方向场训练数据 | 合成图形（已知解析方向角）+ 人工标注 200 张（Golden Set 同源） |
| Flow-Matching 数据 | 见 §4.2；全部数据需满足 PRD 附录 C 版权规范 |
| 训练环境 | 单卡 T4/A10 即可（模型 < 100M 参数）；训练脚本入 `packages/pipeline/training/`（独立依赖组，不进运行时镜像） |
| 权重产出 | 存内部模型仓库，下载脚本逐条标注许可证（自训权重 = 本项目 Apache-2.0） |

### 4.5 T4 性能预算汇总（PRD §5.3 指标对齐）

| 路径 | 组成 | 预算 | 目标 |
|------|------|------|------|
| 快路径 P99 | SAM-B 250 + DINOv2-B 80 + 方向场 100 + Stage2 300 + 序列化/IO 100 + 调度 170 | ~1000ms | **< 1s**（紧张；预留手段：SAM 结果按 ROI 缓存、DINOv2 与 SAM 并行、方向场降分辨率） |
| Stage 3 P95 | 100 迭代 × 3 区域 | ~2.5s | **< 3s** |
| Stage 3 P99 | 复杂区域自适应迭代 | ~4.5s | **< 5s**，硬超时 10s |

## 5. 参数映射实现（PRD 附录 A 落地）

滑块值 → 流水线参数的唯一入口：`packages/pipeline/penpaw_pipeline/param_map.py`（M2 新建，mock 阶段逻辑内联在各 stage）。

```python
def map_sliders(smoothness: int, detail: int) -> MappedParams:
    return MappedParams(
        # Stage 1：方向场高斯平滑核
        flow_sigma_px: 1 + (smoothness / 100) * 5,
        # Stage 2：最大命令数上限
        n_max: 200 + (detail / 100) * 800,
        # Stage 3：曲率惩罚 / 控制点惩罚
        lambda_c: 0.01 * (smoothness / 50) ** 2,
        lambda_p: 0.005 * (1 - detail / 100) + 0.001,
    )
```

- 系数初值即 PRD 附录 A 公式；**M2 调参定稿后更新 PRD 附录 A 与本节，并同步测试用例**（PRD 附录 A 约定）；
- 单元测试：边界值（0/50/100）单调性断言（平滑度↑ → flow_sigma↑、λ_c↑；细节度↑ → n_max↑、λ_p↓）。

## 6. 评估体系（M4）

### 6.1 指标实现

| 指标 | 实现 | 依赖 |
|------|------|------|
| 控制点数 | `penpaw_pipeline.svg.count_control_points`（M1 已实现，M/L=1、Q=2、C=3 口径） | 无 |
| 文件大小 | 序列化后 UTF-8 字节数 | 无 |
| SSIM | `skimage.metrics.structural_similarity`（原图 vs 光栅化 SVG，同尺寸对齐） | scikit-image |
| LPIPS | `lpips` 库（VGG 权重，权重许可需 M4 前确认） | lpips |
| FID | `pytorch-fid`（仅离线批量：200 生成 vs 200 原图） | pytorch-fid |
| ROI 准确率 | 生成 Mask vs ground truth，IoU > 0.8 记正确（PRD §7.1） | 标注集 |
| 方向场准确率 | 方向角误差 < 15° 像素占比（PRD R1） | 标注集 |
| VTracer 对比 | `penpaw_eval.vtracer_baseline`（M4 `uv add vtracer`）；"同等还原度"口径 = LPIPS 差 < 0.02 | vtracer (MIT) |

### 6.2 Golden Test Set 流水线

```
testset-vX.Y/（独立目录，PRD 附录 C 版本管理）
  images/ + masks/ + flow_labels/ + manifest.json（版本号 + 每张图元数据）
        │
        ▼
penpaw-eval --images ... --testset testset-v1.0 --out report.json
  → 逐图：fast_path / slow_path / 指标 / VTracer 对比
  → 汇总：PRD §7 全部阈值判定（PASS/FAIL 逐项）
        │
        ▼
CI（GPU runner）：模型/流水线 PR 触发 → 核心指标退化 > 5% 阻断合并（PRD 附录 C）
```

- 报告绑定 `testset_version` + `model_version`（SVG 头部注释同源）；
- 编辑成功率（PRD §7.4 人工评测）不入 CI，按 SOP 每里程碑执行一次，记录入 `docs/eval-reports/`。

## 7. 安全与合规实现

| PRD 要求 | 实现 | 里程碑 |
|----------|------|--------|
| 内容安全（输入） | `ContentSafetyChecker` 接口（M1 mock 已就位）→ M5 接真实 API；拦截时删除资产 + 400 | M5 |
| 内容安全（输出） | 导出前异步复检栅格化预览图，命中则标记资产 + 前端提示（不阻塞首次导出） | M5 |
| 24h TTL | 访问校验 + 启动清理（M1）→ 定时清理 + S3 生命周期（M4） | M1/M4 |
| 版权告知 | 前端首次使用弹窗 + 勾选确认，确认事件上报埋点（合规留痕日志） | M5 |
| 埋点（PRD §8） | 前端 7 事件（image_uploaded / roi_completed / slider_changed / first_preview / export_requested / export_completed / degrade_occurred）→ 后端 `/api/v1/telemetry`（匿名、无 PII、可关闭） | M5 |
| 可观测性 | 结构化日志（asset_id/task_id 贯穿）；指标：快路径 P50/P99、Stage3 P95/P99、降级率（按原因）、导出成功率 → Prometheus `/metrics`（M3 起） | M3+ |

## 8. 许可证审计结论（PRD R3 归档，2026-09-09 核实）

| 组件 | 用途 | 许可证 | 结论 |
|------|------|--------|------|
| SAM（代码 + 权重） | Stage 1 分割 | Apache-2.0 | ✅ 可直接使用 |
| DINOv2 主代码 | Stage 1 特征 | Apache-2.0 | ✅ 可直接使用 |
| DINOv2 主预训练权重（ViT-S/B/L/g14） | Stage 1 特征 | **CC-BY-4.0（允许商用，需署名）** | ✅ 使用；署名已写入 THIRD_PARTY.md 与产品"关于"页 |
| DINOv2 Cell-DINO / XRay-DINO 子模块 | — | CC-BY-NC / FAIR 非商用 | ❌ **禁止引用**（代码与配置显式拦截 `cell_dino`/`xray_dino` 路径） |
| VTracer | 评估 baseline | MIT | ✅ 直接 `pip install vtracer` 集成（v1.2 曾误标 GPL-3.0，v1.3 修正） |
| DiffVG | Stage 3 | MIT | ✅ 可直接使用 |
| 自训权重（方向场 / Flow-Matching） | Stage 1/2 | 本项目 Apache-2.0 | ✅ 训练数据须满足附录 C 版权规范 |

**义务清单**：① THIRD_PARTY.md 持续维护（已建）；② CC-BY-4.0 署名（已写入）；③ 权重下载脚本逐条标注许可证（M2 落地）；④ 贡献者 CLA（模板已建，M2 起 PR 强制）；⑤ 安装包/镜像保留各组件许可文本（M4 打包时）。

## 9. 里程碑任务分解（对齐 PRD 附录 D）

| 里程碑 | 关键任务 | 出口标准（PRD 附录 D） |
|--------|---------|------------------------|
| M1 ✅ | 脚手架 / mock 全链路 / 合规基线 | 已完成（commit 6f4ca75） |
| M2 | ① SAM + DINOv2 接入（ViT-B 档）② 方向场 M2a ③ Stage 2 M2a 规则式生成器 ④ param_map ⑤ 快路径移入 worker-gpu ⑥ 权重下载脚本 + 许可证标注 ⑦ CLA 强制 | 快路径 P99 < 1s（T4）；方向场 R1 门禁报告；参数映射表定稿 |
| M2b（并行研究） | Flow-Matching 模型 + 训练数据管线 | 同等 LPIPS 下控制点 ≤ M2a 70%；不达标则按 §4.2 风险预案走 PRD 变更 |
| M3 | ① DiffVG Stage 3 ② Celery + Redis 队列（深度 20 / 429）③ 降级闭环（timeout/OOM/分档）④ 置信度复合分定稿 ⑤ 自交叉检测 ⑥ Prometheus 指标 | Stage 3 P95 < 3s；降级链路演练通过 |
| M4 | ① S3 存储 + 生命周期 ② LPIPS/SSIM/FID 落地 ③ VTracer baseline 预计算 ④ Golden Test Set v1.0 + CI 回归门禁 ⑤ 评估看板 API | 附录 C 全部落地 |
| M5 | ① 内容安全双侧接入 ② 埋点 + 版权弹窗 ③ 性能压测（并发 5~10 路）④ 人工评测（§7.4）⑤ 法务文案审核 | PRD §7 全部指标达标，可上线 |

## 10. 开放问题（需决策）

| # | 问题 | 影响 | 建议决策时点 |
|---|------|------|-------------|
| O1 | 内容安全 API 选型（国内阿里云/腾讯云 vs 海外 OpenAI Moderation） | M5 实现 | M2 期间确定部署地域后 |
| O2 | 部署地域（决定 O1 + 模型下载镜像 + 数据合规） | 全局 | **M2 启动前** |
| O3 | SAM ViT-B vs ViT-H（延迟 vs 质量） | M2 性能预算 | M2 首周 A/B 实测后 |
| O4 | M2b Flow-Matching 是否进 MVP（研究性风险） | 里程碑范围 | M2a 完成后评审 |
| O5 | LPIPS VGG 权重许可证确认 | M4 指标落地 | M4 启动前 |
