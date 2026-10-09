"""Tests for agent.validator.validate_and_render against the real report schema."""

from __future__ import annotations

import json

from bacterioscope.agent.validator import validate_and_render


def _deterministic_base(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1.0",
        "analysis_id": "abc123",
        "organism": "Escherichia coli",
        "measurement": {
            "standard": "CLSI M100-Ed33 2023",
            "observations": [
                {
                    "disk_index": 0, "antibiotic_code": "ciprofloxacin", "category": "S",
                    "zone_mm": 26.0, "quality_flags": [], "included_in_rule_evaluation": True,
                    "exclusion_reason": None,
                },
            ],
        },
        "rule_findings": [], "cascade_suppressions": [], "esbl_screen": None,
        "public_alerts": [],
        "catalog_status": {
            "intrinsic_resistance": "no_rules_configured",
            "phenotype": "no_rules_configured", "cascade": "no_rules_configured",
        },
        "requires_human_review": True,
        "traceability": {
            "software_version": "0.1.0", "commit_hash": "abc123", "image_sha256": "x",
        },
    }
    base.update(overrides)
    return base


class TestValidateAndRenderSuccess:
    def test_well_formed_response_is_grounded(self) -> None:
        output = json.dumps({"explanation": "No concerning findings.", "evidence_ids": []})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.status == "grounded_report"
        assert result.report["model_explanation"] == "No concerning findings."
        assert result.report["fallback_reason"] is None
        assert result.fallback_reason is None

    def test_citations_within_evidence_are_accepted(self) -> None:
        output = json.dumps({"explanation": "See rule.", "evidence_ids": ["rule-001"]})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids={"rule-001", "rule-002"}
        )
        assert result.status == "grounded_report"

    def test_explanation_is_trimmed(self) -> None:
        output = json.dumps({"explanation": "  padded  ", "evidence_ids": []})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.report["model_explanation"] == "padded"


class TestValidateAndRenderFallback:
    def test_invalid_json_falls_back(self) -> None:
        result = validate_and_render(
            "not json{{", deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.status == "fallback"
        assert result.fallback_reason == "model_output_not_json"
        assert result.report["model_explanation"] is None
        assert result.report["status"] == "fallback"

    def test_missing_explanation_key_falls_back(self) -> None:
        output = json.dumps({"evidence_ids": []})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.fallback_reason == "model_output_malformed"

    def test_empty_explanation_falls_back(self) -> None:
        output = json.dumps({"explanation": "   ", "evidence_ids": []})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.fallback_reason == "model_output_malformed"

    def test_non_string_citation_falls_back(self) -> None:
        output = json.dumps({"explanation": "ok", "evidence_ids": [1, 2]})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids=set()
        )
        assert result.fallback_reason == "model_output_malformed"

    def test_citation_outside_evidence_falls_back(self) -> None:
        output = json.dumps({"explanation": "ok", "evidence_ids": ["made-up-id"]})
        result = validate_and_render(
            output, deterministic_base=_deterministic_base(), evidence_ids={"rule-001"}
        )
        assert result.fallback_reason == "citation_not_in_evidence"

    def test_incomplete_deterministic_base_falls_back_on_schema(self) -> None:
        incomplete = _deterministic_base()
        del incomplete["traceability"]
        output = json.dumps({"explanation": "ok", "evidence_ids": []})
        result = validate_and_render(output, deterministic_base=incomplete, evidence_ids=set())
        assert result.fallback_reason == "schema_validation_failed"

    def test_fallback_report_still_has_every_other_field(self) -> None:
        output = "not json{{"
        base = _deterministic_base()
        result = validate_and_render(output, deterministic_base=base, evidence_ids=set())
        assert result.report["analysis_id"] == base["analysis_id"]
        assert result.report["measurement"] == base["measurement"]

    def test_model_cannot_overwrite_other_fields(self) -> None:
        tampered = json.dumps({
            "explanation": "ok", "evidence_ids": [],
            "measurement": {"standard": "FAKE", "observations": []},
            "requires_human_review": False,
        })
        base = _deterministic_base()
        result = validate_and_render(tampered, deterministic_base=base, evidence_ids=set())
        assert result.report["measurement"] == base["measurement"]
        assert result.report["requires_human_review"] is True
