"""Stage 1 感知（mock）。

M2 替换为：SAM（Mask）+ DINOv2（语义特征）+ 方向场估计器（切线流）。
mock 行为：
- 无 ROI 时按 PRD §4.1 默认行为生成全图 3 个语义区域；
- 过滤过小区域（包围盒 < 32x32，PRD §4.1 异常处理）；
- 区域数越多置信度越低（模拟 PRD §5.2 置信度分层）。
"""

from __future__ import annotations

from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage1Output

MIN_BBOX = 32  # PRD §4.1：包围盒 < 32x32 视为区域过小


class MockStage1:
    name = "stage1-perception-mock"

    def run(
        self,
        image,  # noqa: ARG002 - mock 忽略图像数据（real 后端使用）
        image_size: tuple[int, int],
        roi_regions: list[RoiRegion],
        sliders: SliderParams,
    ) -> Stage1Output:
        width, height = image_size
        regions = list(roi_regions) if roi_regions else self._default_regions(width, height)
        regions = [r for r in regions if r.width >= MIN_BBOX and r.height >= MIN_BBOX]
        if not regions:
            regions = self._default_regions(width, height)
        # 简单置信度模型：区域数 <= 5 高置信，否则递减
        confidence = max(0.3, 0.95 - 0.05 * max(0, len(regions) - 5))
        return Stage1Output(
            regions=regions,
            semantic_features={"mock": True, "n_regions": len(regions)},
            tangent_flow={"mock": True, "resolution": [width, height]},
            confidence=confidence,
        )

    @staticmethod
    def _default_regions(width: int, height: int) -> list[RoiRegion]:
        """全图默认分割：左/右上/右下 三个语义区域。"""
        specs = [
            (0.05, 0.05, 0.40, 0.90, "left"),
            (0.50, 0.05, 0.45, 0.42, "top-right"),
            (0.50, 0.53, 0.45, 0.42, "bottom-right"),
        ]
        return [
            RoiRegion(x * width, y * height, w * width, h * height, label=label)
            for x, y, w, h, label in specs
        ]