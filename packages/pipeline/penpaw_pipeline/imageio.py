"""图像 IO：解码为 numpy RGB（流水线内部使用，server 不直接依赖 cv2）。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ImageDecodeError(Exception):
    pass


def load_image(path: str | Path) -> np.ndarray:
    """解码图像文件为 HxWx3 RGB uint8 numpy 数组。"""
    data = Path(path).read_bytes()
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageDecodeError(f"无法解码图像: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
