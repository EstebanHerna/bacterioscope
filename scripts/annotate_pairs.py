"""Generate disk-identity pairing templates for real plate validation images.

Rank-order pairing (the current default in validate_measurement.py) sorts both
the pipeline's measured diameters and the reference diameters ascending and
pairs them by position. That assumes rank order is preserved between the two
lists -- true only if detection never confuses which disk is which, which it
does on real photos. A correlation computed that way is an optimistic upper
bound, not a measurement: it cannot be reported as the project's real
accuracy number.

This script produces, for one or more real plate images:

- ``<stem>_numbered.png`` -- the plate with each detected disk circled and
  labelled with its index, next to the reference antibiotic list for that
  image (read from data/processed/ground_truth.csv) printed to stdout in the
  order the source DOCX table lists them.
- ``<stem>_pairs.csv`` -- a template with one row per detected disk and an
  empty ``antibiotic_code`` column, ready for a human (or an operator with
  visual access to the source table) to fill in by reading the printed label
  on each disk in the numbered image.

Usage::

    python scripts/annotate_pairs.py --image path/to/plate.jpg
    python scripts/annotate_pairs.py --batch data/raw/dryad_uzh/images_original --limit 20

Once pairs CSVs exist under --output-dir, validate_measurement.py picks them
up automatically and reports identity-matched EA/MAE/r alongside the rank-order
figures, clearly labelled as two different things.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bacterioscope.detection.detector import DiskDetector  # noqa: E402
from bacterioscope.utils.calibration import calibrate_px_per_mm  # noqa: E402
from bacterioscope.utils.image import resize_canonical  # noqa: E402

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_LABEL_COLOR = (60, 220, 60)
_CIRCLE_COLOR = (60, 220, 60)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=Path, help="Single image to process.")
    group.add_argument("--batch", type=Path, help="Directory of images to process.")
    p.add_argument("--limit", type=int, default=20, help="Max images in --batch mode.")
    p.add_argument("--output-dir", type=Path, default=Path("data/processed/pair_annotations"))
    p.add_argument("--weights", type=Path, default=Path("data/models/yolov8_disks.pt"))
    p.add_argument("--ground-truth", type=Path, default=Path("data/processed/ground_truth.csv"))
    return p.parse_args()


def _load_reference_antibiotics(csv_path: Path, image_filename: str) -> list[str]:
    if not csv_path.is_file():
        return []
    codes = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["image_filename"] == image_filename:
                codes.append(row["antibiotic_code"])
    return codes


def _annotate_numbered(image, disks) -> None:
    for i, disk in enumerate(disks):
        cv2.circle(image, (disk.center_x, disk.center_y), disk.radius_px, _CIRCLE_COLOR, 2)
        cv2.putText(
            image, str(i), (disk.center_x - 8, disk.center_y + 8),
            _FONT, 0.9, _LABEL_COLOR, 2, cv2.LINE_AA,
        )


def _write_pairs_template(disks, px_per_mm: float, out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["disk_index", "center_x", "center_y", "diameter_mm", "antibiotic_code"])
        for i, disk in enumerate(disks):
            diam_mm = round((2 * disk.radius_px) / px_per_mm, 1)
            writer.writerow([i, disk.center_x, disk.center_y, diam_mm, ""])


def process_image(
    image_path: Path,
    detector: DiskDetector,
    output_dir: Path,
    ground_truth_csv: Path,
) -> None:
    """Detect disks, save a numbered annotation, and write a pairing template."""
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"  Skipping {image_path.name}: could not read image.")
        return

    image, _ = resize_canonical(image)
    _, px_per_mm = calibrate_px_per_mm(image)
    disks = detector.detect(image, px_per_mm=px_per_mm)

    output_dir.mkdir(parents=True, exist_ok=True)
    numbered = image.copy()
    _annotate_numbered(numbered, disks)
    numbered_path = output_dir / f"{image_path.stem}_numbered.png"
    cv2.imwrite(str(numbered_path), numbered)

    pairs_path = output_dir / f"{image_path.stem}_pairs.csv"
    _write_pairs_template(disks, px_per_mm, pairs_path)

    reference = _load_reference_antibiotics(ground_truth_csv, image_path.name)
    print(f"  {image_path.name}: {len(disks)} disks detected -> {numbered_path.name}")
    print(f"    Reference antibiotics (source table order): {reference}")
    print(f"    Fill in: {pairs_path}")


def main() -> int:
    args = _parse_args()
    detector = DiskDetector(weights=args.weights)

    if args.image is not None:
        process_image(args.image, detector, args.output_dir, args.ground_truth)
        return 0

    images = sorted(args.batch.glob("*.jpg"))[: args.limit]
    if not images:
        print(f"No images found in {args.batch}", file=sys.stderr)
        return 1
    print(f"Processing {len(images)} images from {args.batch} ...")
    for image_path in images:
        process_image(image_path, detector, args.output_dir, args.ground_truth)
    print(f"\nDone. Annotate the *_pairs.csv files under {args.output_dir}, "
          "then re-run validate_measurement.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
