# Third-Party Dependencies & Licenses

本项目以 Apache-2.0 发布。依据 Apache-2.0 §4，此处列出第三方组件及其许可证。
模型权重不存入本仓库，通过下载脚本按需获取，下载脚本须逐条标注许可证（PRD §6.2）。

## AI 模型（M2/M3 引入，许可证已核实 2026-09-09）

| 组件 | 用途 | 许可证 | 来源 |
|------|------|--------|------|
| SAM (segment-anything) | Stage 1 语义分割 | Apache-2.0（代码与权重） | https://github.com/facebookresearch/segment-anything |
| DINOv2 | Stage 1 语义特征 | 代码 Apache-2.0；主预训练权重 CC-BY-4.0（允许商用，需署名 Meta AI） | https://github.com/facebookresearch/dinov2 |
| DiffVG | Stage 3 可微分光栅化 | MIT | https://github.com/nv-tlabs/diffvg |
| VTracer | 评估 baseline 矢量化 | MIT | https://github.com/visioncortex/vtracer |

> ⚠️ DINOv2 仓库内的 Cell-DINO / XRay-DINO 生物医学子模块为 CC-BY-NC / FAIR 非商用许可，
> 本项目**禁止引用**（PRD R3）。

## Python 依赖（apps/server, packages/*）

| 组件 | 许可证 |
|------|--------|
| FastAPI / Starlette / Pydantic | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| Pillow | MIT (Pillow Copyright Notice) |
| python-multipart | MIT |
| pytest | MIT |
| httpx | BSD-3-Clause |

## 前端依赖（apps/web）

| 组件 | 许可证 |
|------|--------|
| React / React DOM | MIT |
| Konva / react-konva | MIT |
| Zustand | MIT |
| Vite | MIT |
| Tailwind CSS | MIT |
| TypeScript | Apache-2.0 |

## 署名声明（CC-BY-4.0 义务）

本项目的 DINOv2 预训练权重由 Meta AI 发布，依据 CC-BY-4.0 在此署名：
"DINOv2 pretrained weights © Meta AI, used under CC-BY-4.0."
