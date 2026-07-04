"""Evaluate the BacterioScope pipeline against labeled validation data.

Usage:
    python scripts/evaluate.py \\
        --images-dir data/validation \\
        --labels data/labels.csv \\
        --output docs/

CSV format (columns required):
    image,antibiotic,reference_diameter_mm,reference_category

    image                  -- filename or relative path inside images-dir
    antibiotic             -- antibiotic name matching CLSI table keys
    reference_diameter_mm  -- ground-truth zone diameter in mm
    reference_category     -- S, I, or R
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from bacterioscope.evaluation.metrics import collect_metrics
from bacterioscope.evaluation.report import save_report
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return name.lower().strip().replace(" ", "-")


def _load_labels(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"image", "antibiotic", "reference_diameter_mm", "reference_category"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must have columns: {required}")
        return list(reader)


def _match_result(
    analysis: AnalysisResult,
    antibiotic: str,
) -> tuple[str, float] | None:
    key = _normalize(antibiotic)
    for cls in analysis.classifications:
        if _normalize(cls.antibiotic) == key:
            return cls.category, cls.zone_diameter_mm
    return None


def _run_pipeline(
    images_dir: Path,
    rows: list[dict[str, str]],
    config: PipelineConfig,
) -> tuple[list[str], list[str], list[float], list[float]]:
    pipeline = BacterioScopePipeline(config)
    cache: dict[str, AnalysisResult] = {}

    pred_cats: list[str] = []
    ref_cats: list[str] = []
    meas_mm: list[float] = []
    ref_mm: list[float] = []

    for row in rows:
        image_path = images_dir / row["image"]
        key = str(image_path)

        if key not in cache:
            try:
                cache[key] = pipeline.analyze(image_path)
            except Exception as exc:
                log.warning("Skipping %s: %s", image_path.name, exc)
                continue

        match = _match_result(cache[key], row["antibiotic"])
        if match is None:
            log.warning(
                "Antibiotic %r not found in %s — row skipped.",
                row["antibiotic"],
                image_path.name,
            )
            continue

        pred_cat, measured = match
        if pred_cat not in ("S", "I", "R"):
            log.warning(
                "Antibiotic %r classified as %r (UNKNOWN) — row skipped.",
                row["antibiotic"],
                pred_cat,
            )
            continue

        pred_cats.append(pred_cat)
        ref_cats.append(row["reference_category"])
        meas_mm.append(measured)
        ref_mm.append(float(row["reference_diameter_mm"]))

    return pred_cats, ref_cats, meas_mm, ref_mm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--output", default=Path("docs"), type=Path)
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["markdown", "html"],
        choices=["markdown", "html"],
    )
    args = parser.parse_args()

    rows = _load_labels(args.labels)
    log.info("Loaded %d label rows from %s", len(rows), args.labels)

    pred, ref, meas, ref_d = _run_pipeline(args.images_dir, rows, PipelineConfig())

    if not pred:
        log.error("No matched results — cannot compute metrics.")
        return 1

    log.info("Matched %d isolate/antibiotic pairs.", len(pred))
    metrics = collect_metrics(pred, ref, meas, ref_d)
    paths = save_report(metrics, args.output, formats=args.formats)

    for path in paths:
        log.info("Report written: %s", path)

    ca = metrics["categorical_agreement"]
    er = metrics["error_rates"]
    log.info(
        "CA=%.1f%%  VME=%d (%.1f%%)  ME=%d (%.1f%%)",
        ca * 100,
        er["vme_count"], er["vme_rate"] * 100,
        er["me_count"], er["me_rate"] * 100,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
