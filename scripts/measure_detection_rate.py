"""Reproduce the disk-detection accuracy figures cited for the pitch.

Measures, on the 80-image real UZH subset, how often each detector's disk
count matches the true count (independent ground truth from
``ground_truth.csv``, not either detector's own output): Hough (the
pipeline's real default) and the single-class YOLOv8 detector at its tuned
confidence threshold (see F2 in CLAUDE.md for how 0.28 was found).

Usage::

    python scripts/measure_detection_rate.py
"""

from __future__ import annotations

import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bacterioscope.detection.detector import DiskDetector  # noqa: E402
from bacterioscope.utils.calibration import calibrate_px_per_mm  # noqa: E402
from bacterioscope.utils.image import resize_canonical  # noqa: E402

_SUBSET_SIZE = 80
_SINGLE_CLASS_WEIGHTS = Path("data/models/single_class/yolov8_disks.pt")
_SINGLE_CLASS_CONFIDENCE = 0.28


def _true_counts() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    with open("data/processed/ground_truth.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            counts[row["image_filename"]] += 1
    return counts


def _measure_hough(paths: list[str], true_counts: dict[str, int]) -> tuple[int, int, float]:
    detector = DiskDetector(weights=Path("nonexistent.pt"))
    exact, n, abs_err = 0, 0, 0.0
    for path in paths:
        name = Path(path).name
        if name not in true_counts:
            continue
        image = cv2.imread(path)
        image, _ = resize_canonical(image)
        _, px_per_mm = calibrate_px_per_mm(image)
        disks = detector.detect(image, px_per_mm=px_per_mm)
        exact += len(disks) == true_counts[name]
        abs_err += abs(len(disks) - true_counts[name])
        n += 1
    return exact, n, abs_err / n


def _measure_single_class(paths: list[str], true_counts: dict[str, int]) -> tuple[int, int, float]:
    from ultralytics import YOLO

    model = YOLO(str(_SINGLE_CLASS_WEIGHTS))
    exact, n, abs_err = 0, 0, 0.0
    for path in paths:
        name = Path(path).name
        if name not in true_counts:
            continue
        image = cv2.imread(path)
        image, _ = resize_canonical(image)
        results = model(image, conf=_SINGLE_CLASS_CONFIDENCE, verbose=False, imgsz=1280)
        count = len(results[0].boxes)
        exact += count == true_counts[name]
        abs_err += abs(count - true_counts[name])
        n += 1
    return exact, n, abs_err / n


def main() -> int:
    true_counts = _true_counts()
    paths = sorted(glob.glob("data/raw/dryad_uzh/images_original/*.jpg"))[:_SUBSET_SIZE]

    h_exact, h_n, h_mae = _measure_hough(paths, true_counts)
    print(f"Hough: {h_exact}/{h_n} exact-count match ({h_exact / h_n:.1%}), "
          f"mean abs error {h_mae:.2f} disks")

    if _SINGLE_CLASS_WEIGHTS.exists():
        y_exact, y_n, y_mae = _measure_single_class(paths, true_counts)
        print(f"Single-class YOLO (conf={_SINGLE_CLASS_CONFIDENCE}): "
              f"{y_exact}/{y_n} exact-count match ({y_exact / y_n:.1%}), "
              f"mean abs error {y_mae:.2f} disks")
    else:
        print(f"Single-class weights not found at {_SINGLE_CLASS_WEIGHTS}, skipped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
