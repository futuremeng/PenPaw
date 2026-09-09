"""SAM 分割器（M2，懒加载）。

权重/依赖就位时启用，否则 is_available() 返回 False，
real_pipeline 自动回退经典分割（segmentation.segment_classical）。

许可证：SAM 代码 + 权重均为 Apache-2.0（见 THIRD_PARTY.md）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from penpaw_pipeline.segmentation import SegmentedRegion, _dominant_color

# 权重目录：{models_dir}/sam_vit_b.pth
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


class SAMSegmenter:
    """SAM 语义分割（ViT-B 先行，TDD §4.1）。"""

    name = "sam-vit-b"

    def __init__(self, device: str = "cpu", models_dir: str | Path | None = None) -> None:
        self.device = device
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        self._sam = None

    @property
    def checkpoint_path(self) -> Path:
        return self.models_dir / "sam_vit_b.pth"

    def is_available(self) -> bool:
        """依赖 + 权重均就位才可用。"""
        if not self.checkpoint_path.exists():
            return False
        try:
            import segment_anything  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._sam is None:
            from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

            model_type = "vit_b"
            sam = sam_model_registry[model_type](checkpoint=str(self.checkpoint_path))
            sam.to(device=self.device)
            self._sam = SamAutomaticMaskGenerator(sam, min_mask_region_area=200)
        return self._sam

    def segment(self, image: np.ndarray) -> list[SegmentedRegion]:
        """全图自动分割。image: HxWx3 RGB uint8。"""
        if not self.is_available():
            raise RuntimeError("SAM 不可用（依赖或权重缺失），应回退经典分割")

        h, w = image.shape[:2]
        masks = self._load().generate(image)
        regions: list[SegmentedRegion] = []
        for i, m in enumerate(sorted(masks, key=lambda x: x["area"], reverse=True)[:15]):
            region_mask = m["segmentation"].astype(np.uint8) * 255
            x, y, ww, hh = m["bbox"]  # [x, y, w, h]
            regions.append(
                SegmentedRegion(
                    label=f"region-{i}",
                    bbox=(int(x), int(y), int(ww), int(hh)),
                    mask=region_mask,
                    fill=_dominant_color(image, region_mask),
                )
            )
        if not regions:
            m = np.ones((h, w), dtype=np.uint8) * 255
            regions.append(
                SegmentedRegion(
                    label="region-0", bbox=(0, 0, w, h), mask=m, fill=_dominant_color(image, m)
                )
            )
        return regions
