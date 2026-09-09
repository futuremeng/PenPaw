"""真实流水线（M2a）：经典分割 + 方向场 + 规则式生成。

- Stage 1：segmentation（SAM 权重就位时切换，见 sam_segmenter）+ 方向场 + 置信度
- Stage 2：规则式贝塞尔生成（M2b 替换为 Flow-Matching）
- Stage 3：规则式优化（M3 替换为 DiffVG）

设备无关约束（PRD 附录 E.1）：M2a 全部为 CPU 计算（cv2/numpy），
SAM/DINOv2 懒加载模块按 config.device 选择 CUDA/MPS/CPU。
"""

from __future__ import annotations

import numpy as np

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.flow_field import estimate_flow_field
from penpaw_pipeline.param_map import map_sliders
from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage1Output, Stage2Output
from penpaw_pipeline.segmentation import SegmentedRegion, segment_classical
from penpaw_pipeline.stage2_rule import build_rule_stage2


def _confidence(n_regions: int, edge_coverage: float) -> float:
    """置信度（PRD §5.2 分层）：区域数惩罚 × 边缘覆盖度加成。

    M3 前定稿为 SAM mask score + DINOv2 一致性 + 方向场一致性的复合分。
    """
    base = max(0.3, 0.95 - 0.05 * max(0, n_regions - 5))
    return round(min(0.99, base * (0.5 + 0.5 * min(1.0, edge_coverage * 5))), 3)


class RealStage1:
    name = "stage1-perception-real"

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(
        self,
        image: np.ndarray,
        image_size: tuple[int, int],
        roi_regions: list[RoiRegion],
        sliders: SliderParams,
    ) -> Stage1Output:
        params = map_sliders(sliders.smoothness, sliders.detail)
        regions = segment_classical(image, roi_regions or None)

        # 方向场（全局）：M2a 用于置信度；M2b 起作为 Stage 2 条件输入
        _, valid = estimate_flow_field(image, sigma_px=params.flow_sigma_px)
        edge_coverage = float(valid.mean()) if valid.size else 0.0

        return Stage1Output(
            regions=[
                RoiRegion(
                    x=r.bbox[0], y=r.bbox[1], width=r.bbox[2], height=r.bbox[3], label=r.label
                )
                for r in regions
            ],
            semantic_features={"backend": "classical", "n_regions": len(regions)},
            tangent_flow={"backend": "rule", "edge_coverage": round(edge_coverage, 4)},
            confidence=_confidence(len(regions), edge_coverage),
            seg_regions=regions,  # type: ignore[arg-type]
        )


class RealStage2:
    name = "stage2-generation-rule"

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(
        self,
        image: np.ndarray,
        image_size: tuple[int, int],
        stage1: Stage1Output,
        sliders: SliderParams,
        model_version: str,
    ) -> Stage2Output:
        params = map_sliders(sliders.smoothness, sliders.detail)
        height, width = image.shape[:2]
        regions: list[SegmentedRegion] = stage1.seg_regions or []
        return build_rule_stage2(
            regions, params, width, height, model_version, sliders, stage1.confidence
        )
