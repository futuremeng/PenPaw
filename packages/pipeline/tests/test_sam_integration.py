"""M2 真实模型集成测试：SAM 分割 + DINOv2 特征 + 全链路。

需权重就位（scripts/download_models.py）；缺省时自动 skip。
标记 slow（SAM ViT-B 推理较慢），用 `pytest -m "not slow"` 跳过。

设备：resolve_device() 自动选择 cuda > mps > cpu（本机 MPS 已修补 float64）。
"""

from __future__ import annotations

import numpy as np
import pytest
from penpaw_pipeline.config import PipelineConfig, resolve_device
from penpaw_pipeline.dinov2_features import DINOv2Features, region_consistency
from penpaw_pipeline.runner import PipelineRunner
from penpaw_pipeline.sam_segmenter import SAMSegmenter
from penpaw_pipeline.schemas import RoiRegion, SliderParams
from penpaw_pipeline.segmentation import segment_classical

_DEVICE = resolve_device()
_requires_sam = pytest.mark.skipif(
    not SAMSegmenter(device=_DEVICE).is_available(), reason="SAM 权重/依赖未就位"
)
_requires_dino = pytest.mark.skipif(
    not DINOv2Features(device=_DEVICE).is_available(), reason="DINOv2 权重/依赖未就位"
)


def _small_circle() -> np.ndarray:
    """256x256 白底蓝圆（小图加速 SAM 推理）。"""
    import cv2

    img = np.full((256, 256, 3), (250, 250, 250), dtype=np.uint8)
    cv2.circle(img, (128, 128), 70, (40, 90, 220), thickness=-1)
    return img


@pytest.fixture(scope="module")
def sam_seg() -> SAMSegmenter:
    return SAMSegmenter(device=_DEVICE)


@pytest.fixture(scope="module")
def dino() -> DINOv2Features:
    return DINOv2Features(device=_DEVICE)


@pytest.mark.slow
@_requires_sam
def test_sam_full_image_segmentation(sam_seg):
    regions = sam_seg.segment(_small_circle())
    assert len(regions) >= 1
    for r in regions:
        assert r.mask.shape == (256, 256)
        assert 0.0 <= r.score <= 1.0
        assert r.fill.startswith("#")
        assert r.bbox[2] > 0 and r.bbox[3] > 0


@pytest.mark.slow
@_requires_sam
def test_sam_roi_segmentation_preserves_label(sam_seg):
    # float 坐标（匹配 server JSON 来源，验证 int 切片）
    roi = RoiRegion(x=58.0, y=58.0, width=140.0, height=140.0, label="subject")
    regions = sam_seg.segment_rois(_small_circle(), [roi])
    assert len(regions) >= 1
    assert any("subject" in r.label for r in regions)
    # ROI 裁剪：mask 不应超出 ROI 范围
    for r in regions:
        ys, xs = np.where(r.mask > 0)
        assert xs.min() >= roi.x and xs.max() <= roi.x + roi.width


@pytest.mark.slow
@_requires_sam
def test_real_pipeline_with_sam():
    runner = PipelineRunner(
        PipelineConfig(
            backend="real", model_version="sam-test-0.1", use_sam=True, use_dinov2=False
        )
    )
    out = runner.fast_path(_small_circle(), (256, 256), [], SliderParams(60, 40))
    assert out.svg.startswith("<!--")
    assert out.control_points > 0
    assert 0.0 < out.confidence <= 0.99
    assert len(out.intermediate["regions"]) >= 1


@pytest.mark.slow
@_requires_dino
def test_dinov2_feature_extraction(dino):
    feats = dino.extract(_small_circle())
    assert feats.ndim == 2
    assert feats.shape[0] == 256  # 16x16 patches（224/14）
    assert feats.shape[1] > 0


@pytest.mark.slow
@_requires_dino
def test_region_consistency_in_range(dino):
    img = _small_circle()
    feats = dino.extract(img)
    regions = segment_classical(img)
    c = region_consistency(feats, regions, 256, 256)
    assert 0.0 <= c <= 1.0


def test_fallback_to_classical_when_sam_disabled():
    """use_sam=False 时走经典分割（快速、确定性，无需权重）。"""
    runner = PipelineRunner(
        PipelineConfig(
            backend="real", model_version="fb-test-0.1", use_sam=False, use_dinov2=False
        )
    )
    out = runner.fast_path(_small_circle(), (256, 256), [], SliderParams(50, 50))
    assert out.control_points > 0
    assert 0.0 < out.confidence <= 0.99
