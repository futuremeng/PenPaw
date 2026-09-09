"""API 数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoiBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    label: str = "region"


class PreviewRequest(BaseModel):
    regions: list[RoiBox] = Field(default_factory=list)
    smoothness: int = Field(default=50, ge=0, le=100)
    detail: int = Field(default=50, ge=0, le=100)
    # 前端请求版本号（PRD §4.2：过期响应由前端丢弃）
    version: int = Field(default=1, ge=1)


class AssetInfo(BaseModel):
    asset_id: str
    width: int
    height: int
    downsampled: bool
    expires_at: str


class PreviewResult(BaseModel):
    svg: str
    control_points: int
    confidence: float
    version: int


class TaskInfo(BaseModel):
    task_id: str
    asset_id: str
    status: str  # queued | running | succeeded | degraded | failed
    progress: float = 0.0
    error: str | None = None
    control_points: int | None = None
