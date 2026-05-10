#!/usr/bin/env python3
"""
Batch-convert raster images to WebP equivalents.

Usage:
    python scripts/convert-images-to-webp.py [--force]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, Tuple

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "app" / "static" / "images"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

RESIZE_TARGETS: Dict[Path, Tuple[int, int]] = {
    Path("app/static/images/lucas.png"): (320, 427),
}


def gather_images(source: Path) -> Iterable[Path]:
    for path in source.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def webp_kwargs(source_path: Path) -> dict:
    if source_path.suffix.lower() == ".png":
        return {"lossless": True, "method": 6}
    return {"quality": 82, "method": 6}


def convert_image(source_path: Path, force: bool = False) -> Tuple[Path, bool, bool]:
    dest_path = source_path.with_suffix(".webp")
    if dest_path.exists() and not force:
        return dest_path, False, False

    with Image.open(source_path) as img:
        resize_target = RESIZE_TARGETS.get(source_path.relative_to(ROOT))
        processed = img
        resized = False

        if resize_target:
            resized_img = ImageOps.contain(img, resize_target, Image.LANCZOS)
            if resized_img.size != img.size:
                processed = resized_img
                resized = True
        else:
            processed = img.copy()

        if processed.mode in {"P", "RGBA", "LA"}:
            webp_ready = processed.convert("RGBA")
        else:
            webp_ready = processed.convert("RGB")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        webp_ready.save(dest_path, format="WEBP", **webp_kwargs(source_path))

    return dest_path, True, resized


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert images to WebP format.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source_dir = args.source.resolve()
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")

    converted = skipped = resized = 0
    for image_path in gather_images(source_dir):
        dest_path, did_convert, did_resize = convert_image(image_path, force=args.force)
        if did_convert:
            print(f"Saved {dest_path.relative_to(ROOT)}")
            converted += 1
        else:
            skipped += 1
        if did_resize:
            resized += 1

    print(f"Done. Converted {converted}; skipped {skipped}; resized {resized}.")


if __name__ == "__main__":
    main()
