"""Survey real plate images for a single defensible pitch-ready measurement.

Runs the pipeline, as committed, on every image in ``examples/real/`` and the
first 20 UZH images (the same 20 already identity-annotated in Phase 1), and
ranks each detected disk by whether its measured contour is a real biological
edge or an artifact of the search crop's own boundary. No pipeline parameter
is touched here -- this only surveys what the shipped pipeline already
produces.

A disk's zone mask filling nearly all of its own crop's bounding box is the
confirmed signature (this project's Phase 3 findings) of measuring the crop
edge, not a real inhibition-zone edge. Combined with the existing quality
flags (``overlap``, ``low_circularity``, ``boundary``, ``small_zone``,
``crop_boundary``), this gives a per-disk trust classification without
inventing a new metric.

Two separate bars are reported, on purpose, not one:

- ``is_trustworthy`` (fill ratio < 0.90, no flags) matches the pipeline's own
  ``crop_boundary`` flag -- validated statistically (measured EA improves
  from 32.9% to 42.8% on the kept set, see ``measure_confidence_indicator.py``).
  This answers "should this specific measurement be trusted scientifically".
- ``is_presentable`` (fill ratio < 0.80, no flags) is a visibly stricter bar
  for a different question: "will this look like a clean biological contour
  on a slide, not a square". Found necessary directly: several disks that
  pass the 0.90 trust bar (fill ratio in the high 0.80s) still show a
  visibly square contour in the annotated output. Conflating the two bars
  previously led to recommending images that were statistically defensible
  but not visually presentable -- do not collapse them back into one number.

Usage::

    python scripts/survey_pitch_images.py
    python scripts/survey_pitch_images.py --output-dir data/processed/pitch_candidates
"""

from __future__ import annotations

import argparse
import csv
import glob
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bacterioscope.pipeline import (  # noqa: E402
    AnalysisResult,
    BacterioScopePipeline,
    PipelineConfig,
)
from bacterioscope.utils.image import resize_canonical  # noqa: E402
from bacterioscope.utils.visualization import draw_results  # noqa: E402

_FILL_RATIO_TRUST_CEILING = 0.90
_FILL_RATIO_PRESENTABLE_CEILING = 0.80
_MIN_PRESENTABLE_FRACTION = 0.30
_UZH_COUNT = 20


@dataclass
class DiskAssessment:
    """Trust and presentability assessment for one measured disk."""

    image_name: str
    disk_index: int
    antibiotic: str
    diameter_mm: float
    fill_ratio: float
    flags: list[str]
    is_trustworthy: bool
    is_presentable: bool


def _survey_images() -> list[str]:
    real = sorted(glob.glob("examples/real/*.jpg"))
    uzh = sorted(glob.glob("data/raw/dryad_uzh/images_original/*.jpg"))[:_UZH_COUNT]
    return real + uzh


def _bbox_fill_ratio(mask: np.ndarray) -> float | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    w = xs.max() - xs.min()
    h = ys.max() - ys.min()
    bbox_area = w * h
    if bbox_area == 0:
        return None
    return float((mask.sum() / 255) / bbox_area)


def _assess_disk(image_name: str, idx: int, result: AnalysisResult) -> DiskAssessment | None:
    zone = result.zones[idx]
    if zone.mask is None:
        return None
    fill_ratio = _bbox_fill_ratio(zone.mask)
    if fill_ratio is None:
        return None
    flags = result.flags[idx] if result.flags else []
    return DiskAssessment(
        image_name=image_name,
        disk_index=idx,
        antibiotic=result.classifications[idx].antibiotic,
        diameter_mm=zone.diameter_mm,
        fill_ratio=fill_ratio,
        flags=flags,
        is_trustworthy=fill_ratio < _FILL_RATIO_TRUST_CEILING and not flags,
        is_presentable=fill_ratio < _FILL_RATIO_PRESENTABLE_CEILING and not flags,
    )


def _write_report(assessments: list[DiskAssessment], output_dir: Path) -> None:
    path = output_dir / "survey_report.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["image", "disk_index", "antibiotic", "diameter_mm",
             "fill_ratio", "flags", "trustworthy", "presentable"]
        )
        for a in assessments:
            writer.writerow(
                [a.image_name, a.disk_index, a.antibiotic, round(a.diameter_mm, 1),
                 round(a.fill_ratio, 3), ";".join(a.flags), a.is_trustworthy, a.is_presentable]
            )
    print(f"Per-disk report: {path}")


def _presentable_score(assessments: list[DiskAssessment]) -> tuple[int, int]:
    presentable = sum(1 for a in assessments if a.is_presentable)
    return presentable, len(assessments)


def _run_survey(
    pipeline: BacterioScopePipeline,
) -> tuple[list[DiskAssessment], dict[str, tuple[AnalysisResult, list[DiskAssessment]]]]:
    all_assessments: list[DiskAssessment] = []
    per_image: dict[str, tuple[AnalysisResult, list[DiskAssessment]]] = {}
    for path in _survey_images():
        name = Path(path).name
        try:
            result = pipeline.analyze(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: ERROR {exc}")
            continue
        image_assessments = [
            a for i in range(len(result.disks))
            if (a := _assess_disk(name, i, result)) is not None
        ]
        all_assessments.extend(image_assessments)
        per_image[name] = (result, image_assessments)
    return all_assessments, per_image


def _report_ranking(
    ranked: list[tuple[str, tuple[AnalysisResult, list[DiskAssessment]]]],
) -> None:
    print("\nImages ranked by presentable-disk count (the bar for a pitch slide, best first):")
    for name, (_, assessments) in ranked[:10]:
        presentable, total = _presentable_score(assessments)
        print(f"  {name}: {presentable}/{total} disks presentable")


def _report_best_single_disk(all_assessments: list[DiskAssessment]) -> None:
    presentable_disks = [a for a in all_assessments if a.is_presentable]
    if not presentable_disks:
        print("\nNo single disk in the whole survey clears the presentability bar.")
        return
    best = min(presentable_disks, key=lambda a: a.fill_ratio)
    print(
        f"Best single presentable disk: {best.image_name} disk_{best.disk_index} "
        f"({best.antibiotic}, {best.diameter_mm:.1f}mm, fill_ratio={best.fill_ratio:.2f})"
    )


def _save_annotated(
    name: str, result: AnalysisResult, output_dir: Path,
) -> Path:
    image = cv2.imread(str(Path("examples/real" if "real_plate" in name else
                                 "data/raw/dryad_uzh/images_original") / name))
    image, _ = resize_canonical(image)
    annotated = draw_results(
        image.copy(), result.disks, result.zones, result.classifications, result.flags,
    )
    out_path = output_dir / f"annotated_{Path(name).stem}.png"
    cv2.imwrite(str(out_path), annotated)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/pitch_candidates"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = BacterioScopePipeline(PipelineConfig())
    all_assessments, per_image = _run_survey(pipeline)
    _write_report(all_assessments, args.output_dir)

    ranked = sorted(per_image.items(), key=lambda kv: _presentable_score(kv[1][1]), reverse=True)
    _report_ranking(ranked)

    print("\nRecommended for the pitch (presentable fraction "
          f">= {_MIN_PRESENTABLE_FRACTION:.0%}) -- do not use anything not listed here:")
    recommended = []
    for name, (result, assessments) in ranked:
        presentable, total = _presentable_score(assessments)
        if total == 0 or presentable / total < _MIN_PRESENTABLE_FRACTION:
            continue
        recommended.append(name)
        out_path = _save_annotated(name, result, args.output_dir)
        print(f"  {name}: {presentable}/{total} presentable -> {out_path}")
    if not recommended:
        print("  None. No image clears the presentability bar for a full panel.")

    _report_best_single_disk(all_assessments)
    return 0


if __name__ == "__main__":
    sys.exit(main())
