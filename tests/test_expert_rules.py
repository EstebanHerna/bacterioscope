"""Mechanics tests for the rule engine; fixtures are synthetic, not clinical guidance."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from bacterioscope.rules import (
    ASTObservation,
    ExpertRule,
    RuleCondition,
    RuleReference,
    RuleType,
    apply_cascade_reporting,
    check_intrinsic_resistance,
    evaluate_expert_rules,
    evaluate_phenotype_rules,
    load_builtin_clsi_rules,
    load_rule_catalog,
)


def _fixture_rule(
    rule_type: RuleType,
    *,
    conditions: tuple[RuleCondition, ...] | None = None,
    phenotype_label: str | None = None,
    suppress_antibiotics: tuple[str, ...] = (),
) -> ExpertRule:
    return ExpertRule(
        rule_id=f"test-only.{rule_type.value}",
        rule_type=rule_type,
        organisms=("Synthetic organism",),
        conditions=conditions or (RuleCondition("TEST1", ("R",)),),
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


def test_bundled_clsi_catalog_is_empty_until_approved_content_exists() -> None:
    assert load_builtin_clsi_rules() == ()


def test_ed36_catalog_is_available_for_review_but_every_rule_is_draft() -> None:
    rules = load_builtin_clsi_rules("CLSI M100-Ed36 2026")

    assert len(rules) == 5
    assert {rule.reference.standard for rule in rules} == {"CLSI M100-Ed36 2026"}
    assert all(rule.status == "draft" and not rule.enabled for rule in rules)


def test_ed36_rule_tool_fails_closed_until_reviewed() -> None:
    result = check_intrinsic_resistance(
        organism="Klebsiella pneumoniae",
        standard="CLSI M100-Ed36 2026",
        observations=[ASTObservation("ampicillin", "S")],
    )

    assert result.findings == ()
    assert "CLSI-M100-ED36-APPB-KLEBSIELLA-AMPICILLIN" in result.skipped_rule_ids
    assert result.catalog_status == "rules_not_enabled_for_standard_or_review"


def test_unknown_clsi_edition_has_no_catalog() -> None:
    with pytest.raises(ValueError, match="no bundled CLSI rule catalog"):
        load_builtin_clsi_rules("CLSI M100-Ed99 2099")


def test_each_tool_reports_empty_catalog_as_unavailable() -> None:
    observations = [ASTObservation("TEST1", "R")]
    tools = (check_intrinsic_resistance, evaluate_phenotype_rules, apply_cascade_reporting)

    for tool in tools:
        result = tool(
            organism="Synthetic organism",
            standard="CLSI M100-Ed33 2023",
            observations=observations,
        )
        assert result.findings == ()
        assert result.catalog_status == "no_rules_configured"


def test_intrinsic_rule_emits_review_finding_without_rewriting_sir() -> None:
    observations = [ASTObservation("TEST1", "R")]
    result = check_intrinsic_resistance(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        observations=observations,
        rules=[_fixture_rule(RuleType.INTRINSIC_RESISTANCE)],
    )

    assert [finding.code for finding in result.findings] == ["test_intrinsic_resistance"]
    assert observations[0].category == "R"
    assert result.suppressed_antibiotics == ()


def test_phenotype_rule_requires_every_condition_and_exact_organism() -> None:
    rule = _fixture_rule(
        RuleType.PHENOTYPE,
        conditions=(
            RuleCondition("TEST1", ("R",)),
            RuleCondition("TEST2", ("I", "R")),
        ),
        phenotype_label="SYNTHETIC_PATTERN_ONLY",
    )
    incomplete = evaluate_phenotype_rules(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        observations=[ASTObservation("TEST1", "R")],
        rules=[rule],
    )
    wrong_organism = evaluate_phenotype_rules(
        organism="Other organism",
        standard="TEST STANDARD 1",
        observations=[ASTObservation("TEST1", "R"), ASTObservation("TEST2", "I")],
        rules=[rule],
    )
    matched = evaluate_phenotype_rules(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        observations=[ASTObservation("TEST1", "R"), ASTObservation("TEST2", "I")],
        rules=[rule],
    )

    assert incomplete.findings == ()
    assert wrong_organism.findings == ()
    assert matched.findings[0].phenotype_label == "SYNTHETIC_PATTERN_ONLY"


def test_cascade_rule_returns_suppression_without_changing_ast_observation() -> None:
    observations = [ASTObservation("TEST1", "R"), ASTObservation("TEST2", "S")]
    rule = _fixture_rule(
        RuleType.CASCADE,
        suppress_antibiotics=("TEST2", "TEST3"),
    )

    result = apply_cascade_reporting(
        organism="Synthetic organism",
        standard="TEST STANDARD 1",
        observations=observations,
        rules=[rule],
    )

    assert result.suppressed_antibiotics == ("TEST2", "TEST3")
    assert observations[1].category == "S"


def test_draft_unreviewed_or_wrong_standard_rules_are_skipped() -> None:
    draft = replace(_fixture_rule(RuleType.INTRINSIC_RESISTANCE), status="draft")
    pending_reference = RuleReference(
        source_id="pending",
        citation="Pending source",
        url="https://example.test/pending",
        standard="TEST STANDARD 1",
        reuse_status="pending",
    )
    unlicensed = replace(
        draft, rule_id="test-only.pending", status="approved", reference=pending_reference
    )
    wrong_edition = _fixture_rule(RuleType.INTRINSIC_RESISTANCE)

    result = evaluate_expert_rules(
        organism="Synthetic organism",
        standard="TEST STANDARD 2",
        observations=[ASTObservation("TEST1", "R")],
        rules=[draft, unlicensed, wrong_edition],
    )

    assert result.findings == ()
    assert len(result.skipped_rule_ids) == 3


def test_duplicate_observations_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate AST observation"):
        evaluate_expert_rules(
            organism="Synthetic organism",
            standard="TEST STANDARD 1",
            observations=[ASTObservation("test1", "R"), ASTObservation("TEST1", "S")],
            rules=[],
        )


def test_rule_catalog_loader_rejects_duplicate_ids(tmp_path) -> None:
    raw_rule = {
        "rule_id": "duplicate",
        "rule_type": "intrinsic_resistance",
        "organisms": ["Synthetic organism"],
        "conditions": [{"antibiotic_code": "TEST1", "categories": ["R"]}],
        "reference": {
            "source_id": "synthetic",
            "citation": "Test fixture",
            "url": "https://example.test/",
            "standard": "TEST STANDARD 1",
        },
    }
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "catalog_version": "1.0.0",
                "standard": "TEST STANDARD 1",
                "rules": [raw_rule] * 2,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate rule_id"):
        load_rule_catalog(path)
