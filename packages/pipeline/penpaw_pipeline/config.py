"""流水线配置。

设备无关约束（PRD 附录 E.1）：device 仅作为字符串注入，
真实模型实现（M2+）据此选择 CUDA / MPS / CPU，mock 实现忽略该值。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    # "cpu" | "mps" | "cuda" —— 由部署层（云端 worker / 桌面 sidecar）决定
    device: str = "cpu"
    # 模型版本号，写入导出 SVG 头部注释（PRD 附录 B.6）
    model_version: str = "mock-0.1.0"
    # Stage 3 硬超时（PRD §4.2：> 10s 触发降级）
    stage3_timeout_s: float = 10.0
    # 区域数 > 该值直接走降级路径（PRD R2 分档策略）
    max_regions_for_stage3: int = 15
