# PenPaw API 服务（M1 无 GPU 依赖；M2+ 换 nvidia/cuda 基础镜像）
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv==0.11.8

WORKDIR /repo

# 先装依赖（利用层缓存）
COPY pyproject.toml uv.lock* ./
COPY apps/server/pyproject.toml apps/server/
COPY packages/pipeline/pyproject.toml packages/pipeline/
COPY packages/eval/pyproject.toml packages/eval/
RUN uv sync --frozen --no-dev || uv sync --no-dev

# 再拷贝源码
COPY apps/server/ apps/server/
COPY packages/pipeline/ packages/pipeline/
COPY packages/eval/ packages/eval/
RUN uv sync --frozen --no-dev || uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/server"]
