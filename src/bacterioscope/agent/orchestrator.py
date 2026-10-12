"""End-to-end agent review: pipeline -> rule tools -> Nemotron -> validated report.

Ties together every module in this package per docs/AGENT_ARCHITECTURE.md.
The only piece that needs real Token Factory credentials is the
TokenFactoryClient passed in; everything upstream of the model call is
deterministic and independently tested.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

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
from bacterioscope.rules import (
    apply_cascade_reporting,
    check_intrinsic_resistance,
    evaluate_phenotype_rules,
)

if TYPE_CHECKING:
    from bacterioscope.integrations.tavily import PublicAlert
    from bacterioscope.pipeline import AnalysisResult

# Not a credential -- a fixed fallback_reason enum value; bandit's hardcoded
# password heuristic matches the "token..." substring.
_TOKEN_FACTORY_UNAVAILABLE_REASON = "token_factory_unavailable"  # nosec B105

_SYSTEM_PROMPT = (
    "You are reviewing a Kirby-Bauer antimicrobial susceptibility report for "
    "a clinical microbiologist. You are given deterministic evidence as JSON: "
    "measured zones, S/I/R categories, sourced rule findings, an optional "
    "ESBL screen signal, and optional public-health alerts. Write a short, "
    "plain explanation of what the evidence shows. You may only cite ids "
    "from the 'citeable_evidence_ids' list given to you. Respond with ONLY "
    'a JSON object: {"explanation": str, "evidence_ids": [str, ...]}. Never '
    "invent a measurement, category, or finding not present in the evidence."
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


def review_plate(
    result: AnalysisResult,
    *,
    organism: str,
    client: TokenFactoryClient,
    public_alerts: Sequence[PublicAlert] = (),
) -> ValidationResult:
    """Run the full agent review for one completed pipeline analysis.

    Does not run the ESBL screen: the pipeline does not yet capture disk
    potency (micrograms) per antibiotic, which ``evaluate_esbl_screen``
    requires, so ``esbl_screen`` is always None in this build (see
    agent/evidence.py's docstring for the same note).

    Args:
        result: Completed AnalysisResult, after any antibiotic assignment.
        organism: CLSI organism group used for classification.
        client: Configured TokenFactoryClient.
        public_alerts: Optional Tavily PublicAlert results to ground the
            explanation in, already restricted to an official domain.

    Returns:
        ValidationResult with status 'grounded_report' when the model call
        and validation both succeed, 'fallback' otherwise -- including when
        the client is not configured or the request fails. This function
        never raises for a Token Factory failure, only for a programming
        error in the evidence assembly itself.
    """
    normalized = normalize_ast_observations(result)
    standard = result.breakpoint_table_version

    intrinsic = check_intrinsic_resistance(
        organism=organism, standard=standard, observations=normalized.observations
    )
    phenotype = evaluate_phenotype_rules(
        organism=organism, standard=standard, observations=normalized.observations
    )
    cascade = apply_cascade_reporting(
        organism=organism, standard=standard, observations=normalized.observations
    )

    deterministic_base = assemble_evidence(
        result,
        organism=organism,
        measurement=normalized.measurement,
        intrinsic=intrinsic,
        phenotype=phenotype,
        cascade=cascade,
        rule_standard=standard,
        public_alerts=public_alerts,
    )
    evidence_ids = collect_evidence_ids(deterministic_base)

    tier = select_escalation_tier([intrinsic, phenotype, cascade], esbl_screen_signal=None)
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
