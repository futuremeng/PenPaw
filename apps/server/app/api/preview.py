"""快路径预览接口（PRD §4.2 快系统：Stage 1 + 2）。

会话级并发限 1：同一资产同一时刻仅一个快路径任务，
新请求等待旧请求结束（前端另有 300ms debounce + 版本号丢弃过期响应）。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from penpaw_pipeline import PipelineRunner, RoiRegion, SliderParams, load_image

from app.dependencies import get_runner, get_store
from app.schemas import PreviewRequest, PreviewResult
from app.services.storage import AssetExpired, AssetNotFound, AssetStore

router = APIRouter(prefix="/api/v1")

# 每资产一把锁（PRD §4.2：同一会话快路径并发限 1）
_asset_locks: dict[str, asyncio.Lock] = {}


def _get_lock(asset_id: str) -> asyncio.Lock:
    if asset_id not in _asset_locks:
        _asset_locks[asset_id] = asyncio.Lock()
    return _asset_locks[asset_id]


@router.post("/assets/{asset_id}/preview", response_model=PreviewResult)
async def preview(
    asset_id: str,
    req: PreviewRequest,
    store: AssetStore = Depends(get_store),
    runner: PipelineRunner = Depends(get_runner),
) -> PreviewResult:
    try:
        asset = store.get(asset_id)
    except AssetNotFound:
        raise HTTPException(404, "资产不存在") from None
    except AssetExpired:
        raise HTTPException(410, "资产已过期（24h TTL），请重新上传") from None

    regions = [
        RoiRegion(x=r.x, y=r.y, width=r.width, height=r.height, label=r.label) for r in req.regions
    ]
    sliders = SliderParams(smoothness=req.smoothness, detail=req.detail)

    async with _get_lock(asset_id):
        # real 后端需要真实图像（numpy RGB）；mock 后端忽略
        image = load_image(asset.image_path) if runner.config.backend == "real" else None
        result = await asyncio.to_thread(
            runner.fast_path, image, (asset.width, asset.height), regions, sliders
        )

    store.save_preview(asset_id, result.svg)
    # 持久化 Stage 2 intermediate，供 Stage 3 复用（PRD 快慢系统衔接）
    store.update_extra(
        asset_id,
        {"intermediate": result.intermediate, "confidence": result.confidence},
    )
    return PreviewResult(
        svg=result.svg,
        control_points=result.control_points,
        confidence=result.confidence,
        version=req.version,
    )
