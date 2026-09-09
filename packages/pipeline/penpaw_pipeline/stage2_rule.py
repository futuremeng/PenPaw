"""Stage 2 生成（M2a 规则式）。

Mask 轮廓提取 → Douglas-Peucker 简化 → 贝塞尔拟合 → SVG 命令序列（附录 B 规范）。
M2b 替换为 Flow-Matching 潜空间采样 + 离散化解码，接口不变。
"""

from __future__ import annotations

import cv2
import numpy as np

from penpaw_pipeline.bezier import bezier_path
from penpaw_pipeline.param_map import MappedParams
from penpaw_pipeline.schemas import SliderParams, Stage2Output
from penpaw_pipeline.segmentation import SegmentedRegion
from penpaw_pipeline.svg import build_svg, count_control_points


def extract_points(mask: np.ndarray, params: MappedParams) -> np.ndarray:
    """从区域 Mask 提取轮廓点列（DP 简化，受 n_max 上限约束）。"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros((0, 2), dtype=np.float32)
    c = max(contours, key=cv2.contourArea)
    if len(c) < 3:
        return np.zeros((0, 2), dtype=np.float32)
    epsilon = params.contour_epsilon * cv2.arcLength(c, True)
    pts = cv2.approxPolyDP(c, epsilon, True).reshape(-1, 2).astype(np.float32)
    # n_max 上限：超出则加大容差重简化
    while len(pts) * 3 > params.n_max and len(pts) > 4:
        epsilon *= 1.5
        pts = cv2.approxPolyDP(c, epsilon, True).reshape(-1, 2).astype(np.float32)
    return pts


def build_rule_stage2(
    regions: list[SegmentedRegion],
    params: MappedParams,
    width: int,
    height: int,
    model_version: str,
    sliders: SliderParams,
    confidence: float,
) -> Stage2Output:
    """由分割区域列表生成 Stage 2 输出（SVG + intermediate）。"""
    groups: list[tuple[str, str, str, str]] = []
    region_data: list[dict] = []
    for region in regions:
        pts = extract_points(region.mask, params)
        if len(pts) < 3:
            continue
        d = bezier_path(pts, params.bezier_tension)
        if not d:
            continue
        groups.append((region.label, region.label, region.fill, d))
        region_data.append({"label": region.label, "fill": region.fill, "points": pts.tolist()})

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
        confidence=confidence,
        intermediate={
            "schema_version": 1,
            "backend": "rule",
            "regions": region_data,
            "sliders": {"smoothness": sliders.smoothness, "detail": sliders.detail},
        },
    )
