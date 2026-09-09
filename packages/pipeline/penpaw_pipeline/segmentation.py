"""语义分割（M2a 经典规则式；SAM 权重就位后切换，见 sam_segmenter.py）。

ClassicalSegmenter 策略：
- ROI 模式：每个 ROI 内 Canny 边缘 → 闭合轮廓 → 填充为区域；
  ROI 内无边缘时整块 ROI 作为一个区域；
- 全图模式（PRD §4.1 默认行为）：全图边缘 → 外部轮廓 → 填充，
  按面积取前 max_regions 个；无边缘时整图作为一个区域。
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from penpaw_pipeline.schemas import RoiRegion

MIN_REGION_AREA = 200  # 小于该面积（像素）的连通域忽略
MAX_ROI_REGIONS = 3  # 单个 ROI 内最多拆分的区域数


@dataclass
class SegmentedRegion:
    """分割出的一个语义区域（全图坐标系）。"""

    label: str
    bbox: tuple[int, int, int, int]  # x, y, w, h
    mask: np.ndarray  # HxW uint8（全图坐标系，255 为区域内）
    fill: str  # 区域主色（hex）


def _dominant_color(image: np.ndarray, mask: np.ndarray) -> str:
    pixels = image[mask > 0]
    if len(pixels) == 0:
        return "#808080"
    mean = pixels.mean(axis=0)
    r, g, b = (int(v) for v in mean)
    return f"#{r:02X}{g:02X}{b:02X}"


def _edge_mask(gray: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(gray, 50, 150)
    return cv2.dilate(edges, np.ones((3, 3), np.uint8))


def _fill_contour(mask: np.ndarray, contour: np.ndarray) -> None:
    cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)


def segment_classical(
    image: np.ndarray,
    roi_hints: list[RoiRegion] | None = None,
    max_regions: int = 15,
) -> list[SegmentedRegion]:
    """经典分割入口。image: HxWx3 RGB uint8。"""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    if roi_hints:
        regions = _segment_rois(image, gray, roi_hints)
    else:
        regions = _segment_full(image, gray, max_regions)

    if not regions:
        m = np.ones((h, w), dtype=np.uint8) * 255
        regions = [
            SegmentedRegion(
                label="region-0", bbox=(0, 0, w, h), mask=m, fill=_dominant_color(image, m)
            )
        ]
    return regions


def _segment_full(
    image: np.ndarray, gray: np.ndarray, max_regions: int
) -> list[SegmentedRegion]:
    h, w = image.shape[:2]
    edges = _edge_mask(gray)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= MIN_REGION_AREA]
    contours.sort(key=cv2.contourArea, reverse=True)

    regions: list[SegmentedRegion] = []
    for i, c in enumerate(contours[:max_regions]):
        m = np.zeros((h, w), dtype=np.uint8)
        _fill_contour(m, c)
        x, y, ww, hh = cv2.boundingRect(c)
        fill = _dominant_color(image, m)
        regions.append(
            SegmentedRegion(label=f"region-{i}", bbox=(x, y, ww, hh), mask=m, fill=fill)
        )
    return regions


def _segment_rois(
    image: np.ndarray, gray: np.ndarray, roi_hints: list[RoiRegion]
) -> list[SegmentedRegion]:
    h, w = image.shape[:2]
    regions: list[SegmentedRegion] = []
    for i, roi in enumerate(roi_hints):
        x0, y0 = max(0, int(roi.x)), max(0, int(roi.y))
        x1, y1 = min(w, int(roi.x + roi.width)), min(h, int(roi.y + roi.height))
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        sub = gray[y0:y1, x0:x1]
        edges = _edge_mask(sub)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) >= MIN_REGION_AREA]
        contours.sort(key=cv2.contourArea, reverse=True)

        base_label = roi.label or f"roi-{i}"
        if not contours:
            # ROI 内无边缘：整块 ROI 作为一个区域
            m = np.zeros((h, w), dtype=np.uint8)
            m[y0:y1, x0:x1] = 255
            regions.append(
                SegmentedRegion(
                    label=base_label,
                    bbox=(x0, y0, x1 - x0, y1 - y0),
                    mask=m,
                    fill=_dominant_color(image[y0:y1, x0:x1], m[y0:y1, x0:x1]),
                )
            )
            continue

        for j, c in enumerate(contours[:MAX_ROI_REGIONS]):
            c_full = c + np.array([x0, y0], dtype=np.int32)
            m = np.zeros((h, w), dtype=np.uint8)
            _fill_contour(m, c_full)
            x, y, ww, hh = cv2.boundingRect(c_full)
            label = base_label if j == 0 else f"{base_label}-{j}"
            fill = _dominant_color(image, m)
            regions.append(
                SegmentedRegion(label=label, bbox=(x, y, ww, hh), mask=m, fill=fill)
            )
    return regions
