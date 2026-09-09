"""流水线编排：快路径（Stage 1+2）与慢路径（Stage 3）。

后端切换（PipelineConfig.backend）：
- "mock"（默认）：M1 确定性 mock，无需图像数据；
- "real"（M2a）：经典分割 + 方向场 + 规则式生成，需要真实图像（numpy RGB）。
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage2Output, Stage3Output
from penpaw_pipeline.stage1_perception import MockStage1
from penpaw_pipeline.stage2_generation import MockStage2
from penpaw_pipeline.stage3_optimize import MockStage3

ProgressCb = Callable[[float], None]


class PipelineRunner:
    """三阶流水线入口。

    设备无关：所有模型通过 config.device 选择运行设备（PRD 附录 E.1），
    云端 worker 与桌面 sidecar 复用本类。
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        if self.config.backend == "real":
            from penpaw_pipeline.real_pipeline import RealStage1, RealStage2
            from penpaw_pipeline.stage3_rule import RuleStage3

            self.stage1 = RealStage1(self.config)
            self.stage2 = RealStage2(self.config)
            self.stage3 = RuleStage3()
        else:
            self.stage1 = MockStage1()
            self.stage2 = MockStage2()
            self.stage3 = MockStage3()

    def fast_path(
        self,
        image: np.ndarray | None,
        image_size: tuple[int, int],
        roi_regions: list[RoiRegion],
        sliders: SliderParams,
    ) -> Stage2Output:
        """交互态：Stage 1 + Stage 2（PRD §4.2 快系统，目标 P99 < 1s @ T4）。

        image：real 后端必填（HxWx3 RGB uint8）；mock 后端忽略。
        """
        stage1 = self.stage1.run(image, image_size, roi_regions, sliders)
        return self.stage2.run(image, image_size, stage1, sliders, self.config.model_version)

    def slow_path(
        self,
        stage2: Stage2Output,
        image_size: tuple[int, int],
        progress_cb: ProgressCb | None = None,
    ) -> Stage3Output:
        """导出态：Stage 3（PRD §4.2 慢系统，P95 < 3s / P99 < 5s / 硬超时 10s）。

        超时/OOM 由调用方（server 层）捕获并降级返回 Stage 2 结果。
        """
        return self.stage3.run(stage2, image_size, self.config, progress_cb)

