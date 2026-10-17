"""Deterministic benchmark of the vision pipeline against synthetic plates.

The eight plates in ``examples/synthetic/`` are generated, so their exact
drawn geometry is known (``examples/synthetic/ground_truth.json``, written
by ``scripts/generate_test_plates.py --truth-only``). This module measures
what the pipeline recovers from those images: disk detection, zone
diameter error, and the S/I/R categories that the measurement error alone
induces.

What this is not: clinical validation. The reference categories come from
the project's own classifier applied to the drawn diameters, so the
categorical numbers isolate measurement-induced disagreement only; they do
not test whether the breakpoint table itself is right. Synthetic plates are
also far cleaner than real photographs (see docs/VALIDATION_REPORT.md for
the real-photo numbers, which are much worse).

Category convention: SDD is treated like I for error classification (both
lie between S and R), so any discordance involving SDD is a minor error.
This is a declared convention of this benchmark; ``evaluation.metrics``
deliberately still rejects SDD.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bacterioscope.classification.clsi import CLSIClassifier

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

EA_MARGIN_MM = 2.0
_MATCH_TOLERANCE_PX = 22.0
_INTERMEDIATE_LIKE = frozenset({"I", "SDD"})
_CATEGORIZED = frozenset({"S", "I", "SDD", "R"})


@dataclass(frozen=True)
class DiskTruth:
    """One drawn disk on a synthetic plate."""

    antibiotic: str
    center_px: tuple[float, float]
    drawn_mm: float
    nominal_mm: float


@dataclass(frozen=True)
class PlateTruth:
    """Every drawn disk on one synthetic plate."""

    image: str
    disks: tuple[DiskTruth, ...]


@dataclass(frozen=True)
class DiskOutcome:
    """Pipeline outcome for one true disk."""

    image: str
    antibiotic: str
    reference_mm: float
    nominal_mm: float
    measured_mm: float | None
    reference_category: str
    predicted_category: str | None
    flags: tuple[str, ...]

    @property
    def detected(self) -> bool:
        return self.measured_mm is not None

    @property
    def abs_error_mm(self) -> float | None:
        if self.measured_mm is None:
            return None
        return abs(self.measured_mm - self.reference_mm)


@dataclass(frozen=True)
class PlateOutcome:
    """Pipeline outcome for one plate, plus its antibiotic-labelled result."""

    image: str
    n_true: int
    n_detected: int
    disks: tuple[DiskOutcome, ...]
    labels: tuple[str, ...]


def load_synthetic_truth(path: Path) -> list[PlateTruth]:
    """Load ``ground_truth.json`` written by ``generate_test_plates.py``.

    Args:
        path: Path to the JSON file.

    Returns:
        One PlateTruth per synthetic plate.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        PlateTruth(
            image=plate["image"],
            disks=tuple(
                DiskTruth(
                    antibiotic=disk["antibiotic"],
                    center_px=(float(disk["center_px"][0]), float(disk["center_px"][1])),
                    drawn_mm=float(disk["drawn_mm"]),
                    nominal_mm=float(disk["nominal_mm"]),
                )
                for disk in plate["disks"]
            ),
        )
        for plate in payload["plates"]
    ]


def match_detections(
    truth: PlateTruth,
    centers: Sequence[tuple[float, float]],
    tolerance_px: float = _MATCH_TOLERANCE_PX,
) -> list[int | None]:
    """Greedily pair each true disk with its nearest unused detection.

    Pairs are taken shortest distance first, so one detection is never
    assigned to two true disks.

    Args:
        truth: The plate's drawn disks.
        centers: Detected disk centres, in the same pixel frame as ``truth``.
        tolerance_px: Maximum centre distance for a valid pair.

    Returns:
        For each true disk (in ``truth.disks`` order), the index of its
        matched detection, or None when no detection is close enough.
    """
    candidates = sorted(
        (math.dist(disk.center_px, center), t, d)
        for t, disk in enumerate(truth.disks)
        for d, center in enumerate(centers)
    )
    assigned: list[int | None] = [None] * len(truth.disks)
    used: set[int] = set()
    for distance, t, d in candidates:
        if distance > tolerance_px:
            break
        if assigned[t] is None and d not in used:
            assigned[t] = d
            used.add(d)
    return assigned


def evaluate_plate(
    truth: PlateTruth, result: AnalysisResult, classifier: CLSIClassifier
) -> PlateOutcome:
    """Compare one pipeline result with its plate's drawn geometry.

    Args:
        truth: The plate's drawn disks.
        result: Pipeline output for that plate's image.
        classifier: Classifier used for both reference and predicted
            categories (so only measurement error separates them).

    Returns:
        PlateOutcome, including per-detection antibiotic labels that can be
        passed to ``BacterioScopePipeline.reclassify_with_labels``.
    """
    scale = result.canonical_scale_factor or 1.0
    centers = [(disk.center_x / scale, disk.center_y / scale) for disk in result.disks]
    assignment = match_detections(truth, centers)

    labels = [f"disk_{i}" for i in range(len(result.disks))]
    outcomes = []
    for disk_truth, detection in zip(truth.disks, assignment):
        reference = classifier.classify(disk_truth.antibiotic, disk_truth.drawn_mm).category
        if detection is None:
            outcomes.append(DiskOutcome(
                truth.image, disk_truth.antibiotic, disk_truth.drawn_mm,
                disk_truth.nominal_mm, None, reference, None, (),
            ))
            continue
        labels[detection] = disk_truth.antibiotic
        measured = result.zones[detection].diameter_mm
        flags = tuple(result.flags[detection]) if detection < len(result.flags) else ()
        outcomes.append(DiskOutcome(
            truth.image, disk_truth.antibiotic, disk_truth.drawn_mm, disk_truth.nominal_mm,
            measured, reference, classifier.classify(disk_truth.antibiotic, measured).category,
            flags,
        ))
    return PlateOutcome(
        image=truth.image,
        n_true=len(truth.disks),
        n_detected=len(result.disks),
        disks=tuple(outcomes),
        labels=tuple(labels),
    )


def _error_class(reference: str, predicted: str) -> str:
    if reference == predicted:
        return "agree"
    if reference == "R" and predicted == "S":
        return "very_major"
    if reference == "S" and predicted == "R":
        return "major"
    return "minor"


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _measurement_block(disks: Sequence[DiskOutcome], frame: str) -> dict[str, Any]:
    if frame == "nominal":
        errors = [abs(d.measured_mm - d.nominal_mm) for d in disks if d.measured_mm is not None]
        signed = [d.measured_mm - d.nominal_mm for d in disks if d.measured_mm is not None]
    else:
        errors = [d.abs_error_mm for d in disks if d.abs_error_mm is not None]
        signed = [d.measured_mm - d.reference_mm for d in disks if d.measured_mm is not None]
    if not errors:
        return {"n": 0, "ea": None, "mae_mm": None, "bias_mm": None, "p90_abs_error_mm": None}
    return {
        "n": len(errors),
        "ea": sum(e <= EA_MARGIN_MM for e in errors) / len(errors),
        "mae_mm": sum(errors) / len(errors),
        "bias_mm": sum(signed) / len(signed),
        "p90_abs_error_mm": _quantile(errors, 0.9),
    }


def _categorical_block(disks: Sequence[DiskOutcome]) -> dict[str, Any]:
    pairs = [
        (d.reference_category, d.predicted_category)
        for d in disks
        if d.predicted_category in _CATEGORIZED and d.reference_category in _CATEGORIZED
    ]
    excluded = sum(1 for d in disks if d.detected) - len(pairs)
    counts = {"agree": 0, "very_major": 0, "major": 0, "minor": 0}
    for reference, predicted in pairs:
        counts[_error_class(reference, predicted)] += 1
    n_r = sum(1 for reference, _ in pairs if reference == "R")
    n_s = sum(1 for reference, _ in pairs if reference == "S")
    return {
        "n": len(pairs),
        "excluded_uncategorized": excluded,
        "ca": counts["agree"] / len(pairs) if pairs else None,
        "very_major": counts["very_major"],
        "very_major_rate": counts["very_major"] / n_r if n_r else None,
        "major": counts["major"],
        "major_rate": counts["major"] / n_s if n_s else None,
        "minor": counts["minor"],
        "minor_rate": counts["minor"] / len(pairs) if pairs else None,
        "n_reference_resistant": n_r,
        "n_reference_susceptible": n_s,
    }


def summarize(plates: Sequence[PlateOutcome]) -> dict[str, Any]:
    """Aggregate per-plate outcomes into the benchmark's headline metrics.

    Args:
        plates: One PlateOutcome per evaluated plate.

    Returns:
        Dict with ``detection``, ``measurement`` (drawn and nominal frames,
        plus flagged/unflagged splits), ``categorical`` and ``per_plate``.
    """
    disks = [d for plate in plates for d in plate.disks]
    detected = [d for d in disks if d.detected]
    n_true = sum(p.n_true for p in plates)
    n_detections = sum(p.n_detected for p in plates)
    unflagged = [d for d in detected if not d.flags]
    flagged = [d for d in detected if d.flags]
    return {
        "n_plates": len(plates),
        "detection": {
            "true_disks": n_true,
            "detections": n_detections,
            "matched": len(detected),
            "recall": len(detected) / n_true if n_true else None,
            "precision": len(detected) / n_detections if n_detections else None,
            "plates_with_exact_count": sum(p.n_detected == p.n_true for p in plates),
        },
        "measurement": {
            "drawn_frame": _measurement_block(detected, "drawn"),
            "nominal_frame": _measurement_block(detected, "nominal"),
            "unflagged": _measurement_block(unflagged, "drawn"),
            "flagged": _measurement_block(flagged, "drawn"),
            "flagged_fraction": len(flagged) / len(detected) if detected else None,
        },
        "categorical": _categorical_block(detected),
        "categorical_unflagged": _categorical_block(unflagged),
        "categorical_flagged": _categorical_block(flagged),
        "per_plate": [
            {
                "image": p.image,
                "true_disks": p.n_true,
                "detections": p.n_detected,
                "matched": sum(d.detected for d in p.disks),
                **{
                    key: _measurement_block([d for d in p.disks if d.detected], "drawn")[key]
                    for key in ("ea", "mae_mm", "bias_mm")
                },
                "ca": _categorical_block(list(p.disks))["ca"],
            }
            for p in plates
        ],
    }
