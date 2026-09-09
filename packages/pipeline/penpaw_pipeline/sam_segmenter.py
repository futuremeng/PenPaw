"""SAM 分割器（M2，懒加载）。

权重/依赖就位时启用，否则 is_available() 返回 False，
real_pipeline 自动回退经典分割（segmentation.segment_classical）。

许可证：SAM 代码 + 权重均为 Apache-2.0（见 THIRD_PARTY.md）。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from penpaw_pipeline.schemas import RoiRegion
from penpaw_pipeline.segmentation import SegmentedRegion, _bbox_of_mask, _dominant_color

# 权重目录：{models_dir}/sam_vit_b.pth
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def _patch_mps_float64(generator) -> None:
    """MPS 不支持 float64：将点坐标转换输出强制 float32。

    SAM 的 _process_batch 执行 torch.as_tensor(float64 numpy, device=mps) 会报错；
    CUDA/CPU 无此问题。点坐标用 float32 精度足够，故此修补对结果无影响。
    """
    import numpy as _np

    predictor = generator.predictor
    orig_apply = predictor.transform.apply_coords

    def apply_f32(pts, size):
        return orig_apply(pts, size).astype(_np.float32)

    predictor.transform.apply_coords = apply_f32


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
            _patch_mps_float64(self._sam)
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
                    score=float(m.get("score", 1.0)),
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

    def segment_rois(self, image: np.ndarray, roi_hints: list[RoiRegion]) -> list[SegmentedRegion]:
        """ROI 模式：对每个 ROI 用 box prompt 取 SAM mask（裁剪到 ROI 内）。"""
        if not self.is_available() or not roi_hints:
            return []
        predictor = self._load().predictor
        predictor.set_image(image)
        regions: list[SegmentedRegion] = []
        for i, roi in enumerate(roi_hints):
            # ROI 坐标可能为 float（server JSON 来源），切片需 int
            x0, y0 = int(roi.x), int(roi.y)
            x1, y1 = int(roi.x + roi.width), int(roi.y + roi.height)
            box = np.array([x0, y0, x1, y1], dtype=np.float32)
            masks, scores, _ = predictor.predict(box=box, multimask_output=False)
            mask = masks[0].astype(np.uint8) * 255
            # 裁剪到 ROI 内
            roi_mask = np.zeros_like(mask)
            roi_mask[y0:y1, x0:x1] = 255
            mask = cv2.bitwise_and(mask, roi_mask)
            if mask.sum() == 0:
                continue
            regions.append(
                SegmentedRegion(
                    label=roi.label or f"region-{i}",
                    bbox=_bbox_of_mask(mask),
                    mask=mask,
                    fill=_dominant_color(image, mask),
                    score=float(scores[0]) if len(scores) else 1.0,
                )
            )
        return regions
