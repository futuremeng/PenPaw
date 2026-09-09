"""DINOv2 语义特征（M2，懒加载）。

用于区域特征聚类 + 置信度复合分（TDD §4.1）。
权重/依赖就位时启用，否则 is_available() 返回 False（real_pipeline 跳过该信号）。

许可证：DINOv2 主代码 Apache-2.0；主预训练权重 CC-BY-4.0（允许商用，需署名，
见 THIRD_PARTY.md）。严禁引用 Cell-DINO / XRay-DINO 子模块（非商用许可）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
# 显式禁用非商用子模块（PRD R3 / TDD §8）
_FORBIDDEN_HUB_REPOS = ("facebookresearch/dinov2:cell_dino", "facebookresearch/dinov2:xray_dino")


class DINOv2Features:
    """DINOv2 ViT-B/14 patch 特征提取。"""

    name = "dinov2-vit-b14"

    def __init__(self, device: str = "cpu", models_dir: str | Path | None = None) -> None:
        self.device = device
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        self._model = None

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._model is None:
            import torch
            import torch.hub

            # 仅加载主仓库主权重；显式拦截非商用子模块
            for forbidden in _FORBIDDEN_HUB_REPOS:
                if forbidden in str(self.models_dir):
                    raise RuntimeError(f"禁止使用非商用 DINOv2 子模块: {forbidden}")
            self._model = torch.hub.load(
                "facebookresearch/dinov2", "dinov2_vits14", pretrained=True
            ).to(self.device).eval()
        return self._model

    def extract(self, image: np.ndarray) -> np.ndarray:
        """提取 patch 特征。image: HxWx3 RGB uint8 → (n_patches, dim)。"""
        if not self.is_available():
            raise RuntimeError("DINOv2 不可用（依赖缺失），应跳过该信号")
        import torch
        import torch.nn.functional as F

        img = torch.from_numpy(image).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
        img = F.interpolate(img, size=(224, 224), mode="bilinear")
        with torch.no_grad():
            feats = self._load()(img)
        return feats.squeeze(0).cpu().numpy()
