"""Validate BacterioScope zone-diameter measurements against the UZH SIRscan reference.

Runs the pipeline (disk detection + zone segmentation) on a set of real plate images
and compares the measured zone diameters in mm against the SIRscan reference measurements
from the Dryad/UZH dataset.

IMPORTANT — scope of this validation
--------------------------------------
This script validates MEASUREMENT ACCURACY only (zone diameter in mm).
It does NOT validate S/I/R classification because:
  - The UZH reference uses EUCAST 2023 breakpoints (from SIRscan automated reader).
  - BacterioScope classifies using CLSI M100-Ed33 2023 breakpoints.
  - EUCAST and CLSI breakpoints differ for many antibiotic-organism combinations.
  - Comparing S/I/R categories across standards produces misleading error rates
    that reflect the standard difference, not system performance.

Full S/I/R validation against a CLSI-annotated reference is planned for Phase 3.

Matching strategy (Phase 0 limitation)
---------------------------------------
In Phase 0, the Hough-based detector cannot read the antibiotic label printed on each
disk.  Disks are matched to reference measurements by sorting both sets of diameters
ascending and pairing them by rank (see match_diameters_by_rank in metrics.py).
This is an approximation: it assumes the rank order of zone sizes is preserved between
the pipeline output and the reference.  Images where detected disk count differs from
the reference count are flagged and excluded from the EA calculation (logged to
failed_images.log).  Full per-antibiotic matching becomes possible in Phase 2 when
the YOLOv8 model reads disk labels.

Metrics reported
-----------------
  EA  — Essential Agreement: fraction of measurements within +-2 mm of reference.
         Target >= 90% (ISO 20776-2 / EUCAST EDef 13.2 criterion).
  MAE — Mean Absolute Error in mm.
  r   — Pearson correlation coefficient between measured and reference diameters.

Usage::

    python scripts/validate_measurement.py
    python scripts/validate_measurement.py --csv data/processed/ground_truth.csv
                                           --image-dir data/raw/dryad_uzh
                                           --output docs/figures
                                           --subset 50
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.detection.detector import DiskResult
from bacterioscope.evaluation.metrics import (
    match_diameters_by_rank,
    zone_diameter_stats,
)
from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig
from bacterioscope.segmentation.watershed import ZoneResult
from bacterioscope.utils.image import save_image

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_EA_MARGIN_MM = 2.0
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Validate zone-diameter measurement accuracy.")
    p.add_argument("--csv", type=Path, default=Path("data/processed/ground_truth.csv"),
                   help="Ground-truth CSV from prepare_dataset.py.")
    p.add_argument("--image-dir", type=Path, default=Path("data/raw/dryad_uzh"),
                   help="Directory containing plate images.")
    p.add_argument("--output", type=Path, default=Path("docs/figures"),
                   help="Directory for annotated output images.")
    p.add_argument("--report", type=Path, default=Path("docs/VALIDATION_REPORT.md"),
                   help="Output path for the Markdown validation report.")
    p.add_argument("--log-file", type=Path, default=Path("data/processed/failed_images.log"),
                   help="File to record images that could not be processed.")
    p.add_argument("--subset", type=int, default=0,
                   help="Limit to first N images (0 = all, useful for quick tests).")
    p.add_argument("--max-annotated", type=int, default=0,
                   help="Save at most N annotated images (0 = all). Minimum 5 recommended.")
    return p.parse_args()


def _load_ground_truth(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load ground truth CSV; return mapping of image_filename to list of reference rows."""
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Ground-truth CSV not found: {csv_path}\n"
            "Run python scripts/prepare_dataset.py first."
        )
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["image_filename"]].append(row)
    return dict(rows)


def _find_image(image_dir: Path, filename: str) -> Path | None:
    """Locate an image file, trying the exact name then stem-only match."""
    direct = image_dir / filename
    if direct.is_file():
        return direct
    stem = Path(filename).stem
    for suffix in _IMAGE_SUFFIXES:
        candidate = image_dir / (stem + suffix)
        if candidate.is_file():
            return candidate
    return None


def _annotate_with_reference(
    image: NDArray[np.uint8],
    disks: list[DiskResult],
    zones: list[ZoneResult],
    ref_mm_sorted: list[float],
) -> NDArray[np.uint8]:
    """Overlay reference zone diameters on a pipeline-annotated image.

    Pairs each disk to its reference diameter using the same ascending rank
    order as match_diameters_by_rank so labels align with the EA computation.

    Args:
        image: BGR annotated image from pipeline.draw_results().
        disks: Detected disk results in pipeline order.
        zones: Zone results in the same order as disks.
        ref_mm_sorted: Reference diameters sorted ascending.

    Returns:
        Copy of image with cyan reference labels drawn above each disk.
    """
    overlay = image.copy()
    ranked = sorted(zip(disks, zones), key=lambda p: p[1].diameter_mm)
    for (disk, zone), ref in zip(ranked, ref_mm_sorted):
        label = f"ref:{ref:.0f}mm"
        cv2.putText(
            overlay, label,
            (disk.center_x - 22, disk.center_y - disk.radius_px - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA,
        )
    return overlay


def _run_image(
    image_path: Path,
    ref_rows: list[dict[str, str]],
    pipeline: BacterioScopePipeline,
    output_dir: Path,
    save_annotated: bool = True,
) -> tuple[list[float], list[float], bool]:
    """Run pipeline on one image and return (measured_mm, reference_mm, count_ok).

    Saves an annotated image to output_dir when save_annotated is True.
    When disk counts match, the annotated image includes reference diameter
    labels drawn via _annotate_with_reference.
    Returns empty lists and False when disk count mismatches or pipeline fails.
    """
    result = pipeline.analyze(str(image_path))
    measured_mm = [z.diameter_mm for z in result.zones if z.diameter_mm > 0]
    ref_mm = [float(r["zone_diameter_mm_ref"]) for r in ref_rows]
    count_ok = len(measured_mm) == len(ref_mm)

    if save_annotated and result.annotated_image is not None:
        img: NDArray[np.uint8] = (
            _annotate_with_reference(
                result.annotated_image, result.disks, result.zones, sorted(ref_mm)
            )
            if count_ok
            else result.annotated_image
        )
        save_image(img, output_dir / f"annotated_{image_path.stem}.jpg")

    if not count_ok:
        log.warning(
            "%s: detected %d disks, reference has %d — excluding from EA.",
            image_path.name, len(measured_mm), len(ref_mm),
        )
        return [], [], False

    pairs = match_diameters_by_rank(measured_mm, ref_mm)
    return [p[0] for p in pairs], [p[1] for p in pairs], True


def _write_failure_log(log_path: Path, failures: list[str]) -> None:
    """Write the list of failed/mismatched image names to a log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(failures) + "\n", encoding="utf-8")


def _write_report(
    report_path: Path,
    n_images_total: int,
    n_images_matched: int,
    n_pairs: int,
    failures: list[str],
    ea: float,
    mae: float,
    pearson_r: float,
) -> None:
    """Write the Markdown validation report, replacing all pending placeholders."""
    lines = [
        "# BacterioScope Validation Report",
        "",
        "> Dataset: Egli et al. (2023) / University of Zurich SIRscan.",
        "> doi:10.5061/dryad.5dv41nsfj",
        "",
        "## Scope and limitations",
        "",
        "This report validates **zone-diameter measurement accuracy only** "
        "(mm vs SIRscan reference).",
        "S/I/R classification is **not** compared because:",
        "",
        "- The UZH reference uses **EUCAST 2023** breakpoints (SIRscan automated reader).",
        "- BacterioScope classifies using **CLSI M100-Ed33 2023** breakpoints.",
        "- EUCAST and CLSI thresholds differ for many antibiotic-organism combinations "
        "(e.g. ciprofloxacin S: EUCAST >= 25 mm vs CLSI >= 26 mm for Enterobacteriaceae).",
        "- Comparing S/I/R across standards produces misleading discordance rates.",
        "",
        "Full S/I/R validation against a CLSI-annotated reference is planned for Phase 3.",
        "",
        "### Matching strategy — Phase 0 limitation",
        "",
        "Disks are matched to reference measurements by **rank-order pairing** "
        "(both sets sorted ascending by diameter). "
        "This is an approximation valid when zone-size rank order is consistent across images. "
        "Full per-antibiotic matching requires Phase 2 (YOLOv8 label reading).",
        "",
        "## Dataset summary",
        "",
        "| Item | Value |",
        "|---|---|",
        "| Dataset | University of Zurich SIRscan (Egli et al., 2023) |",
        "| Reference system | SIRscan automated reader (EUCAST 2023) |",
        f"| Total images evaluated | {n_images_total} |",
        f"| Images with matching disk count | {n_images_matched} |",
        f"| Disk-antibiotic pairs used for EA | {n_pairs} |",
        f"| Images excluded (disk count mismatch or error) | {len(failures)} |",
        "",
        "## Measurement accuracy",
        "",
        "| Metric | Value | Target | Criterion |",
        "|---|---|---|---|",
        f"| Essential Agreement (EA, +-2 mm) | **{ea:.1%}** | >= 90% | "
        "ISO 20776-2 / EUCAST EDef 13.2 |",
        f"| Mean Absolute Error (MAE) | **{mae:.2f} mm** | — | mm |",
        f"| Pearson r | **{pearson_r:.3f}** | — | — |",
        "",
        "### Definition of Essential Agreement used here",
        "",
        "Classical EA (ISO 20776-2) is defined for MIC broth microdilution: "
        "the test-system MIC must fall within one two-fold dilution of the reference MIC. "
        "BacterioScope measures zone diameters in mm, not MIC values. "
        "EA is **adapted** as the fraction of diameter measurements within **+-2 mm** of the "
        "SIRscan reference, consistent with EUCAST EDef 13.2 inter-laboratory reproducibility. "
        "This adaptation must be disclosed when comparing to ISO 20776-2 EA figures.",
        "",
        "## Excluded images",
        "",
    ]
    if failures:
        lines.append(
            f"{len(failures)} image(s) were excluded from EA: "
            "disk count mismatch between pipeline and reference, or pipeline error."
        )
        lines.append("")
        for f in failures[:20]:
            lines.append(f"- {f}")
        if len(failures) > 20:
            lines.append(f"- ... and {len(failures) - 20} more (see failed_images.log)")
    else:
        lines.append("None — all images had matching disk counts.")
    lines += [
        "",
        "## Annotated examples",
        "",
        "Annotated plate images with detected halos (pipeline) and reference diameter "
        "labels (cyan) are saved in `docs/figures/`. "
        "Reference labels show the SIRscan measurement for each disk, paired by rank order.",
        "",
        "## How to reproduce",
        "",
        "```bash",
        "python scripts/download_data.py       # follow manual download prompt",
        "python scripts/prepare_dataset.py     # normalise CSV",
        "python scripts/validate_measurement.py  # compute EA / MAE / Pearson r",
        "# Quick subset (first 20 images):",
        "python scripts/validate_measurement.py --subset 20",
        "```",
        "",
        "Failures are logged to `data/processed/failed_images.log`.",
        "",
        "## Citation",
        "",
        "> Egli A, Imkamp F, Amlang G, Brunner S, Albrich W, et al. (2023).",
        "> *Automated reading of disk diffusion antibiograms.*",
        "> Dataset on Dryad Digital Repository.",
        "> https://doi.org/10.5061/dryad.5dv41nsfj",
        "> License: CC0 1.0 Universal.",
        "",
        "---",
        "",
        "*This report is generated automatically by `scripts/validate_measurement.py`.*",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Entry point for measurement validation."""
    args = _parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        ground_truth = _load_ground_truth(args.csv)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)

    filenames = sorted(ground_truth.keys())
    if args.subset > 0:
        filenames = filenames[: args.subset]
        log.info("Subset mode: evaluating %d of %d images.", args.subset, len(ground_truth))

    pipeline = BacterioScopePipeline(PipelineConfig())

    all_measured: list[float] = []
    all_reference: list[float] = []
    failures: list[str] = []
    n_matched = 0
    n_annotated = 0

    for filename in filenames:
        img_path = _find_image(args.image_dir, filename)
        if img_path is None:
            log.warning("Image not found: %s", filename)
            failures.append(f"{filename} — file not found")
            continue
        save = args.max_annotated == 0 or n_annotated < args.max_annotated
        try:
            m_mm, r_mm, count_ok = _run_image(
                img_path, ground_truth[filename], pipeline, args.output,
                save_annotated=save,
            )
        except Exception as exc:
            log.warning("Pipeline failed on %s: %s", filename, exc)
            failures.append(f"{filename} — pipeline error: {type(exc).__name__}: {exc}")
            continue
        if not count_ok:
            failures.append(f"{filename} — disk count mismatch")
            continue
        all_measured.extend(m_mm)
        all_reference.extend(r_mm)
        n_matched += 1
        if save:
            n_annotated += 1

    log.info(
        "Results: %d/%d images matched, %d excluded, %d annotated images saved.",
        n_matched, len(filenames), len(failures), n_annotated,
    )

    _write_failure_log(args.log_file, failures)

    if len(all_measured) < 2:
        log.error("Not enough matched pairs to compute metrics (got %d).", len(all_measured))
        sys.exit(1)

    meas_arr = np.asarray(all_measured)
    ref_arr = np.asarray(all_reference)
    ea = float(np.mean(np.abs(meas_arr - ref_arr) <= _EA_MARGIN_MM))
    stats = zone_diameter_stats(all_measured, all_reference)
    mae = stats["mae_mm"]
    r = stats["pearson_r"]

    log.info("EA (+-2 mm): %.1f%%", ea * 100)
    log.info("MAE: %.2f mm", mae)
    log.info("Pearson r: %.3f", r)

    _write_report(
        args.report,
        n_images_total=len(filenames),
        n_images_matched=n_matched,
        n_pairs=len(all_measured),
        failures=failures,
        ea=ea,
        mae=mae,
        pearson_r=r,
    )
    log.info("Report written: %s", args.report)


if __name__ == "__main__":
    main()
