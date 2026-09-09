"""导出接口（PRD §4.2：快速导出 / 精细优化并导出）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.dependencies import get_store
from app.services.storage import AssetExpired, AssetNotFound, AssetStore

router = APIRouter(prefix="/api/v1")


@router.get("/assets/{asset_id}/export")
def export(
    store: AssetStore = Depends(get_store),
    asset_id: str = "",
    optimized: bool = False,
) -> Response:
    try:
        asset = store.get(asset_id)
    except AssetNotFound:
        raise HTTPException(404, "资产不存在") from None
    except AssetExpired:
        raise HTTPException(410, "资产已过期（24h TTL），请重新上传") from None

    if optimized:
        svg = asset.optimized_svg
        if svg is None:
            raise HTTPException(409, "尚无精细优化结果，请先执行优化")
    else:
        svg = asset.preview_svg
        if svg is None:
            raise HTTPException(409, "尚无预览结果，请先生成预览")

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="penpaw-{asset_id[:8]}.svg"'},
    )
