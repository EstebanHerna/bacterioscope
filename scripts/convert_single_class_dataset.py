"""Convert the 29-class Roboflow KB-AST dataset to a single "disk" class.

Locating a disk is a much easier task than reading its printed antibiotic
abbreviation. With 102 training images spread over 29 classes (about 3.5
examples per class), YOLOv8 cannot learn to distinguish them reliably
(mAP50=0.096, see docs/VALIDATION_REPORT.md). Collapsing every box to one
"disk" class turns the same 102 images into 102 examples of one concept,
which is achievable.

The antibiotic identity is resolved separately by panel position
(panels/*.yaml), not by the detector, so this does not remove any
functionality -- it only asks the detector to do the part it can actually
learn from this much data.

Usage::

    python scripts/convert_single_class_dataset.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_SPLITS = ("train", "valid", "test")


def _convert_split(src_root: Path, dst_root: Path, split: str) -> int:
    src_images = src_root / split / "images"
    src_labels = src_root / split / "labels"
    dst_images = dst_root / split / "images"
    dst_labels = dst_root / split / "labels"
    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)

    if not src_images.is_dir():
        return 0

    count = 0
    for img_path in src_images.iterdir():
        shutil.copy2(img_path, dst_images / img_path.name)
        label_path = src_labels / f"{img_path.stem}.txt"
        dst_label_path = dst_labels / f"{img_path.stem}.txt"
        if label_path.is_file():
            _rewrite_single_class(label_path, dst_label_path)
        else:
            dst_label_path.write_text("", encoding="utf-8")
        count += 1
    return count


def _rewrite_single_class(src: Path, dst: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    rewritten = []
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        _, x, y, w, h = parts
        rewritten.append(f"0 {x} {y} {w} {h}")
    dst.write_text("\n".join(rewritten) + ("\n" if rewritten else ""), encoding="utf-8")


def _write_dataset_yaml(dst_root: Path) -> Path:
    yaml_path = dst_root.parent / "roboflow_single_class_dataset.yaml"
    abs_root = dst_root.resolve()
    yaml_path.write_text(
        f"train: {abs_root / 'train' / 'images'}\n"
        f"val: {abs_root / 'valid' / 'images'}\n"
        f"test: {abs_root / 'test' / 'images'}\n"
        "\n"
        "nc: 1\n"
        "names:\n"
        "  - disk\n",
        encoding="utf-8",
    )
    return yaml_path


def main() -> int:
    src_root = Path("data/raw/roboflow_yolo")
    dst_root = Path("data/processed/roboflow_single_class")

    if not src_root.is_dir():
        print(f"Error: {src_root} not found.", file=sys.stderr)
        return 1

    total = 0
    for split in _SPLITS:
        n = _convert_split(src_root, dst_root, split)
        print(f"  {split}: {n} images converted")
        total += n

    yaml_path = _write_dataset_yaml(dst_root)
    print(f"\n{total} images converted to single-class 'disk' labels.")
    print(f"Dataset config: {yaml_path}")
    print("Next: python -m bacterioscope.detection.train "
          f"--data {yaml_path} --epochs 100 --imgsz 1280 --output data/models/single_class/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
