"""Measure whether a crop-fill-ratio flag is a real confidence signal.

Confirms, on the 316 identity-matched disk-antibiotic pairs, that
circularity alone does not linearly predict measurement error (it is
non-monotonic: the ~0.75-0.82 band, the confirmed signature of a mask
filling its own search crop rather than tracing a real biological edge, is
worse than both lower and higher circularity bands). Then sweeps the crop
bounding-box fill-ratio ceiling used to flag a measurement as untrustworthy,
reporting Essential Agreement (EA) for the unflagged set at each ceiling
against the EA of the full set, so the chosen threshold is read off a curve,
not assumed.

Usage::

    python scripts/measure_confidence_indicator.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bacterioscope.detection.detector import DiskDetector  # noqa: E402
from bacterioscope.segmentation.watershed import ZoneSegmenter  # noqa: E402
from bacterioscope.utils.calibration import calibrate_px_per_mm  # noqa: E402
from bacterioscope.utils.image import resize_canonical  # noqa: E402

_CIRCULARITY_BUCKETS = [(0.0, 0.6), (0.6, 0.7), (0.7, 0.75), (0.75, 0.82), (0.82, 0.9), (0.9, 1.01)]
_FILL_RATIO_SWEEP = [0.75, 0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 0.98, 1.01]


def _fill_ratio(mask: np.ndarray) -> float | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    w = xs.max() - xs.min()
    h = ys.max() - ys.min()
    bbox_area = w * h
    if bbox_area == 0:
        return None
    return float((mask.sum() / 255) / bbox_area)


def _collect_pairs() -> list[tuple[float, float, float | None]]:
    """Return (circularity, abs_error_mm, fill_ratio) for every identity-matched pair."""
    gt_rows: dict[str, dict[str, float]] = defaultdict(dict)
    with open("data/processed/ground_truth.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            gt_rows[row["image_filename"]][row["antibiotic_code"]] = float(
                row["zone_diameter_mm_ref"]
            )

    detector = DiskDetector(weights=Path("nonexistent.pt"))
    segmenter = ZoneSegmenter()
    pairs: list[tuple[float, float, float | None]] = []

    for pairs_path in Path("data/processed/pair_annotations").glob("*_pairs.csv"):
        stem = pairs_path.name.replace("_pairs.csv", "")
        image_path = Path("data/raw/dryad_uzh/images_original") / f"{stem}.jpg"
        if not image_path.exists():
            continue
        image = cv2.imread(str(image_path))
        image, _ = resize_canonical(image)
        _, px_per_mm = calibrate_px_per_mm(image)
        disks = detector.detect(image, px_per_mm=px_per_mm)
        zones = segmenter.segment_all(image, disks, px_per_mm)

        with pairs_path.open(newline="", encoding="utf-8") as fh:
            disk_codes = {
                int(row["disk_index"]): row["antibiotic_code"].strip()
                for row in csv.DictReader(fh)
                if row["antibiotic_code"].strip()
            }
        image_gt = gt_rows.get(f"{stem}.jpg", {})

        for idx, code in disk_codes.items():
            if idx >= len(zones) or code not in image_gt:
                continue
            zone = zones[idx]
            abs_err = abs(zone.diameter_mm - image_gt[code])
            fill = _fill_ratio(zone.mask) if zone.mask is not None else None
            pairs.append((zone.circularity, abs_err, fill))

    return pairs


def _report_circularity_buckets(pairs: list[tuple[float, float, float | None]]) -> None:
    circ = np.array([p[0] for p in pairs])
    err = np.array([p[1] for p in pairs])
    print(f"Pearson correlation (circularity, abs error): {np.corrcoef(circ, err)[0, 1]:.3f}")
    print("\nEA and MAE by circularity band:")
    for lo, hi in _CIRCULARITY_BUCKETS:
        mask = (circ >= lo) & (circ < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        ea = (err[mask] <= 2.0).mean()
        print(f"  [{lo:.2f}, {hi:.2f}): n={n:4d}  EA={ea:.1%}  MAE={err[mask].mean():.2f}mm")


def _report_fill_ratio_sweep(pairs: list[tuple[float, float, float | None]]) -> None:
    fill = np.array([p[2] if p[2] is not None else -1.0 for p in pairs])
    err = np.array([p[1] for p in pairs])
    has_fill = fill >= 0
    baseline_ea = (err[has_fill] <= 2.0).mean()
    print(f"\nBaseline EA (all {has_fill.sum()} pairs with a mask): {baseline_ea:.1%}")
    print("\nCeiling | % flagged | n unflagged | EA unflagged | EA flagged")
    for ceiling in _FILL_RATIO_SWEEP:
        flagged = has_fill & (fill >= ceiling)
        unflagged = has_fill & (fill < ceiling)
        pct_flagged = flagged.sum() / has_fill.sum()
        ea_unflagged = (err[unflagged] <= 2.0).mean() if unflagged.sum() else float("nan")
        ea_flagged = (err[flagged] <= 2.0).mean() if flagged.sum() else float("nan")
        print(
            f"  {ceiling:.2f}   |  {pct_flagged:6.1%}  |  {unflagged.sum():5d}     |"
            f"  {ea_unflagged:6.1%}     |  {ea_flagged:6.1%}"
        )


def main() -> int:
    pairs = _collect_pairs()
    print(f"Collected {len(pairs)} identity-matched disk-antibiotic pairs.\n")
    _report_circularity_buckets(pairs)
    _report_fill_ratio_sweep(pairs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
