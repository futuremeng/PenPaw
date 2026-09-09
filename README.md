# PenPaw 神经矢量引擎

基于"三阶神经-符号流水线"的 AI 图像 → 语义化 SVG 生成工具。

- 产品需求：[docs/PRD-v1.5.md](docs/PRD-v1.5.md)
- 许可证：Apache-2.0（见 [LICENSE](LICENSE)）；第三方依赖许可见 [THIRD_PARTY.md](THIRD_PARTY.md)

## 三阶流水线

| 阶段 | 职责 | 状态 |
|------|------|---------|
| Stage 1 感知 | SAM（Mask）+ DINOv2（语义特征）+ 方向场估计器（切线流） | M2a：经典分割 + 方向场（SAM/DINOv2 懒加载） |
| Stage 2 生成 | Flow-Matching 潜空间采样 → 离散 SVG 命令序列 | M2a：规则式贝塞尔生成（M2b 换 Flow-Matching） |
| Stage 3 优化 | DiffVG 可微分光栅化 + 梯度寻径 | M2a：规则式重拟合精简（M3 换 DiffVG） |

## 仓库结构

```
apps/
  web/                  # React 18 + Vite + TS + Konva + Zustand + Tailwind
  server/               # FastAPI 服务（上传/预览/优化/导出 + SSE 进度）
packages/
  pipeline/             # 三阶流水线（设备无关：torch.device 注入，云端/桌面 sidecar 复用）
  eval/                 # Golden Test Set 评估脚本（LPIPS/SSIM/控制点数 + VTracer baseline）
infra/
  docker/               # Dockerfile × 3 + docker-compose.yml
docs/
  PRD-v1.5.md
```

## 快速开始（M1）

### 后端

```bash
uv sync --all-packages --all-extras   # 安装 workspace 依赖 + dev extras（Python 3.12）
cd apps/server
uv run uvicorn app.main:app --reload --port 8000        # mock 后端（默认）
PENPAW_PIPELINE_BACKEND=real uv run uvicorn app.main:app --port 8000   # M2a 真实规则式后端
```

> M2a `real` 后端为 CPU 计算（经典分割 + 方向场 + 贝塞尔生成），无需 GPU/模型下载。
> 接入 SAM/DINOv2 真实模型：`uv pip install torch` +
> `uv pip install git+https://github.com/facebookresearch/segment-anything.git`，
> 再 `uv run python scripts/download_models.py` 下载权重（自动回退，缺权重不影响 real 后端）。

### 前端

```bash
pnpm install
pnpm dev:web                              # http://localhost:5173（/api 代理到 :8000）
```

### 测试

```bash
uv run pytest                             # 后端 API + pipeline 全链路（mock + real 后端）
pnpm build:web                            # 前端类型检查 + 构建
```

### Docker（单机部署）

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

## M1 里程碑状态

- [x] monorepo 脚手架（uv workspace + pnpm workspace）
- [x] 上传 → ROI → 预览 → 优化（SSE 进度）→ 导出 全链路（mock 模型）
- [x] 输入校验（格式/大小/4K 降采样）、24h TTL 资产清理、会话级并发限 1
- [x] THIRD_PARTY.md + CLA 模板
- [x] 模型许可证审计定稿（R3，结论已归档至 [docs/TECH-DESIGN.md §8](docs/TECH-DESIGN.md)）
- [ ] 内容安全 API 真实接入（当前为 mock，接口已预留，M5）

> 注：M1 的 Stage 3 优化为**进程内异步**（线程 + SSE）。Celery + Redis 跨进程队列
> 在 M3 接入真实 DiffVG 时引入（见 `apps/server/app/tasks/` 说明）。

## M2a 里程碑状态（真实规则式流水线）

- [x] `param_map.py`：滑块 → 流水线参数唯一入口（PRD 附录 A，含单调性测试）
- [x] 方向场估计器（M2a 规则式）：Sobel 梯度方向 + 方向感知平滑（圆形均值）
- [x] 经典分割：Canny 边缘 + 轮廓填充（ROI / 全图双模式，无模型依赖）
- [x] 规则式 Stage 2：轮廓 → DP 简化 → 贝塞尔拟合 → SVG（附录 B 规范）
- [x] 规则式 Stage 3：更强简化重拟合（平滑图形精简、尖角图形保留）
- [x] 后端切换：`PENPAW_PIPELINE_BACKEND=mock|real`，server 图像解码接线
- [x] SAM / DINOv2 懒加载集成 + 权重下载脚本（许可证标注，缺省自动回退经典）
- [x] 测试：pipeline 27 项 + server real 后端 2 项，全链路 39 项通过；ruff 全绿
- [ ] M2：SAM + DINOv2 真实模型接入（需 GPU 环境 + 权重下载）
- [ ] M2b：Flow-Matching 生成器（研究性，TDD §4.2）

> 设计文档：[docs/TECH-DESIGN.md](docs/TECH-DESIGN.md)（M2~M5 实施基准，含许可证审计归档）。
