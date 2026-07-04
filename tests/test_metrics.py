"""Tests for bacterioscope.evaluation.metrics and report."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from bacterioscope.evaluation.metrics import (
    categorical_agreement,
    collect_metrics,
    error_rates,
    essential_agreement,
    overall_accuracy,
    per_class_metrics,
    sir_confusion_matrix,
    zone_diameter_stats,
)
from bacterioscope.evaluation.report import generate_html, generate_markdown, save_report


class TestCategoricalAgreement:
    def test_perfect_agreement(self) -> None:
        labels = ["S", "I", "R", "S"]
        assert categorical_agreement(labels, labels) == pytest.approx(1.0)

    def test_zero_agreement(self) -> None:
        assert categorical_agreement(["R", "R", "S"], ["S", "S", "R"]) == pytest.approx(0.0)

    def test_partial_agreement(self) -> None:
        pred = ["S", "S", "R", "R"]
        ref = ["S", "I", "R", "S"]
        assert categorical_agreement(pred, ref) == pytest.approx(0.5)

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            categorical_agreement(["S"], ["S", "R"])

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            categorical_agreement([], [])


class TestErrorRates:
    def test_perfect_case_no_errors(self) -> None:
        pred = ["S", "I", "R", "S", "R"]
        ref = ["S", "I", "R", "S", "R"]
        result = error_rates(pred, ref)
        assert result["vme_count"] == 0
        assert result["me_count"] == 0
        assert result["minor_count"] == 0
        assert result["vme_rate"] == pytest.approx(0.0)
        assert result["me_rate"] == pytest.approx(0.0)
        assert result["minor_rate"] == pytest.approx(0.0)

    def test_vme_is_predicted_s_reference_r(self) -> None:
        """VME definition: system says S, truth is R.
        Patient receives antibiotic that will not work."""
        pred = ["S"]
        ref = ["R"]
        result = error_rates(pred, ref)
        assert result["vme_count"] == 1, "VME must fire when pred=S and ref=R"
        assert result["me_count"] == 0, "ME must NOT fire when pred=S and ref=R"

    def test_me_is_predicted_r_reference_s(self) -> None:
        """ME definition: system says R, truth is S.
        Patient is denied effective antibiotic."""
        pred = ["R"]
        ref = ["S"]
        result = error_rates(pred, ref)
        assert result["me_count"] == 1, "ME must fire when pred=R and ref=S"
        assert result["vme_count"] == 0, "VME must NOT fire when pred=R and ref=S"

    def test_vme_rate_uses_resistant_denominator(self) -> None:
        pred = ["S", "S", "R"]
        ref = ["S", "R", "R"]
        result = error_rates(pred, ref)
        assert result["n_resistant"] == 2
        assert result["vme_count"] == 1
        assert result["vme_rate"] == pytest.approx(0.5)

    def test_me_rate_uses_susceptible_denominator(self) -> None:
        pred = ["R", "S", "R"]
        ref = ["S", "S", "R"]
        result = error_rates(pred, ref)
        assert result["n_susceptible"] == 2
        assert result["me_count"] == 1
        assert result["me_rate"] == pytest.approx(0.5)

    def test_minor_error_both_directions(self) -> None:
        pred = ["I", "R"]
        ref = ["S", "I"]
        result = error_rates(pred, ref)
        assert result["minor_count"] == 2
        assert result["vme_count"] == 0
        assert result["me_count"] == 0

    def test_minor_rate_uses_total_denominator(self) -> None:
        pred = ["I", "S", "R", "R"]
        ref = ["S", "S", "R", "I"]
        result = error_rates(pred, ref)
        assert result["n_total"] == 4
        assert result["minor_count"] == 2
        assert result["minor_rate"] == pytest.approx(0.5)

    def test_no_resistant_isolates_vme_rate_zero(self) -> None:
        pred = ["S", "S"]
        ref = ["S", "S"]
        result = error_rates(pred, ref)
        assert result["n_resistant"] == 0
        assert result["vme_rate"] == pytest.approx(0.0)


class TestEssentialAgreement:
    def test_perfect_ea(self) -> None:
        meas = [20.0, 25.0, 30.0]
        ref = [20.0, 25.0, 30.0]
        assert essential_agreement(meas, ref) == pytest.approx(1.0)

    def test_partial_ea(self) -> None:
        meas = [20.0, 25.0, 30.0]
        ref = [21.0, 27.5, 31.0]
        assert essential_agreement(meas, ref) == pytest.approx(2 / 3)

    def test_boundary_exactly_2mm_is_within_ea(self) -> None:
        assert essential_agreement([20.0], [22.0]) == pytest.approx(1.0)
        assert essential_agreement([22.0], [20.0]) == pytest.approx(1.0)

    def test_just_outside_2mm_fails_ea(self) -> None:
        assert essential_agreement([20.0], [22.1]) == pytest.approx(0.0)

    def test_custom_margin(self) -> None:
        meas = [20.0, 25.0]
        ref = [23.0, 28.0]
        assert essential_agreement(meas, ref, margin_mm=3.0) == pytest.approx(1.0)
        assert essential_agreement(meas, ref, margin_mm=2.0) == pytest.approx(0.0)


class TestZoneDiameterStats:
    def test_perfect_measurement_mae_zero(self) -> None:
        stats = zone_diameter_stats([20.0, 25.0, 30.0], [20.0, 25.0, 30.0])
        assert stats["mae_mm"] == pytest.approx(0.0)
        assert stats["pearson_r"] == pytest.approx(1.0)

    def test_known_mae(self) -> None:
        meas = [20.0, 22.0, 24.0]
        ref = [21.0, 22.0, 26.0]
        stats = zone_diameter_stats(meas, ref)
        assert stats["mae_mm"] == pytest.approx(1.0)

    def test_perfect_linear_shift_gives_r_one(self) -> None:
        meas = [10.0, 20.0, 30.0, 40.0]
        ref = [12.0, 22.0, 32.0, 42.0]
        stats = zone_diameter_stats(meas, ref)
        assert stats["pearson_r"] == pytest.approx(1.0)

    def test_single_measurement_raises(self) -> None:
        with pytest.raises(ValueError, match="2 measurements"):
            zone_diameter_stats([20.0], [20.0])


class TestSirConfusionMatrix:
    def test_perfect_prediction_is_identity(self) -> None:
        cm = sir_confusion_matrix(["S", "I", "R"], ["S", "I", "R"])
        assert cm.shape == (3, 3)
        np.testing.assert_array_equal(cm, np.eye(3, dtype=int))

    def test_all_predicted_as_s(self) -> None:
        cm = sir_confusion_matrix(["S", "S", "S"], ["S", "I", "R"])
        assert cm[0, 0] == 1
        assert cm[1, 0] == 1
        assert cm[2, 0] == 1

    def test_row_order_is_reference(self) -> None:
        cm = sir_confusion_matrix(["R"], ["S"])
        assert cm[0, 2] == 1, "Reference S predicted R should be in row 0, col 2"


class TestPerClassMetrics:
    def test_perfect_all_f1_one(self) -> None:
        metrics = per_class_metrics(["S", "I", "R", "S"], ["S", "I", "R", "S"])
        for cat in ("S", "I", "R"):
            assert metrics[cat]["f1"] == pytest.approx(1.0)

    def test_zero_support_class_returns_zero_f1(self) -> None:
        metrics = per_class_metrics(["S", "R", "S"], ["S", "R", "R"])
        assert metrics["I"]["support"] == 0
        assert metrics["I"]["f1"] == pytest.approx(0.0)


class TestOverallAccuracy:
    def test_all_correct(self) -> None:
        assert overall_accuracy(["S", "I", "R"], ["S", "I", "R"]) == pytest.approx(1.0)

    def test_all_wrong(self) -> None:
        assert overall_accuracy(["R", "S", "S"], ["S", "R", "R"]) == pytest.approx(0.0)


class TestCollectMetrics:
    def test_perfect_case_full_metrics(self) -> None:
        pred = ["S", "S", "R", "R", "I"]
        ref = ["S", "S", "R", "R", "I"]
        meas = [24.0, 25.0, 16.0, 15.0, 21.0]
        ref_d = [24.0, 25.0, 16.0, 15.0, 21.0]
        m = collect_metrics(pred, ref, meas, ref_d)
        assert m["categorical_agreement"] == pytest.approx(1.0)
        assert m["accuracy"] == pytest.approx(1.0)
        assert m["error_rates"]["vme_count"] == 0
        assert m["error_rates"]["me_count"] == 0
        assert m["essential_agreement"] == pytest.approx(1.0)
        assert m["zone_stats"]["mae_mm"] == pytest.approx(0.0)
        assert len(m["confusion_matrix"]) == 3

    def test_known_vme_appears_in_collect(self) -> None:
        pred = ["S", "S"]
        ref = ["R", "S"]
        m = collect_metrics(pred, ref)
        assert m["error_rates"]["vme_count"] == 1

    def test_mismatched_diameter_args_raises(self) -> None:
        with pytest.raises(ValueError):
            collect_metrics(["S"], ["S"], measured_mm=[20.0], reference_mm=None)


def _sample_metrics() -> dict:
    pred = ["S", "S", "R", "R", "I", "S", "R"]
    ref = ["S", "R", "R", "S", "I", "S", "R"]
    meas = [24.0, 25.0, 16.0, 15.0, 21.0, 23.0, 17.0]
    ref_d = [24.0, 24.5, 16.0, 15.5, 21.0, 23.0, 17.0]
    return collect_metrics(pred, ref, meas, ref_d)


class TestGenerateMarkdown:
    def test_contains_ca_section(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Categorical Agreement" in md

    def test_contains_vme_row(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Very Major Error" in md
        assert "Predicted S, reference R" in md

    def test_contains_me_row(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Major Error (ME)" in md
        assert "Predicted R, reference S" in md

    def test_contains_ea_when_diameters_provided(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Essential Agreement" in md

    def test_contains_confusion_matrix(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Confusion Matrix" in md

    def test_contains_per_class_section(self) -> None:
        md = generate_markdown(_sample_metrics())
        assert "Per-Class Metrics" in md

    def test_no_diameter_sections_without_data(self) -> None:
        m = collect_metrics(["S", "R"], ["S", "R"])
        md = generate_markdown(m)
        assert "Essential Agreement" not in md
        assert "MAE" not in md


class TestGenerateHtml:
    def test_is_valid_html_structure(self) -> None:
        html = generate_html(_sample_metrics())
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "<table>" in html

    def test_contains_vme_definition(self) -> None:
        html = generate_html(_sample_metrics())
        assert "Predicted S, reference R" in html


class TestSaveReport:
    def test_markdown_file_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_report(_sample_metrics(), Path(tmp), formats=["markdown"])
            assert len(paths) == 1
            assert paths[0].suffix == ".md"
            assert paths[0].exists()
            content = paths[0].read_text(encoding="utf-8")
            assert "BacterioScope" in content

    def test_html_file_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_report(_sample_metrics(), Path(tmp), formats=["html"])
            assert len(paths) == 1
            assert paths[0].suffix == ".html"
            assert "<!DOCTYPE html>" in paths[0].read_text(encoding="utf-8")

    def test_both_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_report(_sample_metrics(), Path(tmp), formats=["markdown", "html"])
            assert len(paths) == 2

    def test_unknown_format_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="Unsupported"):
                save_report(_sample_metrics(), Path(tmp), formats=["pdf"])
