"""Organise the Dryad/UZH SIRscan dataset for BacterioScope validation.

Reads the raw data extracted by download_data.py and produces a normalised
ground-truth CSV at data/processed/ground_truth.csv that validate_measurement.py
can consume directly.

Expected input at data/raw/dryad_uzh/:
    Plate images (JPEG/PNG), one per isolate.
    A measurements file (CSV or XLSX) with at minimum: isolate identifier,
    antibiotic code or name, zone diameter in mm, and EUCAST S/I/R category.

Output columns of data/processed/ground_truth.csv:
    image_filename       — basename of the image file (e.g. plate_0001.jpg)
    antibiotic_code      — original antibiotic code from the dataset (e.g. CIP)
    antibiotic_name      — our normalised full name (e.g. ciprofloxacin)
    zone_diameter_mm_ref — SIRscan reference measurement in mm
    category_eucast      — EUCAST S/I/R category from the reference system

Usage::

    python scripts/prepare_dataset.py
    python scripts/prepare_dataset.py --data-dir data/raw/dryad_uzh
                                      --output-dir data/processed
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

_EUCAST_TO_CLSI_NAME: dict[str, str] = {
    "AMP": "ampicillin",
    "AMC": "amoxicillin-clavulanate",
    "TZP": "piperacillin-tazobactam",
    "CRO": "ceftriaxone",
    "CAZ": "ceftazidime",
    "FEP": "cefepime",
    "IPM": "imipenem",
    "MEM": "meropenem",
    "ERT": "ertapenem",
    "DOR": "doripenem",
    "CIP": "ciprofloxacin",
    "LEV": "levofloxacin",
    "GEN": "gentamicin",
    "AMK": "amikacin",
    "SXT": "trimethoprim-sulfamethoxazole",
    "AMX": "ampicillin",
    "CTX": "ceftriaxone",
    "TMP": "trimethoprim-sulfamethoxazole",
}


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Prepare UZH dataset for validation.")
    p.add_argument("--data-dir", type=Path, default=Path("data/raw/dryad_uzh"),
                   help="Directory with raw Dryad data (default: data/raw/dryad_uzh).")
    p.add_argument("--output-dir", type=Path, default=Path("data/processed"),
                   help="Output directory (default: data/processed).")
    return p.parse_args()


def _find_images(data_dir: Path) -> dict[str, Path]:
    """Return mapping of stem → path for all plate images in data_dir."""
    images: dict[str, Path] = {}
    for path in data_dir.rglob("*"):
        if path.suffix.lower() in _IMAGE_SUFFIXES:
            images[path.stem] = path
    return images


def _find_measurements_file(data_dir: Path) -> Path | None:
    """Locate the measurements CSV or XLSX in data_dir (first match)."""
    for suffix in (".csv", ".xlsx", ".xls"):
        for path in data_dir.rglob(f"*{suffix}"):
            return path
    return None


def _read_csv_flexible(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read a CSV file and return (headers, rows), trying common delimiters."""
    for delimiter in (",", ";", "\t"):
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh, delimiter=delimiter)
            rows = list(reader)
        if rows and len(rows[0]) > 2:
            return rows[0], rows[1:]
    with path.open(newline="", encoding="latin-1") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    return (rows[0] if rows else []), rows[1:]


def _detect_columns(headers: list[str]) -> dict[str, int]:
    """Map semantic roles to column indices by matching common header names."""
    lower = [h.lower().strip() for h in headers]
    mapping: dict[str, int] = {}

    id_candidates = ["isolate", "sample", "id", "plate", "image", "filename"]
    for col in id_candidates:
        if any(col in h for h in lower):
            mapping["id"] = next(i for i, h in enumerate(lower) if col in h)
            break

    ab_candidates = ["antibiotic", "drug", "agent", "disc", "disk", "abx"]
    for col in ab_candidates:
        if any(col in h for h in lower):
            mapping["antibiotic"] = next(i for i, h in enumerate(lower) if col in h)
            break

    diam_candidates = ["diameter", "zone", "mm", "diam", "size"]
    for col in diam_candidates:
        if any(col in h for h in lower):
            mapping["diameter"] = next(i for i, h in enumerate(lower) if col in h)
            break

    cat_candidates = ["category", "sir", "result", "class", "interp"]
    for col in cat_candidates:
        if any(col in h for h in lower):
            mapping["category"] = next(i for i, h in enumerate(lower) if col in h)
            break

    return mapping


def _process_rows(
    rows: list[list[str]],
    col_map: dict[str, int],
    images: dict[str, Path],
) -> list[dict[str, str]]:
    """Convert raw CSV rows to normalised records matched to image files."""
    output: list[dict[str, str]] = []
    skipped = 0
    for row in rows:
        if not row or len(row) <= max(col_map.values(), default=0):
            skipped += 1
            continue
        isolate_id = row[col_map["id"]].strip() if "id" in col_map else ""
        ab_code = row[col_map["antibiotic"]].strip().upper() if "antibiotic" in col_map else ""
        diameter = row[col_map["diameter"]].strip() if "diameter" in col_map else ""
        category = row[col_map["category"]].strip().upper() if "category" in col_map else ""

        image_path = images.get(isolate_id) or next(
            (v for k, v in images.items() if isolate_id in k), None
        )
        if image_path is None:
            skipped += 1
            continue

        try:
            float(diameter)
        except ValueError:
            skipped += 1
            continue

        output.append({
            "image_filename": image_path.name,
            "antibiotic_code": ab_code,
            "antibiotic_name": _EUCAST_TO_CLSI_NAME.get(ab_code, ab_code.lower()),
            "zone_diameter_mm_ref": diameter,
            "category_eucast": category if category in {"S", "I", "R"} else "",
        })
    if skipped:
        print(f"  Skipped {skipped} rows (missing image match or invalid diameter).")
    return output


def _write_ground_truth(records: list[dict[str, str]], output_path: Path) -> None:
    """Write records to the normalised ground-truth CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image_filename", "antibiotic_code", "antibiotic_name",
        "zone_diameter_mm_ref", "category_eucast",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    """Entry point for dataset preparation."""
    args = _parse_args()

    if not args.data_dir.is_dir():
        print(
            f"Error: {args.data_dir} not found.\n"
            "Run python scripts/download_data.py first, then place the\n"
            "extracted Dryad files in that directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Scanning images in {args.data_dir} ...")
    images = _find_images(args.data_dir)
    print(f"  Found {len(images)} plate images.")

    meas_file = _find_measurements_file(args.data_dir)
    if meas_file is None:
        print(
            "Warning: no measurements file (CSV/XLSX) found in data directory.\n"
            "Expected a file with antibiotic name, zone diameter, and category columns.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  Measurements file: {meas_file.name}")

    if meas_file.suffix == ".csv":
        headers, rows = _read_csv_flexible(meas_file)
    else:
        print(
            f"Error: Excel format not supported without openpyxl. "
            f"Convert {meas_file.name} to CSV first.",
            file=sys.stderr,
        )
        sys.exit(1)

    col_map = _detect_columns(headers)
    print("  Column mapping detected:")
    for role, idx in sorted(col_map.items()):
        print(f"    {role:12s} <- col[{idx}]: {headers[idx]!r}")
    missing = {"id", "antibiotic", "diameter"} - col_map.keys()
    if missing:
        print(
            f"Error: could not detect columns: {sorted(missing)}.\n"
            f"Headers found: {headers}\n"
            "Edit _detect_columns() in prepare_dataset.py to match the actual column names.",
            file=sys.stderr,
        )
        sys.exit(1)

    records = _process_rows(rows, col_map, images)
    if not records:
        print(
            "Error: 0 records produced after processing.\n"
            f"  Column mapping: {col_map}\n"
            f"  Headers: {headers}\n"
            "  Check that isolate identifiers in the CSV match image filenames.\n"
            "  If column names differ from expected, update _detect_columns().",
            file=sys.stderr,
        )
        sys.exit(1)
    output_path = args.output_dir / "ground_truth.csv"
    _write_ground_truth(records, output_path)
    print(f"  Wrote {len(records)} records to {output_path}")
    print("Next step: python scripts/validate_measurement.py")


if __name__ == "__main__":
    main()
