"""评估指标（PRD §4.3 / §7 口径）。"""

from __future__ import annotations

from pathlib import Path

from penpaw_pipeline.svg import count_control_points


def svg_control_points(svg_text: str) -> int:
    """控制点数量（Path Complexity，PRD §4.3）。"""
    return count_control_points(svg_text)


def svg_file_size(svg_text: str) -> int:
    """SVG 文件大小（实际序列化后字节数，PRD §4.3）。"""
    return len(svg_text.encode("utf-8"))


def lpips(original: Path, generated: Path) -> float | None:
    """感知保真度（越低越好）。M4 落地：lpips 库 + VGG 权重。"""
    raise NotImplementedError("LPIPS 于 M4 落地（PRD §4.3）")


def ssim(original: Path, generated: Path) -> float | None:
    """结构相似度（越高越好）。M4 落地：scikit-image。"""
    raise NotImplementedError("SSIM 于 M4 落地（PRD §4.3）")


def fid(generated_dir: Path, reference_dir: Path) -> float | None:
    """集合级 FID（仅 Golden Test Set 离线批量评估使用，PRD §4.3）。M4 落地。"""
    raise NotImplementedError("FID 于 M4 落地（PRD §4.3，仅离线批量）")


def control_point_reduction(ai_svg: str, baseline_svg: str) -> float:
    """相对 baseline 的控制点精简率（PRD §7.2：同等 LPIPS 下需 > 30%）。

    注意：调用方需先确认"同等视觉还原度"口径（LPIPS 差 < 0.02）。
    """
    ai = svg_control_points(ai_svg)
    base = svg_control_points(baseline_svg)
    if base == 0:
        return 0.0
    return (base - ai) / base
