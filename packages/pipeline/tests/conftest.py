"""pipeline 测试公共 fixture：合成图像（无外部依赖，CPU 可跑）。"""

from __future__ import annotations

import cv2
import numpy as np
import pytest


@pytest.fixture()
def flat_image() -> np.ndarray:
    """纯色图（无边缘）：640x480 红色。"""
    return np.full((480, 640, 3), (200, 60, 60), dtype=np.uint8)


@pytest.fixture()
def circle_image() -> np.ndarray:
    """白底蓝色实心圆（中心 320,240，半径 120）：单一清晰边缘。"""
    img = np.full((480, 640, 3), (250, 250, 250), dtype=np.uint8)
    cv2.circle(img, (320, 240), 120, (40, 90, 220), thickness=-1)
    return img


@pytest.fixture()
def two_rect_image() -> np.ndarray:
    """灰底 + 两个彩色矩形：两个清晰区域。"""
    img = np.full((480, 640, 3), (230, 230, 230), dtype=np.uint8)
    cv2.rectangle(img, (60, 60), (260, 260), (220, 60, 60), thickness=-1)
    cv2.rectangle(img, (360, 200), (580, 420), (60, 160, 80), thickness=-1)
    return img
