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
                                           --output data/processed/validation_figures
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
_PAIR_ANNOTATIONS_DIR = Path("data/processed/pair_annotations")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Validate zone-diameter measurement accuracy.")
    p.add_argument("--csv", type=Path, default=Path("data/processed/ground_truth.csv"),
                   help="Ground-truth CSV from prepare_dataset.py.")
    p.add_argument("--image-dir", type=Path, default=Path("data/raw/dryad_uzh"),
                   help="Directory containing plate images.")
    p.add_argument("--output", type=Path, default=Path("data/processed/validation_figures"),
                   help="Directory for annotated output images.")
    p.add_argument("--report", type=Path, default=Path("docs/VALIDATION_REPORT.md"),
                   help="Output path for the Markdown validation report.")
    p.add_argument("--log-file", type=Path, default=Path("data/processed/failed_images.log"),
                   help="File to record images that could not be processed.")
    p.add_argument("--subset", type=int, default=0,
                   help="Limit to first N images (0 = all, useful for quick tests).")
    p.add_argument("--max-annotated", type=int, default=0,
                   help="Save at most N annotated images (0 = all). Minimum 5 recommended.")
    p.add_argument("--disk-calibration", action="store_true",
                   help="Use disk-diameter calibration (Phase 3) instead of plate-rim calibration.")
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


def _load_identity_pairs(pairs_dir: Path, image_filename: str) -> dict[int, str] | None:
    """Load a human-verified disk-index -> antibiotic-code mapping, if it exists.

    Produced by ``scripts/annotate_pairs.py``. Rank-order pairing assumes zone
    size ordering matches between pipeline and reference, which is not
    guaranteed on real photos; identity pairing removes that assumption for
    the subset of images that have been manually annotated.

    Args:
        pairs_dir: Directory containing ``<stem>_pairs.csv`` files.
        image_filename: Ground-truth CSV image filename (e.g. "1.1.1. original.jpg").

    Returns:
        ``{disk_index: antibiotic_code}`` for rows with a non-empty code, or
        ``None`` if no annotation file exists for this image.
    """
    pairs_path = pairs_dir / f"{Path(image_filename).stem}_pairs.csv"
    if not pairs_path.is_file():
        return None
    mapping: dict[int, str] = {}
    with pairs_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = row["antibiotic_code"].strip()
            if code:
                mapping[int(row["disk_index"])] = code
    return mapping or None


def _match_by_identity(
    zones: list[ZoneResult],
    ref_rows: list[dict[str, str]],
    identity_map: dict[int, str],
) -> list[tuple[float, float]]:
    """Pair measured zone diameters to reference rows by antibiotic code.

    Args:
        zones: Zone results in ``DiskDetector.detect()`` order (same order
            ``annotate_pairs.py`` used to assign ``disk_index``).
        ref_rows: Ground-truth rows for this image.
        identity_map: ``{disk_index: antibiotic_code}`` from ``_load_identity_pairs``.

    Returns:
        List of ``(measured_mm, reference_mm)`` tuples for disks whose code
        matched a reference row. Silently skips codes with no reference match.
    """
    ref_by_code = {r["antibiotic_code"]: float(r["zone_diameter_mm_ref"]) for r in ref_rows}
    pairs: list[tuple[float, float]] = []
    for disk_index, code in identity_map.items():
        if disk_index >= len(zones) or code not in ref_by_code:
            continue
        pairs.append((zones[disk_index].diameter_mm, ref_by_code[code]))
    return pairs


def _find_image(image_dir: Path, filename: str) -> Path | None:
    """Locate an image file by exact name, stem match, or recursive search."""
    direct = image_dir / filename
    if direct.is_file():
        return direct
    stem = Path(filename).stem
    for suffix in _IMAGE_SUFFIXES:
        candidate = image_dir / (stem + suffix)
        if candidate.is_file():
            return candidate
    matches = list(image_dir.rglob(filename))
    return matches[0] if matches else None


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
    pairs_dir: Path = _PAIR_ANNOTATIONS_DIR,
) -> tuple[list[float], list[float], bool, list[tuple[float, float]]]:
    """Run pipeline on one image and return rank pairs plus any identity pairs.

    Saves an annotated image to output_dir when save_annotated is True.
    When disk counts match, the annotated image includes reference diameter
    labels drawn via _annotate_with_reference.
    Returns empty rank lists and False when disk count mismatches or pipeline fails,
    but still checks for identity pairs (those do not depend on disk count matching).

    Returns:
        ``(measured_mm, reference_mm, count_ok, identity_pairs)`` where the
        first three describe rank-order matching and ``identity_pairs`` is a
        list of ``(measured_mm, reference_mm)`` from human-verified disk
        identity, independent of ``count_ok``.
    """
    result = pipeline.analyze(str(image_path))
    measured_mm = [z.diameter_mm for z in result.zones if z.diameter_mm > 0]
    ref_mm = [float(r["zone_diameter_mm_ref"]) for r in ref_rows]
    count_ok = len(measured_mm) == len(ref_mm)

    identity_map = _load_identity_pairs(pairs_dir, image_path.name)
    identity_pairs = (
        _match_by_identity(result.zones, ref_rows, identity_map) if identity_map else []
    )

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
        return [], [], False, identity_pairs

    pairs = match_diameters_by_rank(measured_mm, ref_mm)
    return [p[0] for p in pairs], [p[1] for p in pairs], True, identity_pairs


def _bland_altman_stats(
    measured: list[float],
    reference: list[float],
) -> dict[str, float]:
    """Compute Bland-Altman limits of agreement for zone-diameter pairs.

    Args:
        measured: Pipeline zone diameters in mm.
        reference: Reference zone diameters in mm.

    Returns:
        Dict with keys: mean_diff_mm, sd_diff_mm, loa_upper_mm, loa_lower_mm, n_pairs.
    """
    m_arr = np.asarray(measured)
    r_arr = np.asarray(reference)
    diff = m_arr - r_arr
    mean_diff = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1))
    return {
        "mean_diff_mm": mean_diff,
        "sd_diff_mm": sd_diff,
        "loa_upper_mm": mean_diff + 1.96 * sd_diff,
        "loa_lower_mm": mean_diff - 1.96 * sd_diff,
        "n_pairs": float(len(m_arr)),
    }


def _save_scatter_plot(
    measured: list[float],
    reference: list[float],
    output_dir: Path,
) -> None:
    """Save a measured vs reference scatter plot (requires matplotlib)."""
    import matplotlib.pyplot as plt  # noqa: PLC0415
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(reference, measured, alpha=0.4, s=20)
    lim = [min(reference + measured) - 2.0, max(reference + measured) + 2.0]
    ax.plot(lim, lim, "k--", lw=1, label="Identity")
    ax.set_xlabel("Reference — SIRscan (mm)")
    ax.set_ylabel("BacterioScope (mm)")
    ax.set_title("Measured vs Reference Zone Diameters")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "scatter_measured_vs_reference.png", dpi=120)
    plt.close(fig)


def _save_bland_altman_plot(
    measured: list[float],
    reference: list[float],
    output_dir: Path,
) -> None:
    """Save a Bland-Altman difference plot (requires matplotlib)."""
    import matplotlib.pyplot as plt  # noqa: PLC0415
    ba = _bland_altman_stats(measured, reference)
    m_arr = np.asarray(measured)
    r_arr = np.asarray(reference)
    mean_pair = (m_arr + r_arr) / 2.0
    diff = m_arr - r_arr
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(mean_pair, diff, alpha=0.4, s=20)
    ax.axhline(ba["mean_diff_mm"], color="k", ls="--", lw=1,
               label=f"Bias {ba['mean_diff_mm']:.2f} mm")
    ax.axhline(ba["loa_upper_mm"], color="r", ls=":", lw=1,
               label=f"+1.96SD {ba['loa_upper_mm']:.2f} mm")
    ax.axhline(ba["loa_lower_mm"], color="r", ls=":", lw=1,
               label=f"-1.96SD {ba['loa_lower_mm']:.2f} mm")
    ax.set_xlabel("Mean of (BacterioScope + Reference) / 2 (mm)")
    ax.set_ylabel("BacterioScope − Reference (mm)")
    ax.set_title("Bland-Altman Plot")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "bland_altman.png", dpi=120)
    plt.close(fig)


def _try_save_plots(
    measured: list[float],
    reference: list[float],
    output_dir: Path,
) -> None:
    """Attempt to save scatter and Bland-Altman plots; skip gracefully if matplotlib absent."""
    try:
        _save_scatter_plot(measured, reference, output_dir)
        _save_bland_altman_plot(measured, reference, output_dir)
        log.info("Plots saved to %s", output_dir)
    except ImportError:
        log.info("matplotlib not installed — skipping plot generation.")


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
    ba: dict[str, float] | None = None,
    identity_stats: dict[str, float] | None = None,
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
        "### Matching strategy",
        "",
        "Two strategies are reported, clearly separated below: **identity matching** "
        "(each disk paired to its reference by the antibiotic printed on it, "
        "human-verified) where annotation exists, and **rank-order pairing** "
        "(both sets sorted ascending and paired by position) everywhere else. "
        "Rank-order pairing does not verify that the same physical disk is "
        "being compared and is reported only as an optimistic upper bound, "
        "never as the project's accuracy figure. Automatic per-antibiotic "
        "matching without manual annotation requires Phase 2 (YOLOv8 label "
        "reading) at a confidence level that is not yet reliable.",
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
    ]
    if identity_stats:
        lines += [
            "### Identity-matched — the real number",
            "",
            "Each disk matched to its reference by antibiotic identity "
            "(human-verified from the printed disk label), not by sorted rank. "
            "This is the defensible accuracy figure for the project.",
            "",
            "| Metric | Value | Target |",
            "|---|---|---|",
            f"| Essential Agreement (EA, +-2 mm) | **{identity_stats['ea']:.1%}** | >= 90% |",
            f"| Mean Absolute Error (MAE) | **{identity_stats['mae']:.2f} mm** | — |",
            f"| Pearson r | **{identity_stats['pearson_r']:.3f}** | — |",
            f"| Images identity-annotated | {int(identity_stats['n_images'])} |",
            f"| Disk-antibiotic pairs (identity) | {int(identity_stats['n_pairs'])} |",
            "",
            "Annotate more images with `python scripts/annotate_pairs.py --batch "
            "data/raw/dryad_uzh/images_original --limit N` to grow this sample; "
            "20-30 images gives a reasonably stable estimate.",
            "",
        ]
    else:
        lines += [
            "### Identity-matched — not yet available",
            "",
            "No images have been identity-annotated yet. Run "
            "`python scripts/annotate_pairs.py --batch <dir>` and fill in the "
            "generated `*_pairs.csv` files, then re-run this script.",
            "",
        ]
    lines += [
        "### Rank-order pairing — optimistic upper bound, not a measurement",
        "",
        "Both diameter lists sorted ascending and paired by position. This does "
        "not verify that the same physical disk is being compared, and "
        "inflates agreement whenever measurement error does not reorder the "
        "list — do not report this as the project's accuracy figure.",
        "",
        "| Metric | Value | Target | Criterion |",
        "|---|---|---|---|",
        f"| Essential Agreement (EA, +-2 mm) | **{ea:.1%}** | >= 90% | "
        "ISO 20776-2 / EUCAST EDef 13.2 |",
        f"| Mean Absolute Error (MAE) | **{mae:.2f} mm** | — | mm |",
        f"| Pearson r | **{pearson_r:.3f}** | — | — |",
        "",
        "### Bland-Altman limits of agreement (rank-order pairs)",
        "",
    ]
    if ba:
        lines += [
            "| Stat | Value |",
            "|---|---|",
            f"| Bias (mean diff) | {ba['mean_diff_mm']:+.2f} mm |",
            f"| SD of differences | {ba['sd_diff_mm']:.2f} mm |",
            f"| Upper LoA (+1.96 SD) | {ba['loa_upper_mm']:+.2f} mm |",
            f"| Lower LoA (−1.96 SD) | {ba['loa_lower_mm']:+.2f} mm |",
            f"| Pairs analysed | {int(ba['n_pairs'])} |",
            "",
        ]
    else:
        lines.append("Insufficient data for Bland-Altman analysis.")
        lines.append("")
    lines += [
        "### Definition of Essential Agreement used here",
        "",
        "Classical EA (ISO 20776-2) is defined for MIC broth microdilution: "
        "the test-system MIC must fall within one two-fold dilution of the reference MIC. "
        "BacterioScope measures zone diameters in mm, not MIC values. "
        "EA is **adapted** as the fraction of diameter measurements within **+-2 mm** of the "
        "SIRscan reference, consistent with EUCAST EDef 13.2 inter-laboratory reproducibility. "
        "This adaptation must be disclosed when comparing to ISO 20776-2 EA figures.",
        "",
        "## Diagnostic findings (this validation round)",
        "",
        "A first identity-matched validation pass surfaced a structural problem "
        "beyond calibration or detection: on real UZH plates (16 disks packed "
        "onto one 90mm plate with confluent, overlapping inhibition zones), "
        "measured zone diameters clustered tightly regardless of which "
        "antibiotic the disk carried -- the segmenter was measuring the same "
        "shared confluent blob for every disk, not 16 different biological "
        "responses.",
        "",
        "### What was tried on segmentation, and what actually worked",
        "",
        "`ZoneSegmenter.segment_all()` now segments every disk in the context "
        "of its neighbours rather than in isolation. Three approaches were "
        "attempted, in order:",
        "",
        "1. **Marker-based watershed flooding on the raw photo.** Standard "
        "textbook approach, but real-photo texture (agar surface, printed "
        "disk labels, JPEG noise) creates false local ridges everywhere, so "
        "flooding barely left each seed -- every zone collapsed to roughly "
        "the seed's own size. Discarded.",
        "2. **Watershed on a distance-transform elevation.** Removes the "
        "texture-noise problem, but on real (noisy, irregularly-shaped) "
        "masks the saddle points between confluent zones were themselves "
        "unreliable, and an edge disk with more open unclaimed territory "
        "could inherit a physically impossible region (one measurement hit "
        "117mm on a 90mm plate). Discarded.",
        "3. **Voronoi partition: each pixel assigned to its geometrically "
        "nearest disk centre.** Deterministic, independent of image noise. "
        "**Verified correct on a controlled case**: two disks with "
        "deliberately different true zone sizes (80px and 40px radius, "
        "overlapping) were recovered as 40mm and 20mm respectively -- exact. "
        "This is the shipped implementation.",
        "",
        "The Voronoi split is real and tested (see "
        "`tests/test_watershed.py::TestSegmentAllVoronoiSplit`), but it did "
        "not meaningfully move the real-photo numbers below, and the reason "
        "is itself a finding, not an implementation gap: **for several "
        "adjacent disk pairs on the densest UZH plates, the raw pixel "
        "intensity between them is completely flat**, measured directly "
        "(no rise, no dip, ~70-90 vs ~70-90 across the entire gap between "
        "two specific disks checked by hand). When two zones are that fully "
        "confluent, there is no boundary left in the photograph for *any* "
        "algorithm to recover -- a human reading the same photo by eye faces "
        "exactly the same ambiguity. Voronoi still gives each disk a "
        "geometrically fair, bounded region instead of one shared blob "
        "reaching across the whole plate, which is real progress on plates "
        "with partial (not total) overlap; it cannot manufacture information "
        "a fully confluent photograph never captured.",
        "",
        "Two other fixes landed this round, with a measurable before/after:",
        "",
        "| Fix | Before | After |",
        "|---|---|---|",
        "| Hough disk radius: fixed pixel range vs calibration-derived window "
        "(detector.py) | Median disk read as 6mm=~7.7mm (+28% bias); wild "
        "over-detection (100-217 false circles) on several images | "
        "Systematic bias much smaller (~-15 to -20% on clean detections); "
        "false-circle storms eliminated |",
        "| Confidence threshold: 0.04 (post-hoc lowered to force a "
        "29-class model to emit something) vs 0.25 (defensible floor) | "
        "A single ~0.05-confidence YOLO false positive could pre-empt 16 "
        "reliable Hough detections (hybrid fallback only tries Hough when "
        "YOLO returns nothing) | Images with correct disk count: 24/80 -> "
        "70/80 |",
        "",
        "What this means for the headline numbers: rank-order EA moved from "
        "32.8% to 26.9% across this round -- a *drop*, not an improvement, "
        "because the fixed detector now processes far more of the previously-"
        "excluded difficult images instead of silently failing on them. Fewer "
        "images being thrown out is progress even though the visible EA number "
        "went down; it is a more honest measurement over a harder, more "
        "complete sample, not a regression.",
        "",
        "### The disk itself was polluting Otsu's threshold selection",
        "",
        "A later round found a second, structural segmentation bug, unrelated "
        "to confluence: on many real UZH photos, every disk's zone mask "
        "filled essentially 100% of its crop's bounding box, *including on "
        "sparse 4-disk plates with no neighbour anywhere near* -- ruling out "
        "confluence or crop size as the cause (growing the crop measurably "
        "made it worse, not better, jumping to 45-50mm on a ~90mm plate). "
        "Direct pixel measurement found the real cause: the paper disk "
        "itself (bright, ~150-200) is almost always a far stronger "
        "bright/dark signal than the actual zone-vs-lawn contrast, "
        "sometimes as little as 15 grey levels apart on real photos. Otsu, "
        "run over the whole crop, reliably locks onto disk-vs-everything "
        "instead of zone-vs-lawn -- confirmed directly: a between-class-"
        "variance quality score computed the same way Otsu picks its "
        "threshold was *highest* (0.91-0.92) on exactly the real photos "
        "whose masks filled 100% of their crop, because that score was "
        "measuring the disk/background split, not zone/lawn.",
        "",
        "Fixed by excluding the disk's own area from Otsu's histogram "
        "before computing the threshold (`ZoneSegmenter._otsu_excluding_"
        "disk()`), so Otsu only ever sees the zone-vs-lawn contrast that is "
        "actually being measured. This is a real, measured improvement, not "
        "a reparameterization: on a controlled synthetic case with a "
        "15-grey-level zone-vs-lawn gap, the old (disk-included) threshold "
        "measured a 70px true zone as 168px; the fix measured it as 70px, "
        "exact. On the real 20-image identity-matched set this round, EA "
        "moved from 24.1% to 32.9%, MAE from 7.44mm to 6.28mm, and Pearson "
        "r from 0.089 to 0.193 -- real progress, still well short of the "
        "90% EA target.",
        "",
        "### Disk-based calibration was never independent of plate-rim calibration",
        "",
        "`use_disk_calibration` (Phase 3) was investigated directly rather "
        "than left as an open question. It was not measuring the disk "
        "independently at all: `pipeline.analyze()` calls `detector.detect"
        "(image, px_per_mm=px_per_mm_rim)` *before* disk calibration runs, "
        "and Hough's disk-radius search window is derived from that same "
        "plate-rim estimate. The reported disk radius was therefore "
        "plate-rim calibration scaled by whatever Hough voted for inside a "
        "window centred on that same estimate -- confirmed directly: "
        "across 20 real photos the resulting ratio was a suspiciously "
        "tight ~0.80x, far too consistent to be an independent physical "
        "measurement.",
        "",
        "Fixed with `calibration.py::refine_disk_radius_px()`: a local, "
        "calibration-independent Otsu threshold re-measures each disk's "
        "true edge directly in a small crop around its detected centre. "
        "This closed most of the gap on the 20-image identity-matched set "
        "(EA 14.9% -> 28.8%, MAE 8.88mm -> 7.42mm) -- real progress on a "
        "real bug. But disk calibration still trails plate-rim calibration "
        "(32.9% EA, 6.28mm MAE) even once measured correctly, and this "
        "remaining gap is not a bug: it is reference size. The plate rim "
        "spans roughly 550-600px in a canonical-resized image; a disk "
        "spans roughly 50-60px. The same few pixels of edge-detection "
        "noise are a far larger *relative* error against the smaller "
        "reference. `use_disk_calibration` stays `False` by default.",
        "",
        "## Still unresolved",
        "",
        "- **Zone segmentation on fully confluent real plates** (above). "
        "Voronoi splitting is implemented, tested, and verified correct when "
        "some boundary signal exists; it cannot help where the photograph "
        "itself has none. The 16-disk-dense UZH panel is a worst case for "
        "this -- a clinical panel with normal CLSI disk spacing (6-12 disks, "
        "properly separated) should confluence far less often, but this has "
        "not yet been measured directly.",
        "- **Identity-annotated sample grew from 3 to 20 images** (48 to 316 "
        "pairs), reaching the stable-estimate range this file itself called "
        "for. Going from 3 to 20 images changed Pearson r from -0.262 to "
        "+0.089 -- the earlier negative correlation was small-sample noise, "
        "not a real effect. The position-to-antibiotic mapping used to "
        "identity-annotate the 17 new images was derived from the fixed "
        "panel template shared by the first 3 (verified by direct visual "
        "reading of the printed disk labels on several images per template "
        "variant before applying it), not re-read label by label on every "
        "image -- documented here so the provenance is explicit.",
        "- **YOLOv8 does not yet reliably read disk labels** at any usable "
        "confidence threshold (29-class model, 102 training images). A "
        "single-class 'disk' detector trained on the same images reaches "
        "mAP50=0.995 on its own held-out test split (see Phase 2 status in "
        "docs/ROADMAP.md / CLAUDE.md) but is **not** a proven replacement "
        "for Hough localisation despite that score: measured directly "
        "against the 80 real UZH photos this report evaluates, Hough "
        "matches the true disk count on 73.8% of images versus 60.0% for "
        "the single-class model -- a domain-gap effect, the 102 Roboflow "
        "training images do not resemble this dataset's photography closely "
        "enough. Hough stays the pipeline's real default. Disk *identity* "
        "still resolves through panel position, not label reading, either "
        "way.",
        "- **EA is well below the ISO 20776-2 / EUCAST EDef 13.2 target of "
        "90%** on both matching strategies. State plainly: BacterioScope does "
        "not yet meet the accuracy bar for real, unconstrained clinical "
        "photographs. It performs acceptably on synthetic and controlled "
        "images; real-photo accuracy is an open problem this report exists "
        "to make visible, not to paper over.",
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
        "labels (cyan) are saved in `data/processed/validation_figures/`. "
        "Reference labels show the SIRscan measurement for each disk, paired by rank order.",
        "",
        "## How to reproduce",
        "",
        "```bash",
        "python scripts/download_data.py       # follow manual download prompt",
        "python scripts/prepare_dataset.py     # normalise CSV",
        "# Optional but recommended: identity-annotate a sample so EA/MAE/r",
        "# are a real measurement, not a rank-order upper bound.",
        "python scripts/annotate_pairs.py --batch data/raw/dryad_uzh/images_original --limit 20",
        "# ... fill in the generated *_pairs.csv files, then:",
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

    pipeline = BacterioScopePipeline(PipelineConfig(use_disk_calibration=args.disk_calibration))

    all_measured: list[float] = []
    all_reference: list[float] = []
    identity_measured: list[float] = []
    identity_reference: list[float] = []
    n_identity_images = 0
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
            m_mm, r_mm, count_ok, id_pairs = _run_image(
                img_path, ground_truth[filename], pipeline, args.output,
                save_annotated=save,
            )
        except Exception as exc:
            log.warning("Pipeline failed on %s: %s", filename, exc)
            failures.append(f"{filename} — pipeline error: {type(exc).__name__}: {exc}")
            continue
        if id_pairs:
            identity_measured.extend(p[0] for p in id_pairs)
            identity_reference.extend(p[1] for p in id_pairs)
            n_identity_images += 1
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
        log.error(
            "Ensure the dataset is prepared: python scripts/prepare_dataset.py"
        )
        sys.exit(1)

    meas_arr = np.asarray(all_measured)
    ref_arr = np.asarray(all_reference)
    ea = float(np.mean(np.abs(meas_arr - ref_arr) <= _EA_MARGIN_MM))
    diam_stats = zone_diameter_stats(all_measured, all_reference)
    mae = diam_stats["mae_mm"]
    r = diam_stats["pearson_r"]
    ba = _bland_altman_stats(all_measured, all_reference)

    log.info("EA (+-2 mm): %.1f%%", ea * 100)
    log.info("MAE: %.2f mm", mae)
    log.info("Pearson r: %.3f", r)
    log.info(
        "Bland-Altman: bias=%.2f mm  LoA [%.2f, %.2f]",
        ba["mean_diff_mm"], ba["loa_lower_mm"], ba["loa_upper_mm"],
    )

    identity_stats = None
    if len(identity_measured) >= 2:
        id_meas_arr = np.asarray(identity_measured)
        id_ref_arr = np.asarray(identity_reference)
        identity_stats = {
            "n_images": n_identity_images,
            "n_pairs": len(identity_measured),
            "ea": float(np.mean(np.abs(id_meas_arr - id_ref_arr) <= _EA_MARGIN_MM)),
            "mae": zone_diameter_stats(identity_measured, identity_reference)["mae_mm"],
            "pearson_r": zone_diameter_stats(identity_measured, identity_reference)["pearson_r"],
        }
        log.info(
            "Identity-matched (%d images, %d pairs): EA=%.1f%% MAE=%.2fmm r=%.3f",
            identity_stats["n_images"], identity_stats["n_pairs"],
            identity_stats["ea"] * 100, identity_stats["mae"], identity_stats["pearson_r"],
        )

    _try_save_plots(all_measured, all_reference, args.output)
    _write_report(
        args.report,
        n_images_total=len(filenames),
        n_images_matched=n_matched,
        n_pairs=len(all_measured),
        failures=failures,
        ea=ea,
        mae=mae,
        pearson_r=r,
        ba=ba,
        identity_stats=identity_stats,
    )
    log.info("Report written: %s", args.report)


if __name__ == "__main__":
    main()
