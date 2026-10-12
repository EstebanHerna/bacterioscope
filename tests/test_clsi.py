import math

import pytest

from bacterioscope.classification.clsi import CLSIClassifier


class TestCLSIClassifier:
    def setup_method(self) -> None:
        self.classifier = CLSIClassifier(organism_group="Enterobacteriaceae")

    def test_meropenem_susceptible(self) -> None:
        result = self.classifier.classify("meropenem", 25.0)
        assert result.category == "S"
        assert result.zone_diameter_mm == 25.0

    def test_meropenem_intermediate(self) -> None:
        result = self.classifier.classify("meropenem", 21.0)
        assert result.category == "I"

    def test_meropenem_resistant(self) -> None:
        result = self.classifier.classify("meropenem", 15.0)
        assert result.category == "R"

    def test_meropenem_boundary_susceptible(self) -> None:
        result = self.classifier.classify("meropenem", 23.0)
        assert result.category == "S"

    def test_meropenem_boundary_resistant(self) -> None:
        result = self.classifier.classify("meropenem", 19.0)
        assert result.category == "R"

    def test_unknown_antibiotic(self) -> None:
        result = self.classifier.classify("nonexistent_drug", 20.0)
        assert result.category == "UNKNOWN"

    def test_list_antibiotics(self) -> None:
        antibiotics = self.classifier.list_antibiotics()
        assert "meropenem" in antibiotics
        assert "imipenem" in antibiotics
        assert len(antibiotics) >= 10

    def test_case_insensitive(self) -> None:
        result = self.classifier.classify("Meropenem", 25.0)
        assert result.category == "S"

    def test_imipenem_susceptible(self) -> None:
        result = self.classifier.classify("imipenem", 24.0)
        assert result.category == "S"

    def test_ciprofloxacin_resistant(self) -> None:
        result = self.classifier.classify("ciprofloxacin", 18.0)
        assert result.category == "R"

    @pytest.mark.parametrize(
        ("antibiotic", "diameter", "expected"),
        [
            ("gentamicin", 14, "R"), ("gentamicin", 15, "I"),
            ("gentamicin", 17, "I"), ("gentamicin", 18, "S"),
            ("amikacin", 16, "R"), ("amikacin", 17, "I"),
            ("amikacin", 19, "I"), ("amikacin", 20, "S"),
            ("cefepime", 18, "R"), ("cefepime", 19, "SDD"),
            ("cefepime", 24, "SDD"), ("cefepime", 25, "S"),
            ("piperacillin-tazobactam", 20, "R"),
            ("piperacillin-tazobactam", 21, "SDD"),
            ("piperacillin-tazobactam", 24, "SDD"),
            ("piperacillin-tazobactam", 25, "S"),
        ],
    )
    def test_ed33_audited_breakpoint_boundaries(
        self, antibiotic: str, diameter: float, expected: str
    ) -> None:
        assert self.classifier.classify(antibiotic, diameter).category == expected

    def test_whole_mm_rounding_preserves_original_measurement(self) -> None:
        result = self.classifier.classify("cefepime", 24.6)

        assert result.category == "S"
        assert result.zone_diameter_mm == 24.6

    @pytest.mark.parametrize("diameter", [-0.1, math.nan, math.inf, -math.inf])
    def test_invalid_measurement_is_unknown(self, diameter: float) -> None:
        assert self.classifier.classify("cefepime", diameter).category == "UNKNOWN"
