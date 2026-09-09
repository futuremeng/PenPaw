"""VTracer baseline（MIT，PRD R5：直接以官方 Python 库集成）。

M4 启用：`uv add vtracer` 后取消下方 NotImplementedError。
"""

from __future__ import annotations

from pathlib import Path


def run_vtracer(image_path: Path, out_path: Path) -> str:
    """对图像运行 VTracer（官方默认参数，PRD §4.3），返回 SVG 文本。"""
    try:
        import vtracer  # type: ignore
    except ImportError:
        raise NotImplementedError(
            "vtracer 未安装：M4 执行 `uv add vtracer`（PRD §4.3 baseline）"
        ) from None
    svg = vtracer.convert_file(str(image_path), str(out_path))
    return svg if isinstance(svg, str) else out_path.read_text()
