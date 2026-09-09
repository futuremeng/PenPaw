# PenPaw 神经矢量引擎

基于"三阶神经-符号流水线"的 AI 图像 → 语义化 SVG 生成工具。

- 产品需求：[docs/PRD-v1.5.md](docs/PRD-v1.5.md)
- 许可证：Apache-2.0（见 [LICENSE](LICENSE)）；第三方依赖许可见 [THIRD_PARTY.md](THIRD_PARTY.md)

## 三阶流水线

| 阶段 | 职责 | M1 状态 |
|------|------|---------|
| Stage 1 感知 | SAM（Mask）+ DINOv2（语义特征）+ 方向场估计器（切线流） | mock |
| Stage 2 生成 | Flow-Matching 潜空间采样 → 离散 SVG 命令序列 | mock |
| Stage 3 优化 | DiffVG 可微分光栅化 + 梯度寻径 | mock |

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
uv sync                                   # 安装 workspace 依赖（Python 3.12）
uv run uvicorn app.main:app --reload --port 8000   # 在 apps/server 目录下
```

### 前端

```bash
pnpm install
pnpm dev:web                              # http://localhost:5173（/api 代理到 :8000）
```

### 测试

```bash
uv run pytest                             # 后端 API 全链路测试（mock 流水线）
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
- [ ] 内容安全 API 真实接入（当前为 mock，接口已预留）
- [ ] 模型许可证审计定稿（R3，结论已核实：SAM Apache-2.0 / DINOv2 CC-BY-4.0）

> 注：M1 的 Stage 3 优化为**进程内异步**（线程 + SSE）。Celery + Redis 跨进程队列
> 在 M3 接入真实 DiffVG 时引入（见 `apps/server/app/tasks/` 说明）。
