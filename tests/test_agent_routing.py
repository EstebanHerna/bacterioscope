"""Tests for agent.routing: pure, deterministic tier selection."""

from __future__ import annotations

from bacterioscope.agent.routing import (
    select_escalation_tier,
    select_report_tier,
    select_triage_tier,
)
from bacterioscope.rules import (
    ASTObservation,
    ExpertRule,
    RuleCondition,
    RuleReference,
    RuleType,
    evaluate_expert_rules,
)


def _fixture_rule(
    rule_type: RuleType,
    *,
    phenotype_label: str | None = None,
    suppress_antibiotics: tuple[str, ...] = (),
) -> ExpertRule:
    return ExpertRule(
        rule_id=f"test-only.{rule_type.value}",
        rule_type=rule_type,
        organisms=("Synthetic organism",),
        conditions=(RuleCondition("TEST1", ("R",)),),
        reference=RuleReference(
            source_id="synthetic-fixture",
            citation="Synthetic unit-test fixture; not a clinical source",
            url="https://example.test/synthetic-fixture",
            standard="TEST STANDARD 1",
            reuse_status="authorized",
            reviewer="test fixture",
            reviewed_on="2026-10-08",
            source_locator="Synthetic test fixture section",
            reuse_evidence="Test fixture only; not clinical content",
        ),
        status="approved",
        finding_code=f"test_{rule_type.value}",
        phenotype_label=phenotype_label,
        suppress_antibiotics=suppress_antibiotics,
    )


def _evaluation(rule_type: RuleType, phenotype_label: str | None = None):
    rule = _fixture_rule(
        rule_type,
        phenotype_label=phenotype_label,
        suppress_antibiotics=("TEST2",) if rule_type is RuleType.CASCADE else (),
    )
    return evaluate_expert_rules(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        observations=[ASTObservation(antibiotic_code="TEST1", category="R")],
        rules=[rule],
    )


class TestFixedTiers:
    def test_triage_is_always_nano(self) -> None:
        assert select_triage_tier() == "nano"

    def test_report_is_always_super(self) -> None:
        assert select_report_tier() == "super"


class TestSelectEscalationTier:
    def test_no_findings_stays_on_super(self) -> None:
        assert select_escalation_tier([], esbl_screen_signal=None) is None

    def test_positive_esbl_screen_escalates(self) -> None:
        assert select_escalation_tier([], esbl_screen_signal=True) == "ultra"

    def test_negative_esbl_screen_alone_does_not_escalate(self) -> None:
        assert select_escalation_tier([], esbl_screen_signal=False) is None

    def test_concerning_phenotype_label_escalates(self) -> None:
        evaluation = _evaluation(RuleType.PHENOTYPE, phenotype_label="ESBL")
        result = select_escalation_tier([evaluation], esbl_screen_signal=None)
        assert result == "ultra"

    def test_phenotype_label_match_is_case_insensitive(self) -> None:
        evaluation = _evaluation(RuleType.PHENOTYPE, phenotype_label="Possible_Carbapenemase")
        result = select_escalation_tier([evaluation], esbl_screen_signal=None)
        assert result == "ultra"

    def test_unconcerning_phenotype_label_alone_does_not_escalate(self) -> None:
        evaluation = _evaluation(RuleType.PHENOTYPE, phenotype_label="observed_pattern")
        result = select_escalation_tier([evaluation], esbl_screen_signal=None)
        assert result is None

    def test_multiple_rule_types_with_findings_escalates(self) -> None:
        intrinsic = _evaluation(RuleType.INTRINSIC_RESISTANCE)
        cascade = _evaluation(RuleType.CASCADE)
        result = select_escalation_tier([intrinsic, cascade], esbl_screen_signal=None)
        assert result == "ultra"

    def test_single_rule_type_with_findings_does_not_escalate(self) -> None:
        intrinsic = _evaluation(RuleType.INTRINSIC_RESISTANCE)
        result = select_escalation_tier([intrinsic], esbl_screen_signal=False)
        assert result is None
