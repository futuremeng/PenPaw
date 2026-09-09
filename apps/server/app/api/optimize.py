"""慢路径优化接口（PRD §4.2 慢系统：Stage 3，进程内异步 + SSE 进度）。

降级闭环（PRD §4.2 异常处理）：
- Stage 3 超时（> stage3_timeout_s）/ 异常 → 返回 Stage 2 结果，status=degraded；
- 区域数超限 → pipeline 内部直接降级（R2 分档）。
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from penpaw_pipeline import PipelineRunner
from penpaw_pipeline.schemas import Stage2Output
from penpaw_pipeline.svg import count_control_points

from app.config import Settings
from app.dependencies import get_runner, get_settings, get_store, get_tasks
from app.schemas import TaskInfo
from app.services.storage import AssetExpired, AssetNotFound, AssetStore
from app.services.task_registry import TaskRegistry

router = APIRouter(prefix="/api/v1")


def _run_stage3(runner: PipelineRunner, store: AssetStore, asset_id: str) -> dict:
    """Stage 3 执行体（在后台线程运行）。返回 task_registry 结果 dict。"""
    asset = store.get(asset_id)
    if not asset.preview_svg:
        return {"status": "failed", "error": "no_preview"}

    stage2 = Stage2Output(
        svg=asset.preview_svg,
        control_points=count_control_points(asset.preview_svg),
        confidence=asset.extra.get("confidence", 0.9),
        intermediate=asset.extra.get("intermediate", {}),
    )
    result = runner.slow_path(stage2, (asset.width, asset.height))
    store.save_optimized(asset_id, result.svg)
    if result.degraded:
        return {
            "status": "degraded",
            "error": result.degrade_reason,
            "control_points": result.control_points,
        }
    return {"status": "succeeded", "control_points": result.control_points}


def _run_stage3_with_timeout(runner, store, asset_id, timeout_s, cb) -> dict:
    """带硬超时的 Stage 3：超时降级返回 Stage 2 结果（PRD §4.2）。

    M1 mock 耗时远小于超时阈值；M3 接入真实 DiffVG 后此超时为关键保护。
    """
    box: dict = {}

    def _worker():
        box["result"] = _run_stage3(runner, store, asset_id)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    deadline = time.time() + timeout_s
    while thread.is_alive():
        if time.time() > deadline:
            return {"status": "degraded", "error": "stage3_timeout"}
        time.sleep(0.05)
    thread.join()
    return box.get("result", {"status": "failed", "error": "stage3_no_result"})


@router.post("/assets/{asset_id}/optimize", response_model=TaskInfo)
def optimize(
    asset_id: str,
    store: AssetStore = Depends(get_store),
    runner: PipelineRunner = Depends(get_runner),
    registry: TaskRegistry = Depends(get_tasks),
    settings: Settings = Depends(get_settings),
) -> TaskInfo:
    try:
        asset = store.get(asset_id)
    except AssetNotFound:
        raise HTTPException(404, "资产不存在") from None
    except AssetExpired:
        raise HTTPException(410, "资产已过期（24h TTL），请重新上传") from None
    if not asset.preview_svg:
        raise HTTPException(409, "请先生成预览再执行精细优化")

    task = registry.create(asset_id)
    registry.run_async(
        task.task_id,
        lambda cb: _run_stage3_with_timeout(
            runner, store, asset_id, settings.stage3_timeout_s, cb
        ),
    )
    return _to_info(task)


def _to_info(task) -> TaskInfo:
    return TaskInfo(
        task_id=task.task_id,
        asset_id=task.asset_id,
        status=task.status,
        progress=task.progress,
        error=task.error,
        control_points=task.control_points,
    )


@router.get("/tasks/{task_id}", response_model=TaskInfo)
def get_task(task_id: str, registry: TaskRegistry = Depends(get_tasks)) -> TaskInfo:
    task = registry.get(task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    return _to_info(task)


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, registry: TaskRegistry = Depends(get_tasks)) -> StreamingResponse:
    """SSE 进度流：每 0.2s 推送一次状态，终态后关闭。"""
    if registry.get(task_id) is None:
        raise HTTPException(404, "任务不存在")

    async def _stream():
        while True:
            task = registry.get(task_id)
            if task is None:
                break
            payload = json.dumps(_to_info(task).model_dump())
            yield f"data: {payload}\n\n"
            if task.is_terminal:
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
