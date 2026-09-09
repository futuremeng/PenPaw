"""SVG 构建与度量工具（mock 与真实实现共用）。"""

from __future__ import annotations

import math
import re

# 确定性调色板（MVP 仅纯色填充，PRD 附录 B.3）
PALETTE = ["#4F7CFF", "#FF7A59", "#3BB273", "#F5B841", "#8E6BF1", "#E85D9E", "#2BB3C0"]

# 路径命令：M/L/Q/C 各携带的控制点数量
_CMD_POINTS = {"M": 1, "L": 1, "Q": 2, "C": 3}
_CMD_RE = re.compile(r"([MLQC])\s*([-\d.eE,\s]+?)(?=[MLQCZ]|$)")


def count_control_points(svg_text: str) -> int:
    """统计 SVG 中全部路径的控制点数量（PRD §4.3 Path Complexity 口径）。

    口径：M/L 各计 1，Q 计 2（控制点+端点），C 计 3（两手柄+端点）。
    """
    total = 0
    for path in re.findall(r"d=\"([^\"]+)\"", svg_text):
        for cmd, nums in _CMD_RE.findall(path):
            if nums.strip():
                total += _CMD_POINTS[cmd]
    return total


def _smooth_closed_path(cx: float, cy: float, rx: float, ry: float, n: int) -> str:
    """生成 n 段二次贝塞尔的闭合平滑路径（椭圆近似）。"""

    n = max(3, n)
    pts = [
        (cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]
    parts = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(n):
        cur = pts[i]
        nxt = pts[(i + 1) % n]
        # 控制点取相邻两点中点外推，形成平滑曲线
        prev = pts[(i - 1) % n]
        hx = cur[0] + (nxt[0] - prev[0]) / 4
        hy = cur[1] + (nxt[1] - prev[1]) / 4
        parts.append(f"Q {hx:.2f} {hy:.2f} {nxt[0]:.2f} {nxt[1]:.2f}")
    parts.append("Z")
    return " ".join(parts)


def generate_region_paths(
    regions: list,
    smoothness: int,
    detail: int,
    simplify_factor: float = 1.0,
) -> list[tuple[str, str, str, str]]:
    """为每个区域生成 (group_id, label, fill, path_d)。

    参数映射（PRD 附录 A 的 mock 化）：
    - smoothness 越高 → 主轮廓段数越少（更圆滑）
    - detail 越高 → 每个区域附加的内部细节色块越多
    - simplify_factor < 1 → Stage 3 简化后的段数比例
    """
    main_segments = max(3, int((14 - smoothness // 10) * simplify_factor))
    inner_blocks = detail // 25  # 0~4 个内部细节块
    out: list[tuple[str, str, str, str]] = []
    for idx, region in enumerate(regions):
        fill = PALETTE[idx % len(PALETTE)]
        cx = region.x + region.width / 2
        cy = region.y + region.height / 2
        rx = region.width / 2 * 0.92
        ry = region.height / 2 * 0.92
        d = _smooth_closed_path(cx, cy, rx, ry, main_segments)
        out.append((f"region-{idx + 1}", region.label, fill, d))
        for k in range(inner_blocks):
            scale = 0.55 - 0.12 * k
            if scale <= 0.1:
                break
            inner = _smooth_closed_path(cx, cy, rx * scale, ry * scale, max(3, main_segments - 2))
            inner_id = f"region-{idx + 1}-inner-{k + 1}"
            inner_label = f"{region.label}-detail"
            inner_fill = PALETTE[(idx + k + 1) % len(PALETTE)]
            out.append((inner_id, inner_label, inner_fill, inner))
    return out


def build_svg(
    width: int,
    height: int,
    groups: list[tuple[str, str, str, str]],
    model_version: str = "",
    params: dict | None = None,
) -> str:
    """按 PRD 附录 B 规范构建 SVG 1.1 文档。

    groups: (group_id, label, fill, path_d)
    """
    header_params = ", ".join(f"{k}={v}" for k, v in (params or {}).items())
    body = []
    for group_id, label, fill, d in groups:
        body.append(
            f'  <g id="{group_id}" data-label="{label}">\n'
            f'    <path d="{d}" fill="{fill}" />\n'
            f"  </g>"
        )
    return (
        f"<!-- PenPaw SVG | model={model_version} | {header_params} -->\n"
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height} '
        f'width="{width}" height="{height}">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
