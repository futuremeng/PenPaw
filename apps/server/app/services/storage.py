"""资产存储（M1：本地盘；接口对齐 S3，M4 切换实现）。

每个资产一个目录：var/assets/{asset_id}/
  meta.json      # 元数据（尺寸/创建时间/TTL/状态）
  image.{ext}    # 原图（或降采样后）
  preview.svg    # 最新 Stage 2 结果
  optimized.svg  # Stage 3 结果（可选）
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


class AssetNotFound(Exception):
    pass


class AssetExpired(Exception):
    pass


@dataclass
class Asset:
    asset_id: str
    width: int
    height: int
    downsampled: bool
    created_at: float
    ttl_seconds: float
    image_path: Path
    preview_svg: str | None = None
    optimized_svg: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class AssetStore:
    def __init__(self, root: Path, ttl_hours: int = 24) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def _dir(self, asset_id: str) -> Path:
        return self.root / asset_id

    def _meta_path(self, asset_id: str) -> Path:
        return self._dir(asset_id) / "meta.json"

    def create(
        self, image_bytes: bytes, ext: str, width: int, height: int, downsampled: bool
    ) -> Asset:
        asset_id = uuid.uuid4().hex
        d = self._dir(asset_id)
        d.mkdir(parents=True)
        (d / f"image.{ext}").write_bytes(image_bytes)
        asset = Asset(
            asset_id=asset_id,
            width=width,
            height=height,
            downsampled=downsampled,
            created_at=time.time(),
            ttl_seconds=self.ttl_seconds,
            image_path=d / f"image.{ext}",
        )
        self._save_meta(asset)
        return asset

    def get(self, asset_id: str) -> Asset:
        meta_path = self._meta_path(asset_id)
        if not meta_path.exists():
            raise AssetNotFound(asset_id)
        meta = json.loads(meta_path.read_text())
        asset = Asset(
            asset_id=asset_id,
            width=meta["width"],
            height=meta["height"],
            downsampled=meta["downsampled"],
            created_at=meta["created_at"],
            ttl_seconds=meta["ttl_seconds"],
            image_path=self._dir(asset_id) / meta["image_file"],
            preview_svg=self._read_svg(self._dir(asset_id) / "preview.svg"),
            optimized_svg=self._read_svg(self._dir(asset_id) / "optimized.svg"),
            extra=meta.get("extra", {}),
        )
        if asset.is_expired():
            self.delete(asset_id)
            raise AssetExpired(asset_id)
        return asset

    def save_preview(self, asset_id: str, svg: str) -> None:
        (self._dir(asset_id) / "preview.svg").write_text(svg)

    def update_extra(self, asset_id: str, extra: dict) -> None:
        """合并更新 meta.extra（如 Stage 2 intermediate / confidence）。"""
        meta_path = self._meta_path(asset_id)
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text())
        meta.setdefault("extra", {}).update(extra)
        meta_path.write_text(json.dumps(meta))

    def save_optimized(self, asset_id: str, svg: str) -> None:
        (self._dir(asset_id) / "optimized.svg").write_text(svg)

    def delete(self, asset_id: str) -> None:
        shutil.rmtree(self._dir(asset_id), ignore_errors=True)

    def cleanup_expired(self) -> int:
        """清理过期资产（PRD §6.2：24h 自动销毁）。返回清理数量。"""
        removed = 0
        for d in self.root.iterdir():
            if not d.is_dir():
                continue
            meta_path = d / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
                if time.time() > meta["created_at"] + meta["ttl_seconds"]:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
            except (json.JSONDecodeError, KeyError):
                continue
        return removed

    @staticmethod
    def _save_meta(asset: Asset) -> None:
        meta = {
            "width": asset.width,
            "height": asset.height,
            "downsampled": asset.downsampled,
            "created_at": asset.created_at,
            "ttl_seconds": asset.ttl_seconds,
            "image_file": asset.image_path.name,
            "extra": asset.extra,
        }
        asset.image_path.parent.joinpath("meta.json").write_text(json.dumps(meta))

    @staticmethod
    def _read_svg(path: Path) -> str | None:
        return path.read_text() if path.exists() else None
