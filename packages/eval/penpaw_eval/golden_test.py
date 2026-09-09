"""Golden Test Set 批量评估 CLI（PRD §7.3 / 附录 C）。

M1：骨架实现——遍历图像目录跑 mock 流水线，输出结构性指标报告（JSON）。
M4：接入 LPIPS/SSIM/FID + VTracer 对比 + CI 回归门禁（指标退化 > 5% 阻断发布）。

用法：
    penpaw-eval --images /path/to/testset --out report.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from penpaw_pipeline import PipelineRunner, SliderParams

from penpaw_eval import metrics


def evaluate_image(runner: PipelineRunner, image_path: Path) -> dict:
    # M1 mock：不解析真实图像尺寸，用固定尺寸占位；M4 接入 PIL 读取真实尺寸
    width, height = 1024, 1024
    t0 = time.perf_counter()
    stage2 = runner.fast_path((width, height), [], SliderParams())
    fast_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    stage3 = runner.slow_path(stage2, (width, height))
    slow_ms = (time.perf_counter() - t0) * 1000

    return {
        "image": image_path.name,
        "stage2": {
            "control_points": stage2.control_points,
            "file_size": metrics.svg_file_size(stage2.svg),
            "latency_ms": round(fast_ms, 1),
        },
        "stage3": {
            "control_points": stage3.control_points,
            "file_size": metrics.svg_file_size(stage3.svg),
            "latency_ms": round(slow_ms, 1),
            "degraded": stage3.degraded,
        },
        # M4 填充：lpips / ssim / vtracer 对比
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PenPaw Golden Test Set 评估")
    parser.add_argument("--images", required=True, type=Path, help="测试集图像目录")
    parser.add_argument("--out", type=Path, default=Path("report.json"))
    args = parser.parse_args()

    if not args.images.is_dir():
        raise SystemExit(f"图像目录不存在：{args.images}")

    runner = PipelineRunner()
    images = sorted(
        p for p in args.images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    report = {
        "testset_version": "unknown",  # M4：绑定 testset-vX.Y（PRD 附录 C）
        "n_images": len(images),
        "results": [evaluate_image(runner, p) for p in images],
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"评估完成：{len(images)} 张 → {args.out}")


if __name__ == "__main__":
    main()
