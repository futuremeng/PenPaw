"""Stage 2 生成（mock）。

M2 替换为：Flow-Matching 潜空间采样 + 离散化解码为 SVG 命令序列。
mock 行为：按附录 A 参数映射生成确定性 SVG（椭圆近似色块）。
"""

from __future__ import annotations

from penpaw_pipeline.schemas import SliderParams, Stage1Output, Stage2Output
from penpaw_pipeline.svg import build_svg, count_control_points, generate_region_paths


class MockStage2:
    name = "stage2-generation-mock"

    def run(
        self,
        image,  # noqa: ARG002 - mock 忽略图像数据（real 后端使用）
        image_size: tuple[int, int],
        stage1: Stage1Output,
        sliders: SliderParams,
        model_version: str,
    ) -> Stage2Output:
        width, height = image_size
        groups = generate_region_paths(stage1.regions, sliders.smoothness, sliders.detail)
        svg = build_svg(
            width,
            height,
            groups,
            model_version=model_version,
            params={"smoothness": sliders.smoothness, "detail": sliders.detail, "stage": 2},
        )
        return Stage2Output(
            svg=svg,
            control_points=count_control_points(svg),
            confidence=stage1.confidence,
            intermediate={
                "regions": [r.__dict__ for r in stage1.regions],
                "sliders": {"smoothness": sliders.smoothness, "detail": sliders.detail},
            },
        )
