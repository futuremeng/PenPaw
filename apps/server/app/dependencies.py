"""FastAPI 依赖注入（从 app.state 取单例）。"""

from __future__ import annotations

from fastapi import Request
from penpaw_pipeline import PipelineRunner

from app.config import Settings
from app.services.content_safety import ContentSafetyChecker
from app.services.storage import AssetStore
from app.services.task_registry import TaskRegistry


def get_store(request: Request) -> AssetStore:
    return request.app.state.store


def get_runner(request: Request) -> PipelineRunner:
    return request.app.state.runner


def get_safety(request: Request) -> ContentSafetyChecker:
    return request.app.state.safety


def get_tasks(request: Request) -> TaskRegistry:
    return request.app.state.tasks


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
