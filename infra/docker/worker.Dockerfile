# PenPaw GPU worker（M3 启用：Celery + 真实模型）
# M1 阶段为占位镜像，仅验证构建链路。
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv==0.11.8

WORKDIR /repo

COPY pyproject.toml uv.lock* ./
COPY apps/server/pyproject.toml apps/server/
COPY packages/pipeline/pyproject.toml packages/pipeline/
COPY packages/eval/pyproject.toml packages/eval/
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY apps/server/ apps/server/
COPY packages/pipeline/ packages/pipeline/
COPY packages/eval/ packages/eval/
RUN uv sync --frozen --no-dev || uv sync --no-dev

# M3：换 nvidia/cuda:12.x + pip install torch --index-url https://download.pytorch.org/whl/cu124
CMD ["echo", "PenPaw GPU worker placeholder (M3)"]
