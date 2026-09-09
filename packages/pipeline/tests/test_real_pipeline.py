"""真实流水线（M2a）全链路集成测试：分割 → 方向场 → 生成 → 优化。"""

from __future__ import annotations

from penpaw_pipeline.config import PipelineConfig
from penpaw_pipeline.runner import PipelineRunner
from penpaw_pipeline.schemas import RoiRegion, SliderParams
from penpaw_pipeline.svg import count_control_points


def _real_runner() -> PipelineRunner:
    # M2a 测试走经典回退路径（use_sam/use_dinov2=False），保持快速确定性；
    # SAM/DINOv2 路径见 test_sam_integration.py（标记 slow）。
    return PipelineRunner(
        PipelineConfig(
            backend="real",
            model_version="rule-test-0.1",
            use_sam=False,
            use_dinov2=False,
        )
    )


def test_fast_path_full_image(circle_image):
    runner = _real_runner()
    out = runner.fast_path(circle_image, (640, 480), [], SliderParams(60, 40))
    assert out.svg.startswith("<!--")
    assert out.control_points > 0
    assert 0.0 < out.confidence <= 0.99
    assert out.intermediate["backend"] == "rule"
    assert len(out.intermediate["regions"]) >= 1


def test_fast_path_with_roi(circle_image):
    runner = _real_runner()
    roi = RoiRegion(x=180, y=120, width=280, height=240, label="subject")
    out = runner.fast_path(circle_image, (640, 480), [roi], SliderParams(50, 50))
    assert out.control_points > 0
    # ROI 内应产生带 subject 标签的区域
    labels = [r["label"] for r in out.intermediate["regions"]]
    assert any("subject" in lbl for lbl in labels)


def test_fast_path_flat_image_fallback(flat_image):
    """纯色图：回退整图单区域，仍应产出有效 SVG。"""
    runner = _real_runner()
    out = runner.fast_path(flat_image, (640, 480), [], SliderParams(50, 50))
    assert out.control_points > 0
    assert len(out.intermediate["regions"]) == 1


def test_slow_path_reduces_control_points(circle_image):
    """Stage 3 优化后控制点数应不高于 Stage 2（真实精简）。"""
    runner = _real_runner()
    stage2 = runner.fast_path(circle_image, (640, 480), [], SliderParams(50, 50))
    stage3 = runner.slow_path(stage2, (640, 480))
    assert stage3.degraded is False
    assert stage3.control_points <= stage2.control_points
    assert stage3.control_points == count_control_points(stage3.svg)
    assert stage3.svg.startswith("<!--")


def test_progress_callback_invoked(circle_image):
    runner = _real_runner()
    stage2 = runner.fast_path(circle_image, (640, 480), [], SliderParams(50, 50))
    progress: list[float] = []
    runner.slow_path(stage2, (640, 480), progress_cb=progress.append)
    assert len(progress) >= 1
    assert progress[-1] == 1.0


def test_mock_backend_still_works(circle_image):
    """mock 后端不受 image 参数影响（向后兼容）。"""
    runner = PipelineRunner(PipelineConfig(backend="mock"))
    out = runner.fast_path(None, (640, 480), [], SliderParams(50, 50))
    assert out.control_points > 0
