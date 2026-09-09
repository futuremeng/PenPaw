"""param_map 单调性测试（TDD §5）。"""

from __future__ import annotations

from penpaw_pipeline.param_map import map_sliders


def test_smoothness_monotonic():
    low = map_sliders(0, 50)
    mid = map_sliders(50, 50)
    high = map_sliders(100, 50)
    assert low.flow_sigma_px < mid.flow_sigma_px < high.flow_sigma_px
    assert low.lambda_c < mid.lambda_c < high.lambda_c
    assert low.contour_epsilon < mid.contour_epsilon < high.contour_epsilon
    assert low.bezier_tension < mid.bezier_tension < high.bezier_tension


def test_detail_monotonic():
    low = map_sliders(50, 0)
    mid = map_sliders(50, 50)
    high = map_sliders(50, 100)
    assert low.n_max < mid.n_max < high.n_max
    assert low.lambda_p > mid.lambda_p > high.lambda_p


def test_prd_appendix_a_formulas():
    """对齐 PRD 附录 A 公式（TDD §5）。"""
    p = map_sliders(50, 50)
    assert p.flow_sigma_px == 1.0 + 0.5 * 5.0
    assert p.n_max == 200 + int(0.5 * 800)
    assert abs(p.lambda_c - 0.01 * (1.0) ** 2) < 1e-9
    assert abs(p.lambda_p - (0.005 * 0.5 + 0.001)) < 1e-9


def test_clamp_out_of_range():
    below = map_sliders(-20, -20)
    above = map_sliders(120, 120)
    zero = map_sliders(0, 0)
    full = map_sliders(100, 100)
    assert below == zero
    assert above == full
