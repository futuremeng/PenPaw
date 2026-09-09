"""方向场估计器（M2a 规则式）。

Sobel 梯度方向 + 方向感知平滑（圆形均值，避免 ±π 角度回绕）。
M2b 替换为学习型 FPN-CNN（sin/cos 回归），接口不变。
"""

from __future__ import annotations

import cv2
import numpy as np


def estimate_flow_field(
    image: np.ndarray,
    mask: np.ndarray | None = None,
    sigma_px: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """估计逐像素方向场。

    Args:
        image: HxWx3 RGB uint8（或 HxW 灰度）
        mask: HxW uint8（非零为有效区域），None 表示全图
        sigma_px: 平滑强度（由平滑度滑块映射，越大越平滑）

    Returns:
        (angles, valid)：
        - angles: HxW float32，方向角（弧度，atan2(gy, gx)）
        - valid:  HxW bool，高梯度（边缘）区域
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx * gx + gy * gy)
    angles = np.arctan2(gy, gx)

    if magnitude.max() > 0:
        threshold = float(magnitude.mean() + magnitude.std())
    else:
        threshold = 0.0
    valid = magnitude > threshold
    if mask is not None:
        valid = valid & (mask > 0)

    iters = max(1, int(round(sigma_px)))
    for _ in range(iters):
        angles = _direction_aware_smooth(angles, magnitude)

    return angles.astype(np.float32), valid


def _direction_aware_smooth(angles: np.ndarray, magnitude: np.ndarray) -> np.ndarray:
    """方向感知平滑：sin/cos 分解后高斯模糊再合成（圆形均值）。

    高梯度像素保留原方向，低梯度像素采用邻域平滑方向。
    """
    sin_s = cv2.GaussianBlur(np.sin(angles), (3, 3), 0)
    cos_s = cv2.GaussianBlur(np.cos(angles), (3, 3), 0)
    smoothed = np.arctan2(sin_s, cos_s)
    w = np.clip(magnitude / (magnitude.max() + 1e-6), 0.0, 1.0)
    return (1.0 - w) * smoothed + w * angles
