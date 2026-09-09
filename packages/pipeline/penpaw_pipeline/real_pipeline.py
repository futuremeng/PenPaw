"""真实流水线（M2a 规则式 + M2 SAM/DINOv2）。

- Stage 1：分割（SAM 权重就位时启用，否则经典 Canny/轮廓）+ 方向场 + 置信度
- Stage 2：规则式贝塞尔生成（M2b 替换为 Flow-Matching）
- Stage 3：规则式优化（M3 替换为 DiffVG）

设备无关约束（PRD 附录 E.1）：经典分割/方向场为 CPU 计算（cv2/numpy），
SAM/DINOv2 懒加载模块按 config.resolved_device() 选择 CUDA/MPS/CPU。
"""

from __future__ import annotations

import numpy as np

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.dinov2_features import DINOv2Features, region_consistency
from penpaw_pipeline.flow_field import estimate_flow_field
from penpaw_pipeline.param_map import map_sliders
from penpaw_pipeline.sam_segmenter import SAMSegmenter
from penpaw_pipeline.schemas import RoiRegion, SliderParams, Stage1Output, Stage2Output
from penpaw_pipeline.segmentation import SegmentedRegion, segment_classical
from penpaw_pipeline.stage2_rule import build_rule_stage2


def _confidence(
    n_regions: int,
    edge_coverage: float,
    sam_score: float | None = None,
    dinov2_consistency: float | None = None,
) -> float:
    """置信度（PRD §5.2 分层）复合分。

    base（区域数惩罚）× 边缘覆盖 × SAM mask score × DINOv2 语义一致性。
    未启用的信号（sam_score / dinov2_consistency 为 None）不参与，保持中性。
    """
    base = max(0.3, 0.95 - 0.05 * max(0, n_regions - 5))
    factors = [base, 0.5 + 0.5 * min(1.0, edge_coverage * 5)]
    if sam_score is not None:
        factors.append(0.5 + 0.5 * min(1.0, sam_score))
    if dinov2_consistency is not None:
        factors.append(0.5 + 0.5 * min(1.0, dinov2_consistency))
    return round(min(0.99, max(0.01, float(np.prod(factors)))), 3)


class RealStage1:
    name = "stage1-perception-real"

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        device = config.resolved_device()
        self._sam = SAMSegmenter(device=device) if config.use_sam else None
        self._dinov2 = DINOv2Features(device=device) if config.use_dinov2 else None

    def run(
        self,
        image: np.ndarray,
        image_size: tuple[int, int],
        roi_regions: list[RoiRegion],
        sliders: SliderParams,
    ) -> Stage1Output:
        params = map_sliders(sliders.smoothness, sliders.detail)
        h, w = image.shape[:2]

        # 分割：SAM（可用即用）否则经典 Canny/轮廓
        sam_score: float | None = None
        seg_backend = "classical"
        regions: list[SegmentedRegion] = []
        if self._sam is not None and self._sam.is_available():
            regions = (
                self._sam.segment_rois(image, roi_regions)
                if roi_regions
                else self._sam.segment(image)
            )
            if regions:
                seg_backend = "sam"
                sam_score = float(np.mean([r.score for r in regions]))
            else:
                regions = segment_classical(image, roi_regions or None)
        if not regions:
            regions = segment_classical(image, roi_regions or None)

        # 方向场（全局）：M2a 用于置信度；M2b 起作为 Stage 2 条件输入
        _, valid = estimate_flow_field(image, sigma_px=params.flow_sigma_px)
        edge_coverage = float(valid.mean()) if valid.size else 0.0

        # DINOv2 语义一致性（可用即用；失败则跳过该信号）
        dinov2_consistency: float | None = None
        if self._dinov2 is not None and self._dinov2.is_available():
            try:
                feats = self._dinov2.extract(image)
                dinov2_consistency = region_consistency(feats, regions, h, w)
            except Exception:  # noqa: BLE001 - 特征提取失败不应阻断主流程
                dinov2_consistency = None

        confidence = _confidence(len(regions), edge_coverage, sam_score, dinov2_consistency)

        return Stage1Output(
            regions=[
                RoiRegion(
                    x=r.bbox[0], y=r.bbox[1], width=r.bbox[2], height=r.bbox[3], label=r.label
                )
                for r in regions
            ],
            semantic_features={
                "backend": seg_backend,
                "n_regions": len(regions),
                "sam_score": round(sam_score, 3) if sam_score is not None else None,
                "dinov2_consistency": dinov2_consistency,
            },
            tangent_flow={"backend": "rule", "edge_coverage": round(edge_coverage, 4)},
            confidence=confidence,
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
