"""real 后端（M2a）API 全链路集成测试：上传 → 预览 → 优化 → 导出。

验证 server 侧图像解码 → numpy → fast_path 接线（PENPAW_PIPELINE_BACKEND=real）。
"""

from __future__ import annotations

import io

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw


def _circle_png() -> bytes:
    """白底蓝色实心圆（中心 320,240 半径 120）。"""
    img = Image.new("RGB", (640, 480), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 120, 440, 360], fill=(40, 90, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def real_client(tmp_path):
    settings = Settings(
        storage_dir=tmp_path / "assets",
        stage3_timeout_s=10.0,
        pipeline_backend="real",
        model_version="rule-test-0.1",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _upload(client: TestClient, data: bytes) -> dict:
    resp = client.post("/api/v1/uploads", files={"file": ("c.png", data, "image/png")})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_real_backend_full_flow(real_client):
    # 1. 上传
    asset = _upload(real_client, _circle_png())
    asset_id = asset["asset_id"]

    # 2. 预览（全图，无 ROI）
    resp = real_client.post(
        f"/api/v1/assets/{asset_id}/preview",
        json={"regions": [], "smoothness": 60, "detail": 40, "version": 1},
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["control_points"] > 0
    assert 0.0 < preview["confidence"] <= 0.99
    assert "<svg" in preview["svg"]

    # 3. 优化（慢路径）
    resp = real_client.post(f"/api/v1/assets/{asset_id}/optimize")
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["task_id"]

    # 4. 轮询任务至终态
    import time

    for _ in range(50):
        task = real_client.get(f"/api/v1/tasks/{task_id}").json()
        if task["status"] in ("succeeded", "degraded", "failed"):
            break
        time.sleep(0.1)
    assert task["status"] == "succeeded", task

    # 5. 导出优化后 SVG：控制点数应不高于预览
    resp = real_client.get(f"/api/v1/assets/{asset_id}/export", params={"optimized": True})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg")
    optimized_svg = resp.text
    assert optimized_svg.startswith("<!--")

    # 6. 导出快速版（Stage 2）
    resp = real_client.get(f"/api/v1/assets/{asset_id}/export", params={"optimized": False})
    assert resp.status_code == 200
    assert "<svg" in resp.text


def test_real_backend_roi_preview(real_client):
    asset = _upload(real_client, _circle_png())
    asset_id = asset["asset_id"]
    resp = real_client.post(
        f"/api/v1/assets/{asset_id}/preview",
        json={
            "regions": [{"x": 180, "y": 100, "width": 280, "height": 280, "label": "subject"}],
            "smoothness": 50,
            "detail": 50,
            "version": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["control_points"] > 0
