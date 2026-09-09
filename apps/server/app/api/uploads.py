"""上传接口（PRD §4.1 输入图像规范）。"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from PIL import Image

from app.config import Settings
from app.dependencies import get_safety, get_settings, get_store
from app.schemas import AssetInfo
from app.services.content_safety import ContentSafetyChecker
from app.services.storage import AssetStore

router = APIRouter(prefix="/api/v1")

ALLOWED_EXT = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


def _validate_and_load(data: bytes, filename: str) -> tuple[Image.Image, str]:
    ext = "." + (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, "不支持的格式，仅支持 JPG/PNG/WebP（PRD §4.1）")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
        raise HTTPException(400, "图像解析失败，请检查文件是否损坏") from None
    return image, ALLOWED_EXT[ext]


@router.post("/uploads", response_model=AssetInfo)
async def upload(
    file: UploadFile,
    store: AssetStore = Depends(get_store),
    safety: ContentSafetyChecker = Depends(get_safety),
    settings: Settings = Depends(get_settings),
) -> AssetInfo:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "文件超过 10MB 限制（PRD §4.1）")

    image, fmt = _validate_and_load(data, file.filename or "upload")
    width, height = image.size
    downsampled = False

    # 长边 > 4096 → 降采样至 2048（PRD §4.1 超限处理）
    long_edge = max(width, height)
    if long_edge > settings.max_long_edge:
        scale = settings.downscale_long_edge / long_edge
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS
        )
        width, height = image.size
        downsampled = True

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format=fmt.upper())
    asset = store.create(buf.getvalue(), fmt, width, height, downsampled)

    # 输入侧内容安全（M1 mock，PRD §6.2）
    result = safety.check_image(asset.image_path)
    if not result.passed:
        store.delete(asset.asset_id)
        raise HTTPException(400, f"图像未通过内容安全审核：{result.reason}")

    return AssetInfo(
        asset_id=asset.asset_id,
        width=asset.width,
        height=asset.height,
        downsampled=downsampled,
        expires_at=str(asset.expires_at),
    )
