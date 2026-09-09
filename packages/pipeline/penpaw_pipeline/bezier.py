"""贝塞尔拟合与轮廓简化（M2a 规则式 Stage 2 / Stage 3 共用）。"""

from __future__ import annotations

import cv2
import numpy as np


def simplify_points(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Douglas-Peucker 简化（对点列操作，epsilon 为绝对距离）。"""
    if len(points) < 3:
        return points
    contour = points.astype(np.int32).reshape(-1, 1, 2)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return approx.reshape(-1, 2).astype(np.float32)


def bezier_path(points: np.ndarray, tension: float = 1.0) -> str:
    """闭合平滑路径：中点为过曲线点、顶点为控制点（经典平滑闭合曲线）。

    输出 M + n 段 Q + Z；控制点 = 顶点向相邻中点方向按 tension 收缩
    （tension=1 即顶点本身，曲线最圆滑）。
    """
    n = len(points)
    if n < 3:
        return ""
    mids = [(points[i] + points[(i + 1) % n]) / 2 for i in range(n)]
    parts = [f"M {mids[0][0]:.2f} {mids[0][1]:.2f}"]
    for i in range(1, n + 1):
        p = points[i % n]
        m_prev = mids[(i - 1) % n]
        m = mids[i % n]
        ctrl = m_prev + (p - m_prev) * tension
        parts.append(f"Q {ctrl[0]:.2f} {ctrl[1]:.2f} {m[0]:.2f} {m[1]:.2f}")
    parts.append("Z")
    return " ".join(parts)
