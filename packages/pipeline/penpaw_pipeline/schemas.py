"""流水线数据契约（各 Stage 输入输出）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoiRegion:
    """用户框选的语义区域（图像像素坐标）。"""

    x: float
    y: float
    width: float
    height: float
    label: str = "region"


@dataclass(frozen=True)
class SliderParams:
    """意图滑块（PRD §4.1 / 附录 A）。"""

    smoothness: int = 50  # 线条平滑度 0~100
    detail: int = 50  # 细节保留度 0~100


@dataclass
class Stage1Output:
    regions: list[RoiRegion] = field(default_factory=list)
    # 语义特征（mock：占位 dict；M2：DINOv2 patch 特征）
    semantic_features: dict = field(default_factory=dict)
    # 切线流（mock：占位 dict；M2：方向场估计器输出）
    tangent_flow: dict = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class Stage2Output:
    svg: str
    control_points: int
    confidence: float
    # 供 Stage 3 复用的中间表示（mock：区域 + 参数；M2：潜空间采样结果）
    intermediate: dict = field(default_factory=dict)


@dataclass
class Stage3Output:
    svg: str
    control_points: int
    degraded: bool = False
    degrade_reason: str | None = None
