"""后端 API 全链路测试（M1：mock 流水线）。"""

from __future__ import annotations

import io
import json
import time

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes(width: int = 640, height: int = 480, color: tuple = (200, 60, 60)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path):
    settings = Settings(storage_dir=tmp_path / "assets", stage3_timeout_s=10.0)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _upload(client: TestClient, data: bytes, filename: str = "test.png") -> dict:
    resp = client.post(
        "/api/v1/uploads",
        files={"file": (filename, data, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_full_flow_upload_preview_optimize_export(client):
    # 1. 上传
    asset = _upload(client, _png_bytes())
    assert asset["width"] == 640 and asset["height"] == 480
    assert asset["downsampled"] is False
    asset_id = asset["asset_id"]

    # 2. 预览（带 ROI + 滑块）
    resp = client.post(
        f"/api/v1/assets/{asset_id}/preview",
        json={
            "regions": [{"x": 50, "y": 40, "width": 300, "height": 250, "label": "subject"}],
            "smoothness": 60,
            "detail": 40,
            "version": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["svg"].startswith("<!-- PenPaw SVG")
    assert preview["control_points"] > 0
    assert 0 < preview["confidence"] <= 1
    assert preview["version"] == 1

    # 3. 精细优化（异步 + 轮询）
    resp = client.post(f"/api/v1/assets/{asset_id}/optimize")
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["task_id"]

    deadline = time.time() + 15
    state = None
    while time.time() < deadline:
        state = client.get(f"/api/v1/tasks/{task_id}").json()
        if state["status"] in ("succeeded", "degraded", "failed"):
            break
        time.sleep(0.2)
    assert state["status"] == "succeeded", state
    assert state["progress"] == 1.0
    # Stage 3 应精简控制点（mock simplify_factor=0.6）
    assert state["control_points"] is not None
    assert state["control_points"] < preview["control_points"]

    # 4. 导出（快速 + 优化后）
    resp = client.get(f"/api/v1/assets/{asset_id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    fast_svg = resp.text

    resp = client.get(f"/api/v1/assets/{asset_id}/export", params={"optimized": True})
    assert resp.status_code == 200
    opt_svg = resp.text
    assert opt_svg != fast_svg
    assert 'stage=3' in opt_svg


def test_sse_events(client):
    asset = _upload(client, _png_bytes())
    asset_id = asset["asset_id"]
    client.post(f"/api/v1/assets/{asset_id}/preview", json={"version": 1})
    task_id = client.post(f"/api/v1/assets/{asset_id}/optimize").json()["task_id"]

    with client.stream("GET", f"/api/v1/tasks/{task_id}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    # 最后一条必须是终态
    assert events[-1]["status"] in ("succeeded", "degraded", "failed")
    assert events[-1]["progress"] == 1.0


def test_upload_rejects_bad_extension(client):
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("test.gif", _png_bytes(), "image/gif")},
    )
    assert resp.status_code == 415


def test_upload_rejects_oversized(client, monkeypatch):
    # 直接构造超过 10MB 的 body 太慢，改为 monkeypatch 阈值
    app_client = client
    app_client.app.state.settings.max_upload_bytes = 100
    resp = app_client.post(
        "/api/v1/uploads",
        files={"file": ("test.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 413


def test_upload_downscales_over_4k(client):
    big = _png_bytes(width=5000, height=1000)
    asset = _upload(client, big)
    assert asset["downsampled"] is True
    assert max(asset["width"], asset["height"]) == 2048


def test_preview_requires_existing_asset(client):
    resp = client.post("/api/v1/assets/nonexistent/preview", json={})
    assert resp.status_code == 404


def test_optimize_requires_preview(client):
    asset = _upload(client, _png_bytes())
    resp = client.post(f"/api/v1/assets/{asset['asset_id']}/optimize")
    assert resp.status_code == 409


def test_expired_asset_returns_410(client):
    asset = _upload(client, _png_bytes())
    asset_id = asset["asset_id"]
    # 手动把创建时间拨到 25 小时前
    store = client.app.state.store
    meta_path = store._meta_path(asset_id)
    meta = json.loads(meta_path.read_text())
    meta["created_at"] = time.time() - 25 * 3600
    meta_path.write_text(json.dumps(meta))

    resp = client.post(f"/api/v1/assets/{asset_id}/preview", json={})
    assert resp.status_code == 410


def test_cleanup_expired(client):
    asset = _upload(client, _png_bytes())
    asset_id = asset["asset_id"]
    store = client.app.state.store
    meta_path = store._meta_path(asset_id)
    meta = json.loads(meta_path.read_text())
    meta["created_at"] = time.time() - 25 * 3600
    meta_path.write_text(json.dumps(meta))

    assert store.cleanup_expired() == 1
    assert not store._dir(asset_id).exists()
