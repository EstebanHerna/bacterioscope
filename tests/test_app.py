"""Tests for app-level helper functions that do not require a Streamlit runtime."""

from __future__ import annotations

from bacterioscope._app_logic import (
    _UNASSIGNED,
    reclassify_with_assignment,
    reclassify_with_override,
)
from bacterioscope.classification.clsi import CLSIClassifier


class TestReclassifyWithAssignment:
    def setup_method(self) -> None:
        self.clf = CLSIClassifier()

    def test_known_antibiotic_susceptible(self) -> None:
        result = reclassify_with_assignment(27.0, "ciprofloxacin", self.clf)
        assert result.category == "S"
        assert result.antibiotic == "ciprofloxacin"
        assert result.zone_diameter_mm == 27.0

    def test_known_antibiotic_resistant(self) -> None:
        result = reclassify_with_assignment(10.0, "ciprofloxacin", self.clf)
        assert result.category == "R"

    def test_known_antibiotic_intermediate(self) -> None:
        result = reclassify_with_assignment(23.0, "ciprofloxacin", self.clf)
        assert result.category == "I"

    def test_unassigned_sentinel_preserves_disk_label(self) -> None:
        result = reclassify_with_assignment(27.0, _UNASSIGNED, self.clf, "disk_0")
        assert result.category == "UNKNOWN"
        assert result.antibiotic == "disk_0"
        assert result.zone_diameter_mm == 27.0

    def test_empty_string_preserves_disk_label(self) -> None:
        result = reclassify_with_assignment(15.0, "", self.clf, "disk_3")
        assert result.category == "UNKNOWN"
        assert result.antibiotic == "disk_3"

    def test_breakpoints_populated_for_known_antibiotic(self) -> None:
        result = reclassify_with_assignment(27.0, "meropenem", self.clf)
        assert result.breakpoints
        assert "S" in result.breakpoints

    def test_breakpoints_empty_for_unassigned(self) -> None:
        result = reclassify_with_assignment(27.0, _UNASSIGNED, self.clf, "disk_1")
        assert result.breakpoints == {}


class TestReclassifyWithOverride:
    def setup_method(self) -> None:
        self.clf = CLSIClassifier()

    def test_no_override_uses_measured_value(self) -> None:
        result, source = reclassify_with_override(27.0, None, "ciprofloxacin", self.clf)
        assert result.zone_diameter_mm == 27.0
        assert source == "automatic"

    def test_override_replaces_measured_value(self) -> None:
        result, source = reclassify_with_override(27.0, 15.0, "ciprofloxacin", self.clf)
        assert result.zone_diameter_mm == 15.0
        assert source == "manual"

    def test_override_changes_category(self) -> None:
        auto, _ = reclassify_with_override(27.0, None, "ciprofloxacin", self.clf)
        manual, _ = reclassify_with_override(27.0, 15.0, "ciprofloxacin", self.clf)
        assert auto.category == "S"
        assert manual.category == "R"

    def test_source_is_automatic_when_override_is_none(self) -> None:
        _, source = reclassify_with_override(20.0, None, "ciprofloxacin", self.clf)
        assert source == "automatic"

    def test_source_is_manual_when_override_provided(self) -> None:
        _, source = reclassify_with_override(20.0, 20.0, "ciprofloxacin", self.clf)
        assert source == "manual"

    def test_override_with_unassigned_antibiotic(self) -> None:
        result, source = reclassify_with_override(27.0, 20.0, _UNASSIGNED, self.clf, "disk_0")
        assert result.category == "UNKNOWN"
        assert source == "manual"
