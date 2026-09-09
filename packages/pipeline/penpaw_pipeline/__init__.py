"""PenPaw three-stage neural-symbolic pipeline.

M1 阶段为 mock 实现；M2a 提供真实规则式流水线（经典分割 + 方向场 + 贝塞尔生成，
PENPAW_PIPELINE_BACKEND=real 启用）；M2b/M3 逐步替换为 Flow-Matching / DiffVG。
所有实现必须保持设备无关（device 通过 PipelineConfig 注入，PRD 附录 E.1 约束）。
"""

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.imageio import load_image
from penpaw_pipeline.param_map import MappedParams, map_sliders
from penpaw_pipeline.runner import PipelineRunner
from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage2Output, Stage3Output

__all__ = [
    "MappedParams",
    "PipelineConfig",
    "PipelineRunner",
    "RoiRegion",
    "SliderParams",
    "Stage2Output",
    "Stage3Output",
    "load_image",
    "map_sliders",
]

__version__ = "0.2.0"
