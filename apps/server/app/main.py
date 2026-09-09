"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from penpaw_pipeline import PipelineConfig, PipelineRunner

from app.api import export, health, optimize, preview, uploads
from app.config import Settings, get_settings
from app.services.content_safety import MockContentSafetyChecker
from app.services.storage import AssetStore
from app.services.task_registry import TaskRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时清理一次过期资产（PRD §6.2：24h TTL）
    app.state.store.cleanup_expired()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="PenPaw Neural Vector Engine", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = AssetStore(settings.storage_dir, settings.asset_ttl_hours)
    app.state.runner = PipelineRunner(
        PipelineConfig(
            backend=settings.pipeline_backend,
            device=settings.pipeline_device,
            use_sam=settings.use_sam,
            use_dinov2=settings.use_dinov2,
            model_version=settings.model_version,
            stage3_timeout_s=settings.stage3_timeout_s,
        )
    )
    app.state.safety = MockContentSafetyChecker()
    app.state.tasks = TaskRegistry()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(preview.router)
    app.include_router(optimize.router)
    app.include_router(export.router)
    return app


app = create_app()
