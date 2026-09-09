"""Stage 3 优化（mock）。

M3 替换为：DiffVG 可微分光栅化 + 梯度下降（视觉还原 + λ_c 曲率惩罚 + λ_p 控制点惩罚）。
mock 行为：
- 模拟 1s 左右的优化耗时，通过 progress_cb 上报进度；
- 以 simplify_factor=0.6 重新生成路径（模拟控制点精简 ~30%+）；
- 区域数超过 config.max_regions_for_stage3 时直接降级（PRD R2 分档）。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.schemas import RoiRegion, Stage2Output, Stage3Output
from penpaw_pipeline.svg import build_svg, count_control_points, generate_region_paths

ProgressCb = Callable[[float], None]


class MockStage3:
    name = "stage3-optimize-mock"

    def run(
        self,
        stage2: Stage2Output,
        image_size: tuple[int, int],
        config: PipelineConfig,
        progress_cb: ProgressCb | None = None,
    ) -> Stage3Output:
        regions = [RoiRegion(**r) for r in stage2.intermediate.get("regions", [])]
        if len(regions) > config.max_regions_for_stage3:
            return Stage3Output(
                svg=stage2.svg,
                control_points=stage2.control_points,
                degraded=True,
                degrade_reason="region_count_exceeded",
            )

        steps = 10
        for i in range(steps):
            time.sleep(0.1)  # 模拟 DiffVG 迭代耗时
            if progress_cb:
                progress_cb((i + 1) / steps)

        sliders = stage2.intermediate.get("sliders", {})
        groups = generate_region_paths(
            regions,
            sliders.get("smoothness", 50),
            sliders.get("detail", 50),
            simplify_factor=0.6,
        )
        width, height = image_size
        svg = build_svg(
            width,
            height,
            groups,
            model_version=config.model_version,
            params={**sliders, "stage": 3},
        )
        return Stage3Output(svg=svg, control_points=count_control_points(svg))
