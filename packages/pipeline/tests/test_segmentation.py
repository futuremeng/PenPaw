"""经典分割测试（M2a）。"""

from __future__ import annotations

from penpaw_pipeline.schemas import RoiRegion
from penpaw_pipeline.segmentation import segment_classical


def test_flat_image_single_region(flat_image):
    regions = segment_classical(flat_image)
    assert len(regions) == 1
    r = regions[0]
    assert r.bbox == (0, 0, 640, 480)
    # 主色应接近红色
    assert r.fill.startswith("#")
    assert len(r.fill) == 7


def test_circle_image_detects_region(circle_image):
    regions = segment_classical(circle_image)
    assert len(regions) >= 1
    # 圆：中心 (320,240) 半径 120 → bbox 约 x:200-440, y:120-360
    biggest = max(regions, key=lambda r: r.bbox[2] * r.bbox[3])
    x, y, w, h = biggest.bbox
    assert 180 <= x <= 220
    assert 100 <= y <= 140
    assert 200 <= w <= 280
    assert 200 <= h <= 280


def test_two_rects_detects_regions(two_rect_image):
    regions = segment_classical(two_rect_image)
    assert len(regions) >= 2


def test_roi_mode_no_edges_whole_roi(flat_image):
    """纯色图 ROI 内无边缘：整块 ROI 作为一个区域。"""
    roi = RoiRegion(x=100, y=100, width=200, height=150, label="subject")
    regions = segment_classical(flat_image, [roi])
    assert len(regions) == 1
    assert regions[0].label == "subject"
    assert regions[0].bbox == (100, 100, 200, 150)


def test_roi_mode_clamps_to_bounds(circle_image):
    roi = RoiRegion(x=600, y=400, width=200, height=200, label="corner")
    regions = segment_classical(circle_image, [roi])
    for r in regions:
        x, y, w, h = r.bbox
        assert x + w <= 640
        assert y + h <= 480


def test_masks_are_full_image_size(circle_image):
    regions = segment_classical(circle_image)
    for r in regions:
        assert r.mask.shape == circle_image.shape[:2]
        assert r.mask.max() == 255
