"""服务配置（环境变量前缀 PENPAW_）。"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PENPAW_")

    # 资产存储（M1 本地盘；M4 切 S3/MinIO，接口不变）
    storage_dir: Path = Path("var/assets")
    # 资产 TTL（PRD §6.2：24 小时自动销毁）
    asset_ttl_hours: int = 24

    # 输入图像规范（PRD §4.1）
    max_upload_bytes: int = 10 * 1024 * 1024
    max_long_edge: int = 4096
    downscale_long_edge: int = 2048

    # Stage 3（PRD §4.2）
    stage3_timeout_s: float = 10.0

    # 流水线后端（M1 mock / M2a real，TDD §1.1）
    pipeline_backend: str = "mock"
    # M2：设备（auto 自动检测 cuda>mps>cpu）与模型开关
    pipeline_device: str = "auto"
    use_sam: bool = True
    use_dinov2: bool = True
    # 模型版本号（写入导出 SVG 头部注释，PRD 附录 B.6）
    model_version: str = "mock-0.1.0"

    # CORS（前端 dev server）
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


def get_settings() -> Settings:
    return Settings()
