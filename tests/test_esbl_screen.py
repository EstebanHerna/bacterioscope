"""ESBL screen mechanics; clinical catalog remains draft and unavailable."""

from __future__ import annotations

import pytest

from bacterioscope.rules import (
    ED36_STANDARD,
    ESBLScreenContext,
    RuleReference,
    ScreeningCriterion,
    ZoneObservation,
    evaluate_esbl_screen,
    load_esbl_screen_catalog,
)


def _context(**overrides) -> ESBLScreenContext:
    values = {
        "method": "disk diffusion",
        "medium": "MHA",
        "temperature_c": 35,
        "incubation_hours": 17,
        "atmosphere": "ambient air",
        "standard_disk_diffusion_procedure": True,
    }
    values.update(overrides)
    return ESBLScreenContext(**values)


def _criterion(*, status: str = "approved") -> ScreeningCriterion:
    return ScreeningCriterion(
        rule_id="synthetic.esbl.screen",
        version="1.0.0",
        organisms=("Synthetic organism",),
        antibiotic_code="test-drug",
        disk_potency_ug=30,
        maximum_zone_mm=22,
        standard="TEST STANDARD 1",
        status=status,
        reference=RuleReference(
            source_id="synthetic-fixture",
            citation="Synthetic unit test only; not a clinical source",
            url="https://example.test/synthetic",
            standard="TEST STANDARD 1",
            reuse_status="authorized",
            reviewer="test fixture",
            reviewed_on="2026-10-08",
            source_locator="Synthetic test fixture",
            reuse_evidence="Synthetic test fixture only",
        ),
    )


def test_ed36_esbl_candidates_are_draft_and_unavailable() -> None:
    criteria = load_esbl_screen_catalog()
    result = evaluate_esbl_screen(
        organism="Klebsiella pneumoniae",
        standard=ED36_STANDARD,
        context=_context(),
        observations=[ZoneObservation("ceftazidime", 30, 20, True)],
    )

    assert len(criteria) == 8
    assert all(item.status == "draft" and not item.enabled for item in criteria)
    assert result.status == "screen_rules_unavailable"
    assert result.screen_signal is None
    assert result.catalog_status == "rules_not_enabled_for_standard_or_review"
    assert result.source_id == "CLSI-M100-Ed36-2026"
    assert result.source_locator == (
        "Table 3A, disk-diffusion screening criteria, printed p. 155; "
        "method conditions on printed pp. 154-155."
    )


def test_ed36_screen_threshold_transcription_matches_table_3a() -> None:
    criteria = load_esbl_screen_catalog()
    actual = {
        (organism, item.antibiotic_code, item.disk_potency_ug): item.maximum_zone_mm
        for item in criteria
        for organism in item.organisms
    }
    common_organisms = (
        "Klebsiella pneumoniae",
        "Klebsiella oxytoca",
        "Escherichia coli",
    )
    expected = {
        (organism, "cefpodoxime", 10): 17
        for organism in common_organisms
    }
    for organism in common_organisms:
        expected.update(
            {
                (organism, "ceftazidime", 30): 22,
                (organism, "aztreonam", 30): 27,
                (organism, "cefotaxime", 30): 27,
                (organism, "ceftriaxone", 30): 25,
            }
        )
    expected.update(
        {
            ("Proteus mirabilis", "cefpodoxime", 10): 22,
            ("Proteus mirabilis", "ceftazidime", 30): 22,
            ("Proteus mirabilis", "cefotaxime", 30): 27,
        }
    )

    assert actual == expected


def test_synthetic_screen_uses_inclusive_threshold_and_never_rewrites_ast() -> None:
    criterion = _criterion()
    at_threshold = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(),
        observations=[ZoneObservation("test-drug", 30, 22, True)],
        criteria=[criterion],
    )
    above_threshold = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(),
        observations=[ZoneObservation("test-drug", 30, 22.1, True)],
        criteria=[criterion],
    )

    assert at_threshold.status == "screen_signal_for_review"
    assert at_threshold.screen_signal is True
    assert at_threshold.matches[0].zone_mm == 22
    assert above_threshold.status == "no_signal_observed"
    assert above_threshold.screen_signal is False
    assert not hasattr(at_threshold, "category")


@pytest.mark.parametrize(
    ("overrides", "expected_gap"),
    [
        ({"method": "broth microdilution"}, "method"),
        ({"medium": "blood agar"}, "medium"),
        ({"temperature_c": 32.9}, "temperature_c"),
        ({"temperature_c": 37.1}, "temperature_c"),
        ({"incubation_hours": 15.9}, "incubation_hours"),
        ({"incubation_hours": 18.1}, "incubation_hours"),
        ({"atmosphere": "CO2"}, "atmosphere"),
        ({"standard_disk_diffusion_procedure": False}, "standard_disk_diffusion_procedure"),
    ],
)
def test_context_must_match_disk_diffusion_conditions(overrides, expected_gap) -> None:
    result = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(**overrides),
        observations=[ZoneObservation("test-drug", 30, 18, True)],
        criteria=[_criterion()],
    )

    assert result.status == "assay_context_incomplete"
    assert result.screen_signal is None
    assert expected_gap in result.skipped_rule_ids


@pytest.mark.parametrize(("temperature", "hours"), [(33, 16), (37, 18)])
def test_context_accepts_m100_incubation_boundaries(temperature, hours) -> None:
    result = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(temperature_c=temperature, incubation_hours=hours),
        observations=[ZoneObservation("test-drug", 30, 30, True)],
        criteria=[_criterion()],
    )

    assert result.status == "no_signal_observed"
    assert result.catalog_status == "rules_available"


def test_unknown_or_wrong_potency_disk_does_not_count_as_a_negative_screen() -> None:
    for observation in (
        ZoneObservation("unknown-drug", 30, 18, True),
        ZoneObservation("test-drug", 10, 18, True),
    ):
        result = evaluate_esbl_screen(
            organism="Synthetic organism",
            standard="TEST STANDARD 1",
            context=_context(),
            observations=[observation],
            criteria=[_criterion()],
        )
        assert result.status == "no_usable_matching_measurements"
        assert result.screen_signal is None
        assert result.missing_rule_ids == ("synthetic.esbl.screen",)


def test_quality_rejected_measurement_is_not_evaluated() -> None:
    result = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(),
        observations=[ZoneObservation("test-drug", 30, 18, False)],
        criteria=[_criterion()],
    )

    assert result.status == "no_usable_matching_measurements"
    assert result.screen_signal is None
    assert result.quality_rejected_rule_ids == ("synthetic.esbl.screen",)


def test_draft_synthetic_criterion_fails_closed() -> None:
    result = evaluate_esbl_screen(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        context=_context(),
        observations=[ZoneObservation("test-drug", 30, 18, True)],
        criteria=[_criterion(status="draft")],
    )

    assert result.status == "screen_rules_unavailable"
    assert result.screen_signal is None


def test_wrong_edition_never_applies_ed36_screening_criteria() -> None:
    result = evaluate_esbl_screen(
        organism="Klebsiella pneumoniae",
        standard="CLSI M100-Ed33 2023",
        context=_context(),
        observations=[ZoneObservation("ceftazidime", 30, 18, True)],
    )

    assert result.status == "no_applicable_screen_rules"
    assert result.screen_signal is None


def test_duplicate_disk_observations_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate zone observation"):
        evaluate_esbl_screen(
            organism="Synthetic organism",
            standard="TEST STANDARD 1",
            context=_context(),
            observations=[
                ZoneObservation("test-drug", 30, 18, True),
                ZoneObservation("TEST-DRUG", 30, 20, True),
            ],
            criteria=[_criterion()],
        )


def test_zone_observation_rejects_nonfinite_or_invalid_measurements() -> None:
    with pytest.raises(ValueError, match="zone_mm"):
        ZoneObservation("test-drug", 30, float("nan"), True)
    with pytest.raises(ValueError, match="disk_potency"):
        ZoneObservation("test-drug", True, 18, True)
