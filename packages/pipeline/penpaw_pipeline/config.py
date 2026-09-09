"""流水线配置。

设备无关约束（PRD 附录 E.1）：device 仅作为字符串注入，
真实模型实现（M2+）据此选择 CUDA / MPS / CPU，mock 实现忽略该值。
"""

from __future__ import annotations

from dataclasses import dataclass


def resolve_device(device: str = "auto") -> str:
    """设备自动检测：cuda > mps > cpu。torch 不可用时回退 cpu。"""
    if device != "auto":
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


@dataclass(frozen=True)
class PipelineConfig:
    # "auto" | "cpu" | "mps" | "cuda" —— 由部署层（云端 worker / 桌面 sidecar）决定
    device: str = "auto"
    # "mock" | "real" —— 流水线后端（PENPAW_PIPELINE_BACKEND）
    # mock：M1 确定性 mock；real：M2a 经典分割 + 方向场 + 规则式生成
    backend: str = "mock"
    # M2：权重/依赖就位时启用 SAM 分割（否则回退经典分割）
    use_sam: bool = True
    # M2：权重/依赖就位时启用 DINOv2 语义特征（否则跳过该置信度信号）
    use_dinov2: bool = True
    # 模型版本号，写入导出 SVG 头部注释（PRD 附录 B.6）
    model_version: str = "mock-0.1.0"
    # Stage 3 硬超时（PRD §4.2：> 10s 触发降级）
    stage3_timeout_s: float = 10.0
    # 区域数 > 该值直接走降级路径（PRD R2 分档策略）
    max_regions_for_stage3: int = 15

    def resolved_device(self) -> str:
        return resolve_device(self.device)
