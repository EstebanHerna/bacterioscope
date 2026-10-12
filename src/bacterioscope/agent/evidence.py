"""Assemble the deterministic report base from the pipeline and rule tools.

Implements the "assemble_evidence" node from docs/AGENT_ARCHITECTURE.md: takes
pipeline output, rule-tool outputs, and optional public alerts, and returns
every agent-review-v1 field except ``status``, ``model_explanation`` and
``fallback_reason`` -- the three fields ``validate_and_render`` fills in from
the model's (untrusted) response. Nothing here ever reads from the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from bacterioscope.agent.contract import MeasurementObservation, build_measurement_section
from bacterioscope.rules import ESBLScreenResult, RuleEvaluation

if TYPE_CHECKING:
    from bacterioscope.integrations.tavily import PublicAlert
    from bacterioscope.pipeline import AnalysisResult

SCHEMA_VERSION = "1.0"


def _map_rule_evaluation(evaluation: RuleEvaluation, standard: str) -> list[dict[str, Any]]:
    return [
        {
            "rule_type": finding.rule_type.value,
            "rule_id": finding.rule_id,
            "rule_version": finding.rule_version,
            "standard": standard,
            "code": finding.code,
            "phenotype_label": finding.phenotype_label,
            "observed_codes": list(finding.observed_codes),
            "source_id": finding.source_id,
            "citation": finding.citation,
            "source_url": finding.source_url,
        }
        for finding in evaluation.findings
    ]


def _map_esbl_screen(
    result: ESBLScreenResult | None, standard: str | None
) -> dict[str, Any] | None:
    if result is None:
        return None
    if standard is None:
        raise ValueError("esbl_standard is required when esbl_screen is not None")
    return {
        "status": result.status,
        "screen_signal": result.screen_signal,
        "standard": standard,
        "matches": [
            {
                "rule_id": match.rule_id,
                "antibiotic_code": match.antibiotic_code,
                "zone_mm": match.zone_mm,
                "maximum_zone_mm": match.maximum_zone_mm,
                "source_id": match.source_id,
                "citation": match.citation,
                "source_url": match.source_url,
            }
            for match in result.matches
        ],
        "coverage_complete": result.coverage_complete,
        "catalog_status": result.catalog_status,
        "source_id": result.source_id,
        "citation": result.citation,
        "source_url": result.source_url,
    }


def _map_alerts(alerts: Sequence[PublicAlert]) -> list[dict[str, Any]]:
    return [
        {
            "source": alert.source,
            "title": alert.title,
            "url": alert.url,
            "snippet": alert.snippet,
            "published_date": alert.published_date,
        }
        for alert in alerts
    ]


def assemble_evidence(
    result: AnalysisResult,
    *,
    organism: str,
    measurement: tuple[MeasurementObservation, ...],
    intrinsic: RuleEvaluation,
    phenotype: RuleEvaluation,
    cascade: RuleEvaluation,
    rule_standard: str,
    esbl_screen: ESBLScreenResult | None = None,
    esbl_standard: str | None = None,
    public_alerts: Sequence[PublicAlert] = (),
    alert_search_status: str = "not_requested",
) -> dict[str, Any]:
    """Build the deterministic agent-review-v1 report base.

    Args:
        result: Completed AnalysisResult from the pipeline.
        organism: CLSI organism group used for classification.
        measurement: Per-disk tuple from
            ``agent.contract.normalize_ast_observations()``.
        intrinsic: RuleEvaluation from ``check_intrinsic_resistance()``.
        phenotype: RuleEvaluation from ``evaluate_phenotype_rules()``.
        cascade: RuleEvaluation from ``apply_cascade_reporting()``.
        rule_standard: The CLSI standard string passed to the three rule
            tool calls above -- independent of ``esbl_standard`` (dual-
            edition decision, docs/TEAM_EXECUTION_PLAN.md).
        esbl_screen: Optional ESBLScreenResult from ``evaluate_esbl_screen()``.
            None when the caller did not provide typed disk potency and assay
            context. The pipeline does not yet capture disk potency per
            antibiotic, so callers must supply those fields explicitly.
        esbl_standard: Required when ``esbl_screen`` is not None; the
            standard it was evaluated against (e.g. ``ED36_STANDARD``).
        public_alerts: Optional Tavily ``PublicAlert`` results.
        alert_search_status: Whether public-alert search was requested and
            whether eligible results were available.

    Returns:
        A dict matching every agent-review-v1 field except ``status``,
        ``model_explanation`` and ``fallback_reason``.
    """
    findings = [
        *_map_rule_evaluation(intrinsic, rule_standard),
        *_map_rule_evaluation(phenotype, rule_standard),
        *_map_rule_evaluation(cascade, rule_standard),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": result.analysis_id,
        "organism": organism,
        "measurement": build_measurement_section(result, measurement),
        "rule_standard": rule_standard,
        "rule_findings": findings,
        "cascade_suppressions": sorted(set(cascade.suppressed_antibiotics)),
        "esbl_screen": _map_esbl_screen(esbl_screen, esbl_standard),
        "public_alerts": _map_alerts(public_alerts),
        "alert_search_status": alert_search_status,
        "catalog_status": {
            "intrinsic_resistance": intrinsic.catalog_status,
            "phenotype": phenotype.catalog_status,
            "cascade": cascade.catalog_status,
        },
        "requires_human_review": True,
        "traceability": {
            "software_version": result.software_version,
            "commit_hash": result.commit_hash,
            "image_sha256": result.image_sha256,
        },
    }


def collect_evidence_ids(deterministic_base: dict[str, Any]) -> set[str]:
    """Collect every id the model is allowed to cite in ``model_explanation``.

    Includes each rule finding's ``source_id``, the ESBL screen's own
    ``source_id`` plus each of its matches' ``source_id`` (if the screen
    ran), and every public alert's ``url`` -- everything in the report with
    a real citation behind it.

    Args:
        deterministic_base: The dict returned by ``assemble_evidence()``.

    Returns:
        The set of citeable ids/urls for this report.
    """
    ids: set[str] = set()
    for finding in deterministic_base["rule_findings"]:
        ids.add(finding["source_id"])
    esbl = deterministic_base.get("esbl_screen")
    if esbl is not None:
        if esbl.get("source_id"):
            ids.add(esbl["source_id"])
        for match in esbl["matches"]:
            ids.add(match["source_id"])
    for alert in deterministic_base["public_alerts"]:
        ids.add(alert["url"])
    return ids
