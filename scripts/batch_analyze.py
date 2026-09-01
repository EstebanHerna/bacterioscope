"""Batch-process a folder of Kirby-Bauer plate images.

Expects images following the naming convention::

    cepa_replica_condicion.ext

where:
  cepa       - strain identifier
  replica    - replicate label (number or letter)
  condicion  - experimental condition or date

Produces two output files in --output-dir:
  results.csv   one row per disk per image, with metadata, measurement, and flags
  errors.log    images that could not be processed, with the error message

Usage::

    python scripts/batch_analyze.py data/raw/session1 \\
        --output results/session1 --panel enterobacteria_clsi_12
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
from pathlib import Path

_SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
_NAME_RE = re.compile(r"^(?P<cepa>[^_]+)_(?P<replica>[^_]+)_(?P<condicion>.+)$")

log = logging.getLogger(__name__)


def _parse_filename(stem: str) -> dict[str, str]:
    m = _NAME_RE.match(stem)
    if m:
        return m.groupdict()
    return {"cepa": stem, "replica": "", "condicion": ""}


def _collect_images(input_dir: Path) -> list[Path]:
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED
    )


def _write_csv(rows: list[dict[str, str]], output_dir: Path) -> Path:
    path = output_dir / "results.csv"
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _process_image(
    image_path: Path,
    pipeline: object,
    panel_labels: list[str] | None,
) -> list[dict[str, str]]:
    from bacterioscope.pipeline import BacterioScopePipeline

    pl: BacterioScopePipeline = pipeline  # type: ignore[assignment]
    result = pl.analyze(image_path)

    if panel_labels is not None and len(panel_labels) == len(result.disks):
        result = pl.reclassify_with_labels(result, panel_labels)

    meta = _parse_filename(image_path.stem)
    rows = []
    for i, cls in enumerate(result.classifications):
        flags = result.flags[i] if i < len(result.flags) else []
        rows.append({
            "analysis_id": result.analysis_id,
            "software_version": result.software_version,
            "breakpoint_table_version": result.breakpoint_table_version,
            "image_sha256": result.image_sha256,
            "filename": image_path.name,
            "cepa": meta["cepa"],
            "replica": meta["replica"],
            "condicion": meta["condicion"],
            "disk_index": str(i + 1),
            "antibiotic": cls.antibiotic,
            "zone_mm": f"{cls.zone_diameter_mm:.1f}",
            "category": cls.category,
            "flags": "|".join(flags),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch-analyze Kirby-Bauer plate images.")
    parser.add_argument("input_dir", type=Path, metavar="INPUT_DIR",
                        help="Folder containing plate images.")
    parser.add_argument("--output-dir", "--output", "-o", required=True, type=Path,
                        dest="output_dir", metavar="OUTPUT_DIR")
    parser.add_argument("--panel", default=None,
                        help="Panel name for automatic antibiotic assignment.")
    parser.add_argument("--organism", default="Enterobacteriaceae")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(args.output_dir / "errors.log"),
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig
    pl = BacterioScopePipeline(PipelineConfig(organism_group=args.organism))

    panel_labels: list[str] | None = None
    if args.panel:
        from bacterioscope.panels.manager import PanelManager
        pm = PanelManager()
        panel_cfg = pm.load(args.panel)
        panel_labels = panel_cfg.antibiotics

    images = _collect_images(args.input_dir)
    if not images:
        print(f"No supported images found in {args.input_dir}", file=sys.stderr)
        return 1

    all_rows: list[dict[str, str]] = []
    timings_ms: list[float] = []
    disk_counts: list[int] = []
    errors = 0
    for img_path in images:
        t0 = time.perf_counter()
        try:
            rows = _process_image(img_path, pl, panel_labels)
            elapsed = (time.perf_counter() - t0) * 1000.0
            all_rows.extend(rows)
            timings_ms.append(elapsed)
            disk_counts.append(len(rows))
            print(f"  ok  {img_path.name} ({len(rows)} disks, {elapsed:.0f} ms)")
        except Exception as exc:
            log.warning("FAILED %s: %s", img_path.name, exc)
            print(f" ERR  {img_path.name}: {exc}", file=sys.stderr)
            errors += 1

    csv_path = _write_csv(all_rows, args.output_dir)
    n_ok = len(images) - errors
    print(f"\nResults written to {csv_path}")
    print(f"Processed: {n_ok}/{len(images)} images, {errors} failed.")
    if timings_ms:
        mean_ms = sum(timings_ms) / len(timings_ms)
        avg_disks = sum(disk_counts) / len(disk_counts)
        print(
            f"Timing: mean {mean_ms:.0f} ms/image, "
            f"min {min(timings_ms):.0f} ms, max {max(timings_ms):.0f} ms. "
            f"Avg disks/image: {avg_disks:.1f}."
        )
    if errors:
        print(f"Errors logged to {args.output_dir / 'errors.log'}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
