"""Tests for evaluation.synthetic_benchmark."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from bacterioscope.classification.clsi import CLSIClassifier, SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.evaluation.synthetic_benchmark import (
    DiskOutcome,
    DiskTruth,
    PlateOutcome,
    PlateTruth,
    evaluate_plate,
    load_synthetic_truth,
    match_detections,
    summarize,
)
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.segmentation.watershed import ZoneResult

_REPO = Path(__file__).resolve().parents[1]
_TRUTH = _REPO / "examples" / "synthetic" / "ground_truth.json"


def _plate(*disks: tuple[str, float, float, float]) -> PlateTruth:
    return PlateTruth(
        image="p.png",
        disks=tuple(DiskTruth(name, (x, y), mm, mm) for name, x, y, mm in disks),
    )


def _result(detections: list[tuple[float, float, float]], flags: list[list[str]]) -> AnalysisResult:
    disks = [
        DiskResult(label=f"disk_{i}", center_x=int(x), center_y=int(y), radius_px=14,
                   confidence=1.0, bbox=(int(x) - 14, int(y) - 14, int(x) + 14, int(y) + 14))
        for i, (x, y, _) in enumerate(detections)
    ]
    zones = [
        ZoneResult(disk_label=f"disk_{i}", center_x=int(x), center_y=int(y), radius_px=mm * 2.8,
                   diameter_px=mm * 5.6, diameter_mm=mm, area_px=1.0, circularity=0.9, mask=None)
        for i, (x, y, mm) in enumerate(detections)
    ]
    classifications = [
        SusceptibilityResult(antibiotic=f"disk_{i}", zone_diameter_mm=mm, category="UNKNOWN",
                             breakpoints={})
        for i, (_, _, mm) in enumerate(detections)
    ]
    return AnalysisResult(image_path="p.png", plate_diameter_px=504.0, px_per_mm=5.6,
                          disks=disks, zones=zones, classifications=classifications, flags=flags)


def _outcome(reference: str, predicted: str, flags: tuple[str, ...] = ()) -> DiskOutcome:
    return DiskOutcome("p.png", "x", 20.0, 20.0, 20.0, reference, predicted, flags)


class TestMatchDetections:
    def test_pairs_nearest_detection(self) -> None:
        truth = _plate(("a", 100, 100, 20), ("b", 300, 100, 20))
        assert match_detections(truth, [(302, 99), (101, 101)]) == [1, 0]

    def test_detection_outside_tolerance_is_unmatched(self) -> None:
        truth = _plate(("a", 100, 100, 20))
        assert match_detections(truth, [(200, 200)]) == [None]

    def test_one_detection_never_serves_two_disks(self) -> None:
        truth = _plate(("a", 100, 100, 20), ("b", 110, 100, 20))
        assignment = match_detections(truth, [(104, 100)])
        assert assignment.count(0) == 1
        assert assignment.count(None) == 1


class TestEvaluatePlate:
    def test_labels_and_missed_disks(self) -> None:
        truth = _plate(("meropenem", 100, 100, 24.0), ("ampicillin", 300, 100, 10.0))
        result = _result([(101, 100, 23.0)], [["crop_boundary"]])
        outcome = evaluate_plate(truth, result, CLSIClassifier())
        assert outcome.labels == ("meropenem",)
        assert outcome.disks[0].measured_mm == 23.0
        assert outcome.disks[0].flags == ("crop_boundary",)
        assert outcome.disks[1].measured_mm is None

    def test_extra_detection_keeps_placeholder_label(self) -> None:
        truth = _plate(("meropenem", 100, 100, 24.0))
        result = _result([(400, 400, 15.0), (100, 100, 24.0)], [[], []])
        outcome = evaluate_plate(truth, result, CLSIClassifier())
        assert outcome.labels == ("disk_0", "meropenem")


class TestSummarize:
    def test_sdd_discordance_is_minor(self) -> None:
        plate = PlateOutcome("p.png", 2, 2, (_outcome("S", "SDD"), _outcome("SDD", "R")), ())
        cat = summarize([plate])["categorical"]
        assert (cat["minor"], cat["very_major"], cat["major"]) == (2, 0, 0)

    def test_very_major_and_major(self) -> None:
        plate = PlateOutcome("p.png", 2, 2, (_outcome("R", "S"), _outcome("S", "R")), ())
        cat = summarize([plate])["categorical"]
        assert (cat["very_major"], cat["major"]) == (1, 1)
        assert (cat["very_major_rate"], cat["major_rate"]) == (1.0, 1.0)

    def test_flagged_and_unflagged_split(self) -> None:
        disks = (_outcome("R", "S", ("overlap",)), _outcome("S", "S"))
        summary = summarize([PlateOutcome("p.png", 2, 2, disks, ())])
        assert summary["categorical_flagged"]["very_major"] == 1
        assert summary["categorical_unflagged"]["very_major"] == 0

    def test_uncategorized_disks_are_excluded_and_counted(self) -> None:
        plate = PlateOutcome("p.png", 1, 1, (_outcome("UNKNOWN", "UNKNOWN"),), ())
        cat = summarize([plate])["categorical"]
        assert (cat["n"], cat["excluded_uncategorized"], cat["ca"]) == (0, 1, None)


class TestGroundTruthFile:
    def test_loads_all_plates(self) -> None:
        plates = load_synthetic_truth(_TRUTH)
        assert len(plates) == 8
        assert sum(len(p.disks) for p in plates) == 54

    def test_committed_file_matches_generator(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "generate_test_plates", _REPO / "scripts" / "generate_test_plates.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        committed = json.loads(_TRUTH.read_text(encoding="utf-8"))["plates"]
        assert committed == module.ground_truth()

    @pytest.mark.parametrize("plate", load_synthetic_truth(_TRUTH), ids=lambda p: p.image)
    def test_drawn_is_below_nominal(self, plate: PlateTruth) -> None:
        assert all(disk.drawn_mm <= disk.nominal_mm for disk in plate.disks)
