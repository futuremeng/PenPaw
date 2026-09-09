#!/usr/bin/env python3
"""下载 PenPaw 运行时模型权重，并写入许可证清单（TDD §4.4 / §8 义务③）。

用法：
    uv run python scripts/download_models.py            # 下载 SAM + DINOv2
    uv run python scripts/download_models.py --dry-run  # 仅打印将下载的内容

权重落盘到仓库根 models/（已 gitignore），并生成 models/manifest.json
逐条标注许可证——合规义务（PRD R3 / TDD §8）。

⚠️ 严禁下载 Cell-DINO / XRay-DINO 子模块（非商用许可，PRD R3 禁用清单）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models"

# (文件名, 下载 URL, 许可证, 用途, 大小约)
WEIGHTS = [
    {
        "file": "sam_vit_b.pth",
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "license": "Apache-2.0",
        "component": "SAM ViT-B（Stage 1 语义分割）",
        "size_mb": 375,
    },
    {
        "file": "dinov2_vits14_pretrain.pth",
        "url": "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth",
        "license": "CC-BY-4.0（允许商用，需署名）",
        "component": "DINOv2 ViT-S/14（Stage 1 语义特征）",
        "size_mb": 84,
    },
]


def _download(url: str, dest: Path) -> None:
    print(f"  ↓ {url}")
    print(f"    → {dest}（约 {dest.stat().st_size if dest.exists() else '?'} 字节）")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
        print()
    tmp.rename(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 PenPaw 模型权重")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不下载")
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"weights": []}

    for w in WEIGHTS:
        dest = MODELS_DIR / w["file"]
        print(f"[{w['license']}] {w['component']}")
        if dest.exists():
            print(f"  ✓ 已存在，跳过: {dest.name}")
        elif args.dry_run:
            print(f"  （dry-run）将下载 {w['size_mb']}MB → {dest.name}")
        else:
            _download(w["url"], dest)
        manifest["weights"].append(
            {
                "file": w["file"],
                "license": w["license"],
                "component": w["component"],
                "exists": dest.exists(),
            }
        )

    manifest_path = MODELS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\n许可证清单已写入: {manifest_path}")
    print("提醒：DINOv2 权重为 CC-BY-4.0，产品需保留署名（见 THIRD_PARTY.md）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
