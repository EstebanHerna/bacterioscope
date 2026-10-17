"""End-to-end agent review: pipeline -> rule tools -> Nemotron -> validated report.

Ties together every module in this package per docs/AGENT_ARCHITECTURE.md.
The only piece that needs real Token Factory credentials is the
TokenFactoryClient passed in; everything upstream of the model call is
deterministic and independently tested.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from bacterioscope.agent.contract import normalize_ast_observations
from bacterioscope.agent.evidence import assemble_evidence, collect_evidence_ids
from bacterioscope.agent.nemotron_client import (
    TokenFactoryClient,
    TokenFactoryConfigurationError,
    TokenFactoryRequestError,
)
from bacterioscope.agent.routing import select_escalation_tier, select_report_tier
from bacterioscope.agent.validator import (
    ValidationResult,
    build_fallback_result,
    validate_and_render,
)
from bacterioscope.integrations.tavily import (
    AlertSource,
    PublicAlert,
    TavilyAlertSearch,
    TavilyConfigurationError,
    TavilySearchError,
)
from bacterioscope.rules import (
    ESBLScreenContext,
    ZoneObservation,
    apply_cascade_reporting,
    check_intrinsic_resistance,
    evaluate_esbl_screen,
    evaluate_phenotype_rules,
)

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult


class AlertSearchClient(Protocol):
    """Structural type for the server-side Tavily search adapter."""

    def search_amr_alerts(self, source: AlertSource | str) -> list[PublicAlert]: ...

# Not a credential -- a fixed fallback_reason enum value; bandit's hardcoded
# password heuristic matches the "token..." substring.
_TOKEN_FACTORY_UNAVAILABLE_REASON = "token_factory_unavailable"  # nosec B105

_SYSTEM_PROMPT = (
    "You are reviewing a Kirby-Bauer antimicrobial susceptibility report for "
    "a clinical microbiologist. You are given deterministic evidence as JSON. "
    "Keep measurement classifications separate from expert-rule findings: "
    "measurement.observations[].category contains deterministic CLSI S/I/R "
    "classifications; rule_findings contains expert-rule matches. "
    "included_in_rule_evaluation=true means an observation passed input "
    "eligibility checks; it does not mean any expert rule matched. If a "
    "catalog_status value is no_rules_configured, say that rules from that "
    "catalog are unavailable. If a value is "
    "rules_not_enabled_for_standard_or_review, say that candidate rules "
    "exist but evaluation is disabled pending the standard/review gate. In "
    "either case, do not imply rules were confirmed, ruled out, or matched. "
    "Never say 'no rules matched' unless the corresponding catalog status is "
    "rules_available; that would claim an evaluation happened. If any catalog "
    "status is rules_not_enabled_for_standard_or_review and rule_findings is "
    "empty, include this exact sentence: 'Expert-rule candidates exist, but "
    "they are not enabled for evaluation under the current standard/review "
    "gate.' If every "
    "catalog_status value is "
    "no_rules_configured and rule_findings is empty, include this exact "
    "sentence: 'Expert-rule evaluation was unavailable because no expert-rule "
    "catalogs are configured.' Do not add a claim about whether rules matched. "
    "Do not infer a resistance mechanism or recommend treatment. "
    "Summarize only measurements, findings, and alerts present in the JSON. "
    "You may only cite ids from the 'citeable_evidence_ids' list given to "
    "you. Respond with ONLY a JSON object: "
    '{"explanation": str, "evidence_ids": [str, ...]}. Never invent a '
    "measurement, category, or finding."
)


def _build_messages(
    deterministic_base: dict[str, object], evidence_ids: set[str]
) -> list[dict[str, str]]:
    user_content = json.dumps({
        "evidence": deterministic_base,
        "citeable_evidence_ids": sorted(evidence_ids),
    })
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _collect_public_alerts(
    *,
    provided: Sequence[PublicAlert],
    alert_search: AlertSearchClient | None,
    alert_sources: Sequence[AlertSource | str],
) -> tuple[tuple[PublicAlert, ...], str]:
    """Optionally retrieve fixed-query INS/OPS alerts and expose availability."""
    alerts_by_url = {alert.url: alert for alert in provided}
    if not alert_sources:
        return tuple(alerts_by_url.values()), "provided" if provided else "not_requested"

    selected_sources = tuple(dict.fromkeys(AlertSource(source) for source in alert_sources))
    searcher = alert_search or TavilyAlertSearch()
    successful_searches = 0
    failed_searches = 0
    searches_with_results = 0
    for source in selected_sources:
        try:
            found = searcher.search_amr_alerts(source)
        except (TavilyConfigurationError, TavilySearchError):
            failed_searches += 1
            continue
        successful_searches += 1
        if found:
            searches_with_results += 1
        for alert in found:
            alerts_by_url.setdefault(alert.url, alert)

    if failed_searches and (searches_with_results or provided):
        status = "partial"
    elif failed_searches:
        status = "unavailable"
    elif searches_with_results:
        status = "available"
    elif successful_searches and provided:
        status = "provided"
    elif successful_searches:
        status = "no_results"
    else:
        status = "provided" if provided else "not_requested"
    return tuple(alerts_by_url.values()), status


def review_plate(
    result: AnalysisResult,
    *,
    organism: str,
    client: TokenFactoryClient,
    rule_standard: str | None = None,
    esbl_standard: str | None = None,
    esbl_context: ESBLScreenContext | None = None,
    esbl_observations: Sequence[ZoneObservation] = (),
    public_alerts: Sequence[PublicAlert] = (),
    alert_search: AlertSearchClient | None = None,
    alert_sources: Sequence[AlertSource | str] = (),
) -> ValidationResult:
    """Run the full agent review for one completed pipeline analysis.

    ``rule_standard`` is independent of the pipeline's breakpoint edition and
    must be supplied explicitly to evaluate rules against another edition.
    The ESBL screen runs only when the caller supplies an explicit
    ``esbl_standard`` and typed disk/assay observations; the pipeline itself
    does not currently capture disk potency or the full assay context.

    Args:
        result: Completed AnalysisResult, after any antibiotic assignment.
        organism: CLSI organism group used for classification.
        client: Configured TokenFactoryClient.
        rule_standard: Edition used for the expert-rule catalogs. Defaults to
            the pipeline measurement edition for backwards compatibility.
        esbl_standard: Explicit edition for the separate zone-based screen.
        esbl_context: Assay context required by the screen. If the edition is
            provided without context, an incomplete context is reported.
        esbl_observations: Exact disk codes, potencies, zones, and quality
            acceptance values for the separate ESBL screen.
        public_alerts: Optional Tavily PublicAlert results to ground the
            explanation in, already restricted to an official domain.
        alert_search: Optional server-side Tavily client. Defaults to a client
            reading ``TAVILY_API_KEY`` from the environment when sources are
            requested.
        alert_sources: Optional allowlisted sources to search, ``ins`` and/or
            ``ops``. Search failures are recorded and do not stop plate review.

    Returns:
        ValidationResult with status 'grounded_report' when the model call
        and validation both succeed, 'fallback' otherwise -- including when
        the client is not configured or the request fails. This function
        never raises for a Token Factory failure, only for a programming
        error in the evidence assembly itself.
    """
    normalized = normalize_ast_observations(result)
    selected_rule_standard = (
        result.breakpoint_table_version if rule_standard is None else rule_standard
    ).strip()
    if not selected_rule_standard:
        raise ValueError("rule_standard or result.breakpoint_table_version is required")
    if esbl_standard is None and (esbl_context is not None or esbl_observations):
        raise ValueError("esbl_standard is required when ESBL screen inputs are supplied")
    if esbl_standard is not None:
        esbl_standard = esbl_standard.strip()
        if not esbl_standard:
            raise ValueError("esbl_standard must not be empty")
    selected_alerts, alert_search_status = _collect_public_alerts(
        provided=public_alerts,
        alert_search=alert_search,
        alert_sources=alert_sources,
    )

    intrinsic = check_intrinsic_resistance(
        organism=organism, standard=selected_rule_standard,
        observations=normalized.observations,
    )
    phenotype = evaluate_phenotype_rules(
        organism=organism, standard=selected_rule_standard,
        observations=normalized.observations,
    )
    cascade = apply_cascade_reporting(
        organism=organism, standard=selected_rule_standard,
        observations=normalized.observations,
    )

    esbl_screen = None
    if esbl_standard is not None:
        context = esbl_context or ESBLScreenContext(
            method=None,
            medium=None,
            temperature_c=None,
            incubation_hours=None,
            atmosphere=None,
            standard_disk_diffusion_procedure=None,
        )
        esbl_screen = evaluate_esbl_screen(
            organism=organism,
            standard=esbl_standard,
            context=context,
            observations=esbl_observations,
        )

    deterministic_base = assemble_evidence(
        result,
        organism=organism,
        measurement=normalized.measurement,
        intrinsic=intrinsic,
        phenotype=phenotype,
        cascade=cascade,
        rule_standard=selected_rule_standard,
        esbl_screen=esbl_screen,
        esbl_standard=esbl_standard,
        public_alerts=selected_alerts,
        alert_search_status=alert_search_status,
    )
    evidence_ids = collect_evidence_ids(deterministic_base)

    tier = select_escalation_tier(
        [intrinsic, phenotype, cascade],
        esbl_screen_signal=(esbl_screen.screen_signal if esbl_screen is not None else None),
    )
    if tier is None:
        tier = select_report_tier()

    messages = _build_messages(deterministic_base, evidence_ids)

    try:
        completion = client.chat(tier, messages)
    except (TokenFactoryConfigurationError, TokenFactoryRequestError):
        return build_fallback_result(deterministic_base, _TOKEN_FACTORY_UNAVAILABLE_REASON)

    return validate_and_render(
        completion.content, deterministic_base=deterministic_base, evidence_ids=evidence_ids
    )
