"""规则式 Stage 2 生成测试（M2a）。"""

from __future__ import annotations

import numpy as np
from penpaw_pipeline.bezier import bezier_path, simplify_points
from penpaw_pipeline.param_map import map_sliders
from penpaw_pipeline.schemas import SliderParams
from penpaw_pipeline.segmentation import segment_classical
from penpaw_pipeline.stage2_rule import build_rule_stage2, extract_points
from penpaw_pipeline.svg import count_control_points


def test_bezier_path_closed():
    pts = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
    d = bezier_path(pts, 1.0)
    assert d.startswith("M ")
    assert d.endswith("Z")
    assert "Q " in d


def test_bezier_path_too_few_points():
    assert bezier_path(np.array([[0, 0], [1, 1]], dtype=np.float32), 1.0) == ""


def test_simplify_points_reduces():
    # 生成一个带噪声的圆
    t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    pts = np.stack([100 + 50 * np.cos(t), 100 + 50 * np.sin(t)], axis=1).astype(np.float32)
    simplified = simplify_points(pts, 3.0)
    assert len(simplified) < len(pts)
    assert len(simplified) >= 3


def test_extract_points_respects_n_max(circle_image):
    regions = segment_classical(circle_image)
    # 极低 n_max 应强制更少点
    strict = map_sliders(0, 0)  # n_max=200
    loose = map_sliders(0, 100)  # n_max=1000
    r = max(regions, key=lambda r: r.bbox[2] * r.bbox[3])
    pts_strict = extract_points(r.mask, strict)
    pts_loose = extract_points(r.mask, loose)
    assert len(pts_strict) * 3 <= strict.n_max or len(pts_strict) <= 4
    assert len(pts_loose) >= len(pts_strict)


def test_build_rule_stage2_produces_valid_svg(circle_image):
    regions = segment_classical(circle_image)
    params = map_sliders(60, 40)
    sliders = SliderParams(smoothness=60, detail=40)
    out = build_rule_stage2(regions, params, 640, 480, "test-0.1", sliders, 0.9)
    assert out.svg.startswith("<!--")
    assert "<svg" in out.svg
    assert out.control_points > 0
    assert out.control_points == count_control_points(out.svg)
    # intermediate 结构
    assert out.intermediate["schema_version"] == 1
    assert out.intermediate["backend"] == "rule"
    assert len(out.intermediate["regions"]) >= 1
    assert "points" in out.intermediate["regions"][0]


def test_smoothness_reduces_points(circle_image):
    """平滑度越高 → 轮廓点越少（DP 容差越大）。"""
    regions = segment_classical(circle_image)
    r = max(regions, key=lambda r: r.bbox[2] * r.bbox[3])
    pts_low = extract_points(r.mask, map_sliders(0, 50))
    pts_high = extract_points(r.mask, map_sliders(100, 50))
    assert len(pts_high) <= len(pts_low)
