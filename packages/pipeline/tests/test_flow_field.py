"""方向场估计器测试（M2a 规则式）。"""

from __future__ import annotations

import numpy as np
from penpaw_pipeline.flow_field import estimate_flow_field


def test_output_shapes(circle_image):
    angles, valid = estimate_flow_field(circle_image, sigma_px=3.0)
    h, w = circle_image.shape[:2]
    assert angles.shape == (h, w)
    assert valid.shape == (h, w)
    assert angles.dtype == np.float32
    assert valid.dtype == bool


def test_flat_image_no_valid_edges(flat_image):
    """纯色图无边缘：valid 应基本为空。"""
    _, valid = estimate_flow_field(flat_image, sigma_px=3.0)
    assert valid.sum() == 0


def test_circle_edges_detected(circle_image):
    """圆形边缘应被检出：valid 非空且集中在圆环附近。"""
    _, valid = estimate_flow_field(circle_image, sigma_px=3.0)
    assert valid.sum() > 100
    # 圆心处不应是边缘
    assert not valid[240, 320]


def test_angles_bounded(circle_image):
    angles, _ = estimate_flow_field(circle_image, sigma_px=5.0)
    assert np.all(angles >= -np.pi - 1e-3)
    assert np.all(angles <= np.pi + 1e-3)


def test_mask_restricts_valid(circle_image):
    mask = np.zeros(circle_image.shape[:2], dtype=np.uint8)
    mask[:, :100] = 255  # 仅左条带有效
    _, valid = estimate_flow_field(circle_image, mask=mask, sigma_px=3.0)
    assert valid[:, 100:].sum() == 0
