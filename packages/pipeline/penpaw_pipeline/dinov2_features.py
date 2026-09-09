"""DINOv2 语义特征（M2，懒加载）。

用于区域特征一致性 + 置信度复合分（TDD §4.1）。
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
    """DINOv2 ViT-S/14 patch 特征提取（本地权重优先）。"""

    name = "dinov2-vits14"

    def __init__(self, device: str = "cpu", models_dir: str | Path | None = None) -> None:
        self.device = device
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        self._model = None

    @property
    def checkpoint_path(self) -> Path:
        return self.models_dir / "dinov2_vits14_pretrain.pth"

    def is_available(self) -> bool:
        """依赖 + 本地权重均就位才可用（避免运行时联网下载）。"""
        if not self.checkpoint_path.exists():
            return False
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
            # hub 代码（pretrained=False，不下载权重）+ 本地权重
            model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", pretrained=False)
            state = torch.load(self.checkpoint_path, map_location="cpu")
            model.load_state_dict(state)
            self._model = model.to(self.device).eval()
        return self._model

    def extract(self, image: np.ndarray) -> np.ndarray:
        """提取 patch 特征。image: HxWx3 RGB uint8 → (n_patches, dim)。"""
        if not self.is_available():
            raise RuntimeError("DINOv2 不可用（依赖或权重缺失），应跳过该信号")
        import torch
        import torch.nn.functional as F

        img = torch.from_numpy(image).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
        img = F.interpolate(img, size=(224, 224), mode="bilinear")
        img = img.to(self.device)  # 输入与模型同设备（MPS/CUDA）
        with torch.no_grad():
            # get_intermediate_layers 返回 (n_layers,) 元组，每个 (batch, n_patches, dim)
            feats = self._load().get_intermediate_layers(img, n=1, return_class_token=False)
        return feats[0].squeeze(0).cpu().numpy()  # (n_patches, dim)


def region_consistency(
    feats: np.ndarray,
    regions: list,
    image_h: int,
    image_w: int,
) -> float:
    """区域语义一致性（0~1）：区域内 patch 特征越均匀，一致性越高。

    feats: (n_patches, dim)，按 16x16 网格排列（224/14）。
    将每个 patch 中心映射回原图坐标，采样落在区域 mask 内的 patch，
    计算各区域内部特征方差，取倒数归一化为一致性分。
    """
    if feats is None or len(feats) == 0 or not regions:
        return 1.0
    grid = int(round(np.sqrt(feats.shape[0])))
    if grid * grid != feats.shape[0]:
        return 1.0
    # patch 中心在原图坐标
    ys = (np.arange(grid) + 0.5) / grid * image_h
    xs = (np.arange(grid) + 0.5) / grid * image_w
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    yy = yy.astype(np.int32).clip(0, image_h - 1).ravel()
    xx = xx.astype(np.int32).clip(0, image_w - 1).ravel()

    variances: list[float] = []
    for r in regions:
        mask = r.mask
        inside = (mask[yy, xx] > 0)
        if inside.sum() < 2:
            continue
        f = feats[inside]
        # L2 归一化（尺度无关）：语义一致的区域 patch 特征方向相近
        norms = np.linalg.norm(f, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        f = f / norms
        f = f - f.mean(axis=0, keepdims=True)
        variances.append(float((f**2).mean()))
    if not variances:
        return 1.0
    mean_var = float(np.mean(variances))
    # 归一化：方差越小一致性越高（L2 归一化后方差量级 ~1e-3，M3 前定稿）
    return round(float(1.0 / (1.0 + mean_var * 10.0)), 3)
