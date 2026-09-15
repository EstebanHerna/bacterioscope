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
flags (``overlap``, ``low_circularity``, ``boundary``, ``small_zone``), this
gives a per-disk trust classification without inventing a new metric.

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
_UZH_COUNT = 20


@dataclass
class DiskAssessment:
    """Trust assessment for one measured disk."""

    image_name: str
    disk_index: int
    antibiotic: str
    diameter_mm: float
    fill_ratio: float
    flags: list[str]
    is_trustworthy: bool


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
    is_trustworthy = fill_ratio < _FILL_RATIO_TRUST_CEILING and not flags
    return DiskAssessment(
        image_name=image_name,
        disk_index=idx,
        antibiotic=result.classifications[idx].antibiotic,
        diameter_mm=zone.diameter_mm,
        fill_ratio=fill_ratio,
        flags=flags,
        is_trustworthy=is_trustworthy,
    )


def _write_report(assessments: list[DiskAssessment], output_dir: Path) -> None:
    path = output_dir / "survey_report.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["image", "disk_index", "antibiotic", "diameter_mm",
             "fill_ratio", "flags", "trustworthy"]
        )
        for a in assessments:
            writer.writerow(
                [a.image_name, a.disk_index, a.antibiotic, round(a.diameter_mm, 1),
                 round(a.fill_ratio, 3), ";".join(a.flags), a.is_trustworthy]
            )
    print(f"Per-disk report: {path}")


def _image_score(assessments: list[DiskAssessment]) -> tuple[int, int]:
    trusted = sum(1 for a in assessments if a.is_trustworthy)
    return trusted, len(assessments)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/pitch_candidates"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = BacterioScopePipeline(PipelineConfig())
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

    _write_report(all_assessments, args.output_dir)

    ranked = sorted(
        per_image.items(),
        key=lambda kv: _image_score(kv[1][1]),
        reverse=True,
    )
    print("\nImages ranked by trustworthy-disk count (best first):")
    for name, (_, assessments) in ranked[:10]:
        trusted, total = _image_score(assessments)
        print(f"  {name}: {trusted}/{total} disks trustworthy")

    def _is_fully_trustworthy(assessments: list[DiskAssessment]) -> bool:
        trusted, total = _image_score(assessments)
        return total > 0 and trusted == total

    best_full_panel = next(
        (r for r in ranked if _is_fully_trustworthy(r[1][1])), None,
    )
    if best_full_panel is None:
        print("\nNo image gives a fully defensible panel (every disk trustworthy).")
        best_single = max(all_assessments, key=lambda a: (a.is_trustworthy, -a.fill_ratio))
        print(
            f"Best single defensible disk: {best_single.image_name} disk_{best_single.disk_index} "
            f"({best_single.antibiotic}, {best_single.diameter_mm:.1f}mm, "
            f"fill_ratio={best_single.fill_ratio:.2f}, flags={best_single.flags or 'none'})"
        )

    for name, (result, _) in ranked[:3]:
        image = cv2.imread(str(Path("examples/real" if "real_plate" in name else
                                     "data/raw/dryad_uzh/images_original") / name))
        image, _ = resize_canonical(image)
        annotated = draw_results(
            image.copy(), result.disks, result.zones, result.classifications, result.flags,
        )
        out_path = args.output_dir / f"annotated_{Path(name).stem}.png"
        cv2.imwrite(str(out_path), annotated)
        print(f"Saved annotated candidate: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
