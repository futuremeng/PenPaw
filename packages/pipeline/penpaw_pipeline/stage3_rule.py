"""Stage 3 优化（M2a 规则式；M3 替换为 DiffVG 可微分光栅化）。

从 Stage 2 intermediate 的轮廓点列出发，以更强简化（epsilon ×1.8）
重拟合贝塞尔 → 控制点显著减少，形成真实的"快速 vs 优化后"对比。
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from penpaw_pipeline.bezier import bezier_path, simplify_points
from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.schemas import Stage2Output, Stage3Output
from penpaw_pipeline.svg import build_svg, count_control_points

ProgressCb = Callable[[float], None]

# Stage 3 相对周长的 DP 容差：强于 Stage 2 典型值（~0.012），但低于尖角崩塌阈值（~0.025），
# 确保"终极优化"精简平滑冗余点、同时保留尖角轮廓（星形等无法无损简化的图形保持原点数）。
_STAGE3_EPSILON_RATIO = 0.02
_STEPS = 8  # 模拟优化迭代步数（进度上报用）


class RuleStage3:
    name = "stage3-optimize-rule"

    def run(
        self,
        stage2: Stage2Output,
        image_size: tuple[int, int],
        config: PipelineConfig,
        progress_cb: ProgressCb | None = None,
    ) -> Stage3Output:
        regions_data = stage2.intermediate.get("regions", [])
        if len(regions_data) > config.max_regions_for_stage3:
            return Stage3Output(
                svg=stage2.svg,
                control_points=stage2.control_points,
                degraded=True,
                degrade_reason="region_count_exceeded",
            )

        for i in range(_STEPS):
            if progress_cb:
                progress_cb((i + 1) / _STEPS)

        width, height = image_size
        groups: list[tuple[str, str, str, str]] = []
        for rd in regions_data:
            pts = np.array(rd.get("points", []), dtype=np.float32)
            if len(pts) < 3:
                continue
            # 以点列周长为基准的绝对容差，做更强简化
            perimeter = float(np.sum(np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)))
            simplified = simplify_points(pts, _STAGE3_EPSILON_RATIO * perimeter)
            if len(simplified) < 3:
                continue
            d = bezier_path(simplified, 1.0)
            if d:
                groups.append((rd["label"], rd["label"], rd["fill"], d))

        sliders = stage2.intermediate.get("sliders", {})
        svg = build_svg(
            width,
            height,
            groups,
            model_version=config.model_version,
            params={**sliders, "stage": 3},
        )
        return Stage3Output(svg=svg, control_points=count_control_points(svg))
