"""Validate a Nemotron response against the agent-review-v1 report contract.

Implements the "Persona 1 schema validator" node from
docs/AGENT_ARCHITECTURE.md. The model is only ever trusted for one field,
``model_explanation``, plus the ``evidence_ids`` it claims to cite -- every
other field in the returned report comes from ``deterministic_base``, which
the caller must assemble purely from the pipeline and the Persona 2 rule
tools. This is a structural guarantee, not a diff check: the model's raw
JSON is parsed, two fields are read out of it, and the rest of it is
discarded, so it cannot alter a measurement, category, rule finding,
citation, or suppression even if its output tries to.

Any failure (invalid JSON, a missing/empty explanation, a citation outside
the supplied evidence, or a schema violation) returns a safe fallback report
instead of raising.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "contracts" / "agent-review-v1.schema.json"
)
_EXPLANATION_MAX_LENGTH = 1500

_INVALID_JSON_REASON = "model_output_not_json"
_MALFORMED_OUTPUT_REASON = "model_output_malformed"
_UNKNOWN_EVIDENCE_REASON = "citation_not_in_evidence"
_SCHEMA_INVALID_REASON = "schema_validation_failed"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one model response against the report contract."""

    status: str
    report: dict[str, Any]
    fallback_reason: str | None


@lru_cache(maxsize=1)
def _load_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema


def _build_fallback(deterministic_base: dict[str, Any], reason: str) -> dict[str, Any]:
    fallback = dict(deterministic_base)
    fallback["status"] = "fallback"
    fallback["model_explanation"] = None
    fallback["fallback_reason"] = reason
    return fallback


def _fallback_result(deterministic_base: dict[str, Any], reason: str) -> ValidationResult:
    return ValidationResult(
        status="fallback",
        report=_build_fallback(deterministic_base, reason),
        fallback_reason=reason,
    )


def _extract_explanation_and_citations(parsed: Any) -> tuple[str, list[str]] | None:
    if not isinstance(parsed, dict):
        return None
    explanation = parsed.get("explanation")
    cited = parsed.get("evidence_ids", [])
    if not isinstance(explanation, str) or not explanation.strip():
        return None
    if not isinstance(cited, list) or not all(isinstance(c, str) for c in cited):
        return None
    return explanation.strip()[:_EXPLANATION_MAX_LENGTH], cited


def validate_and_render(
    model_output: str, *, deterministic_base: dict[str, Any], evidence_ids: set[str]
) -> ValidationResult:
    """Validate raw Nemotron output against the agent-review-v1 contract.

    Args:
        model_output: Raw text returned by the Nemotron chat completion.
            Expected to be a JSON object with at least an "explanation"
            string and an "evidence_ids" list of strings it is citing.
        deterministic_base: The report dict assembled from the pipeline and
            Persona 2 tools (``measurement``, ``rule_findings``,
            ``cascade_suppressions``, ``esbl_screen``, ``public_alerts``,
            ``catalog_status``, ``traceability``, ``analysis_id``,
            ``organism``, ``schema_version``, ``requires_human_review``),
            with ``status``/``model_explanation``/``fallback_reason`` left
            out -- this function sets those three and nothing else.
        evidence_ids: Every citeable id (rule_id, source_id, alert url,
            etc.) the model is allowed to reference in its explanation.

    Returns:
        ValidationResult with status 'grounded_report' when the model
        response is well-formed, fully cited, and the assembled report
        validates against the schema; 'fallback' otherwise, always with a
        complete, schema-shaped report and no model text.
    """
    try:
        parsed = json.loads(model_output)
    except json.JSONDecodeError:
        return _fallback_result(deterministic_base, _INVALID_JSON_REASON)

    extracted = _extract_explanation_and_citations(parsed)
    if extracted is None:
        return _fallback_result(deterministic_base, _MALFORMED_OUTPUT_REASON)
    explanation, cited = extracted

    if any(citation not in evidence_ids for citation in cited):
        return _fallback_result(deterministic_base, _UNKNOWN_EVIDENCE_REASON)

    candidate = dict(deterministic_base)
    candidate["status"] = "grounded_report"
    candidate["model_explanation"] = explanation
    candidate["fallback_reason"] = None

    try:
        jsonschema.validate(candidate, _load_schema())
    except jsonschema.ValidationError:
        return _fallback_result(deterministic_base, _SCHEMA_INVALID_REASON)

    return ValidationResult(status="grounded_report", report=candidate, fallback_reason=None)
