"""Tests for agent.evidence: assembling the deterministic report base."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bacterioscope.agent.contract import normalize_ast_observations
from bacterioscope.agent.evidence import assemble_evidence, collect_evidence_ids
from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.rules import (
    ASTObservation,
    ExpertRule,
    RuleCondition,
    RuleReference,
    RuleType,
    evaluate_expert_rules,
)
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


def _result(classifications: list[SusceptibilityResult]) -> AnalysisResult:
    n = len(classifications)
    return AnalysisResult(
        image_path="/tmp/test.jpg", plate_diameter_px=900.0, px_per_mm=10.0,
        disks=[_disk(i) for i in range(n)],
        zones=[_zone(i, c.zone_diameter_mm) for i, c in enumerate(classifications)],
        classifications=classifications,
        flags=[[] for _ in range(n)],
        breakpoint_table_version="CLSI M100-Ed33 2023",
        analysis_id="abc123", software_version="0.1.0", commit_hash="deadbee",
        image_sha256="x" * 64,
    )


def _fixture_rule(rule_type: RuleType, *, suppress_antibiotics: tuple[str, ...] = ()) -> ExpertRule:
    return ExpertRule(
        rule_id=f"test-only.{rule_type.value}",
        rule_type=rule_type,
        organisms=("Synthetic organism",),
        conditions=(RuleCondition("CIPROFLOXACIN", ("R",)),),
        reference=RuleReference(
            source_id="synthetic-fixture",
            citation="Synthetic unit-test fixture; not a clinical source",
            url="https://example.test/synthetic-fixture",
            standard="CLSI M100-Ed33 2023",
            reuse_status="authorized",
            reviewer="test fixture",
            reviewed_on="2026-10-08",
            source_locator="Synthetic test fixture section",
            reuse_evidence="Test fixture only; not clinical content",
        ),
        status="approved",
        finding_code=f"test_{rule_type.value}",
        phenotype_label="observed_pattern" if rule_type is RuleType.PHENOTYPE else None,
        suppress_antibiotics=suppress_antibiotics,
    )


def _evaluation_with_finding(rule_type: RuleType, **kwargs: object):
    rule = _fixture_rule(rule_type, **kwargs)  # type: ignore[arg-type]
    return evaluate_expert_rules(
        organism="Synthetic organism",
        standard="CLSI M100-Ed33 2023",
        observations=[ASTObservation(antibiotic_code="ciprofloxacin", category="R")],
        rules=[rule],
    )


def _empty_evaluation(rule_type: RuleType):
    return evaluate_expert_rules(
        organism="Synthetic organism", standard="CLSI M100-Ed33 2023",
        observations=[], rules=[],
    )


def _load_schema() -> dict:
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "contracts" / "agent-review-v1.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestAssembleEvidence:
    def test_shape_validates_against_the_real_schema(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        candidate = dict(base)
        candidate.update(status="grounded_report", model_explanation="ok", fallback_reason=None)
        jsonschema.validate(candidate, _load_schema())

    def test_findings_carry_their_own_standard(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_evaluation_with_finding(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        assert len(base["rule_findings"]) == 1
        assert base["rule_findings"][0]["standard"] == "CLSI M100-Ed33 2023"

    def test_cascade_suppressions_are_deduplicated_and_sorted(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        cascade = _evaluation_with_finding(
            RuleType.CASCADE, suppress_antibiotics=("B", "A", "A")
        )
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=cascade, rule_standard="CLSI M100-Ed33 2023",
        )
        assert base["cascade_suppressions"] == ["A", "B"]

    def test_esbl_screen_is_none_by_default(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        assert base["esbl_screen"] is None

    def test_traceability_comes_from_the_result(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        assert base["traceability"]["commit_hash"] == "deadbee"
        assert base["analysis_id"] == "abc123"


class TestCollectEvidenceIds:
    def test_collects_finding_source_ids(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_evaluation_with_finding(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        assert collect_evidence_ids(base) == {"synthetic-fixture"}

    def test_empty_report_has_no_citeable_ids(self) -> None:
        result = _result([_cls("ciprofloxacin", 26.0, "S")])
        normalized = normalize_ast_observations(result)
        base = assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
        )
        assert collect_evidence_ids(base) == set()


def test_esbl_screen_without_standard_raises() -> None:
    from bacterioscope.rules import ESBLScreenResult

    result = _result([_cls("ciprofloxacin", 26.0, "S")])
    normalized = normalize_ast_observations(result)
    screen = ESBLScreenResult(status="not_applicable", screen_signal=None)
    with pytest.raises(ValueError, match="esbl_standard"):
        assemble_evidence(
            result, organism="Escherichia coli", measurement=normalized.measurement,
            intrinsic=_empty_evaluation(RuleType.INTRINSIC_RESISTANCE),
            phenotype=_empty_evaluation(RuleType.PHENOTYPE),
            cascade=_empty_evaluation(RuleType.CASCADE),
            rule_standard="CLSI M100-Ed33 2023",
            esbl_screen=screen,
            esbl_standard=None,
        )
