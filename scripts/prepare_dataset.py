"""Organise one or more plate image datasets for BacterioScope validation.

Produces a normalised ground-truth CSV at data/processed/ground_truth.csv
that validate_measurement.py can consume directly.

Two modes of operation
-----------------------
Single-source (UZH/Dryad, backward-compatible)::

    python scripts/prepare_dataset.py --data-dir data/raw/dryad_uzh

Multi-source (reads all YAML configs in data/sources/)::

    python scripts/prepare_dataset.py --sources-dir data/sources

Output columns of data/processed/ground_truth.csv::

    source               — dataset name declared in the YAML config
    image_filename       — basename of the image file (e.g. plate_0001.jpg)
    antibiotic_code      — original antibiotic code from the dataset (e.g. CIP)
    antibiotic_name      — normalised full name (e.g. ciprofloxacin)
    zone_diameter_mm_ref — reference measurement in mm
    category_ref         — reference S/I/R category (EUCAST or CLSI)
    standard             — measurement standard declared in the YAML (EUCAST/CLSI)
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
    p = argparse.ArgumentParser(description="Prepare dataset(s) for validation.")
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--data-dir", type=Path, default=None,
        help="Single-source: directory with UZH raw data.",
    )
    group.add_argument(
        "--sources-dir", type=Path, default=None,
        help="Multi-source: directory containing YAML source configs.",
    )
    p.add_argument("--output-dir", type=Path, default=Path("data/processed"),
                   help="Output directory (default: data/processed).")
    return p.parse_args()


def _find_images(data_dir: Path) -> dict[str, Path]:
    images: dict[str, Path] = {}
    for path in data_dir.rglob("*"):
        if path.suffix.lower() in _IMAGE_SUFFIXES:
            images[path.stem] = path
    return images


def _find_measurements_file(data_dir: Path) -> Path | None:
    for suffix in (".csv", ".xlsx", ".xls"):
        for path in data_dir.rglob(f"*{suffix}"):
            return path
    return None


def _read_csv_flexible(path: Path) -> tuple[list[str], list[list[str]]]:
    for delimiter in (",", ";", "\t"):
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh, delimiter=delimiter))
        if rows and len(rows[0]) > 2:
            return rows[0], rows[1:]
    with path.open(newline="", encoding="latin-1") as fh:
        rows = list(csv.reader(fh))
    return (rows[0] if rows else []), rows[1:]


def _detect_columns(headers: list[str]) -> dict[str, int]:
    lower = [h.lower().strip() for h in headers]
    mapping: dict[str, int] = {}
    for candidates, role in [
        (["isolate", "sample", "id", "plate", "image", "filename"], "id"),
        (["antibiotic", "drug", "agent", "disc", "disk", "abx"], "antibiotic"),
        (["diameter", "zone", "mm", "diam", "size"], "diameter"),
        (["category", "sir", "result", "class", "interp"], "category"),
    ]:
        for col in candidates:
            if any(col in h for h in lower):
                mapping[role] = next(i for i, h in enumerate(lower) if col in h)
                break
    return mapping


def _process_rows(
    rows: list[list[str]],
    col_map: dict[str, int],
    images: dict[str, Path],
    source_name: str,
    standard: str,
) -> list[dict[str, str]]:
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
            "source": source_name,
            "image_filename": image_path.name,
            "antibiotic_code": ab_code,
            "antibiotic_name": _EUCAST_TO_CLSI_NAME.get(ab_code, ab_code.lower()),
            "zone_diameter_mm_ref": diameter,
            "category_ref": category if category in {"S", "I", "R"} else "",
            "standard": standard,
        })
    if skipped:
        print(f"  Skipped {skipped} rows (missing image match or invalid diameter).")
    return output


def _write_ground_truth(records: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source", "image_filename", "antibiotic_code", "antibiotic_name",
        "zone_diameter_mm_ref", "category_ref", "standard",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _process_single_dir(
    data_dir: Path, source_name: str, standard: str
) -> list[dict[str, str]]:
    if not data_dir.is_dir():
        print(f"  Warning: {data_dir} not found, skipping.", file=sys.stderr)
        return []
    print(f"  Scanning {data_dir} ...")
    images = _find_images(data_dir)
    print(f"    Found {len(images)} plate images.")
    meas_file = _find_measurements_file(data_dir)
    if meas_file is None:
        print(f"    No measurements file found in {data_dir}, skipping.", file=sys.stderr)
        return []
    if meas_file.suffix != ".csv":
        print(f"    Excel format not supported without openpyxl. Convert to CSV.", file=sys.stderr)
        return []
    headers, rows = _read_csv_flexible(meas_file)
    col_map = _detect_columns(headers)
    print("    Column mapping:")
    for role, idx in sorted(col_map.items()):
        print(f"      {role:12s} <- col[{idx}]: {headers[idx]!r}")
    missing = {"id", "antibiotic", "diameter"} - col_map.keys()
    if missing:
        print(f"    Error: could not detect columns: {sorted(missing)}.", file=sys.stderr)
        return []
    return _process_rows(rows, col_map, images, source_name, standard)


def _load_source_configs(sources_dir: Path) -> list[dict[str, str]]:
    try:
        import yaml
    except ImportError:
        print(
            "Error: PyYAML is required for multi-source mode.\n"
            "Install with: pip install PyYAML",
            file=sys.stderr,
        )
        sys.exit(1)
    configs = []
    for yaml_path in sorted(sources_dir.glob("*.yaml")):
        with yaml_path.open(encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        configs.append(cfg)
    return configs


def main() -> None:
    args = _parse_args()

    if args.sources_dir is not None:
        if not args.sources_dir.is_dir():
            print(f"Error: {args.sources_dir} not found.", file=sys.stderr)
            sys.exit(1)
        configs = _load_source_configs(args.sources_dir)
        if not configs:
            print(f"Error: no YAML configs found in {args.sources_dir}.", file=sys.stderr)
            sys.exit(1)
        all_records: list[dict[str, str]] = []
        for cfg in configs:
            name = cfg.get("name", "unknown")
            path = Path(cfg.get("path", ""))
            standard = cfg.get("standard", "unknown")
            print(f"Processing source: {name}")
            records = _process_single_dir(path, name, standard)
            all_records.extend(records)
            print(f"    {len(records)} records from {name}.")
    else:
        data_dir = args.data_dir or Path("data/raw/dryad_uzh")
        if not data_dir.is_dir():
            print(
                f"Error: {data_dir} not found.\n"
                "Run python scripts/download_data.py first.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Single-source mode: {data_dir}")
        all_records = _process_single_dir(data_dir, "dryad_uzh", "EUCAST")

    if not all_records:
        print(
            "Error: 0 records produced after processing all sources.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_path = args.output_dir / "ground_truth.csv"
    _write_ground_truth(all_records, output_path)
    print(f"Wrote {len(all_records)} records to {output_path}")
    print("Next step: python scripts/validate_measurement.py")


if __name__ == "__main__":
    main()
