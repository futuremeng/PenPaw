"""PenPaw three-stage neural-symbolic pipeline.

M1 阶段为 mock 实现；M2/M3 逐步替换为 SAM + DINOv2 + 方向场估计器 /
Flow-Matching / DiffVG 真实模型。所有实现必须保持设备无关
（device 通过 PipelineConfig 注入，PRD 附录 E.1 约束）。
"""

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.runner import PipelineRunner
from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage2Output, Stage3Output

__all__ = [
    "PipelineConfig",
    "PipelineRunner",
    "RoiRegion",
    "SliderParams",
    "Stage2Output",
    "Stage3Output",
]

__version__ = "0.1.0"
