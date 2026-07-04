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
