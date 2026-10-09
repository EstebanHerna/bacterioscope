"""Tests for agent.contract: mapping AnalysisResult into the rule-tool contract."""

from __future__ import annotations

from bacterioscope.agent.contract import build_measurement_section, normalize_ast_observations
from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.segmentation.watershed import ZoneResult


def _disk(i: int) -> DiskResult:
    return DiskResult(
        label=f"disk_{i}", center_x=100 + i * 50, center_y=100,
        radius_px=15, confidence=1.0, bbox=(85 + i * 50, 85, 115 + i * 50, 115),
    )


def _zone(i: int, mm: float) -> ZoneResult:
    return ZoneResult(
        disk_label=f"disk_{i}", center_x=100 + i * 50, center_y=100,
        radius_px=20.0, diameter_px=40.0, diameter_mm=mm,
        area_px=1256.0, circularity=0.9, mask=None,
    )


def _cls(antibiotic: str, mm: float, category: str) -> SusceptibilityResult:
    return SusceptibilityResult(
        antibiotic=antibiotic, zone_diameter_mm=mm, category=category,
        breakpoints={} if category == "UNKNOWN" else {"S": 20.0, "R": 15.0},
    )


def _result(
    classifications: list[SusceptibilityResult],
    flags: list[list[str]] | None = None,
    standard: str = "CLSI M100-Ed33 2023",
) -> AnalysisResult:
    n = len(classifications)
    return AnalysisResult(
        image_path="/tmp/test.jpg",
        plate_diameter_px=900.0,
        px_per_mm=10.0,
        disks=[_disk(i) for i in range(n)],
        zones=[_zone(i, c.zone_diameter_mm) for i, c in enumerate(classifications)],
        classifications=classifications,
        flags=flags or [[] for _ in range(n)],
        breakpoint_table_version=standard,
    )


class TestNormalizeAstObservations:
    def test_resolved_disks_become_observations(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S"), _cls("meropenem", 18.0, "R")])
        normalized = normalize_ast_observations(result)
        assert len(normalized.observations) == 2
        assert normalized.observations[0].antibiotic_code == "ciprofloxacin"
        assert normalized.observations[0].category == "S"

    def test_unknown_category_is_skipped_not_raised(self) -> None:
        result = _result([_cls("disk_0", 12.0, "UNKNOWN")])
        normalized = normalize_ast_observations(result)
        assert normalized.observations == ()
        assert normalized.measurement[0].included_in_rule_evaluation is False
        assert normalized.measurement[0].exclusion_reason == "unresolved_antibiotic_identity"

    def test_duplicate_antibiotic_code_is_skipped(self) -> None:
        result = _result([
            _cls("ciprofloxacin", 26.0, "S"),
            _cls("ciprofloxacin", 10.0, "R"),
        ])
        normalized = normalize_ast_observations(result)
        assert len(normalized.observations) == 1
        assert normalized.measurement[1].included_in_rule_evaluation is False
        reason = normalized.measurement[1].exclusion_reason
        assert reason == "duplicate_antibiotic_code:ciprofloxacin"

    def test_duplicate_check_is_case_insensitive(self) -> None:
        result = _result([
            _cls("Ciprofloxacin", 26.0, "S"),
            _cls("CIPROFLOXACIN", 10.0, "R"),
        ])
        normalized = normalize_ast_observations(result)
        assert len(normalized.observations) == 1

    def test_measurement_keeps_every_disk(self) -> None:
        result = _result([
            _cls("ciprofloxacin", 26.0, "S"),
            _cls("disk_1", 5.0, "UNKNOWN"),
        ])
        normalized = normalize_ast_observations(result)
        assert len(normalized.measurement) == 2

    def test_quality_flags_carried_through(self) -> None:
        result = _result(
            [_cls("ciprofloxacin", 26.0, "S")], flags=[["low_circularity", "overlap"]]
        )
        normalized = normalize_ast_observations(result)
        assert normalized.measurement[0].quality_flags == ("low_circularity", "overlap")

    def test_empty_result_returns_empty(self) -> None:
        normalized = normalize_ast_observations(_result([]))
        assert normalized.observations == ()
        assert normalized.measurement == ()


class TestBuildMeasurementSection:
    def test_standard_comes_from_result(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")], standard="CLSI M100-Ed33 2023")
        normalized = normalize_ast_observations(result)
        section = build_measurement_section(result, normalized.measurement)
        assert section["standard"] == "CLSI M100-Ed33 2023"

    def test_observation_shape_matches_schema_fields(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        section = build_measurement_section(result, normalized.measurement)
        obs = section["observations"][0]
        assert set(obs.keys()) == {
            "disk_index", "antibiotic_code", "category", "zone_mm",
            "quality_flags", "included_in_rule_evaluation", "exclusion_reason",
        }

    def test_unresolved_disk_has_null_exclusion_reason_is_a_string(self) -> None:
        result = _result([_cls("disk_0", 12.0, "UNKNOWN")])
        normalized = normalize_ast_observations(result)
        section = build_measurement_section(result, normalized.measurement)
        assert section["observations"][0]["exclusion_reason"] == "unresolved_antibiotic_identity"
