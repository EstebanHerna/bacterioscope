"""Difficulty-based model-tier routing for the agent core.

Pure, deterministic, no network calls -- testable without Token Factory
credentials. See docs/AGENT_ARCHITECTURE.md's node table and the team's
agreed priority order: triage is cheap and fast, the grounded report needs
tool-calling reasoning, and escalation reaches for the largest model only
when the case actually looks complex or contradictory, not on every plate.
"""

from __future__ import annotations

from collections.abc import Sequence

from bacterioscope.rules import RuleEvaluation

_ESCALATION_PHENOTYPE_LABELS = frozenset({"mdr", "esbl", "possible_carbapenemase"})


def select_triage_tier() -> str:
    """Return the tier for input validation / triage calls: always 'nano'."""
    return "nano"


def select_report_tier() -> str:
    """Return the tier for the main grounded-report call: always 'super'."""
    return "super"


def select_escalation_tier(
    rule_evaluations: Sequence[RuleEvaluation], esbl_screen_signal: bool | None
) -> str | None:
    """Return 'ultra' when escalation criteria are met, else None (stay on 'super').

    Escalation criteria, from docs/AGENT_ARCHITECTURE.md's "Escalation (MDR
    or contradictory patterns)" node: a positive ESBL screen signal, a
    phenotype finding whose label suggests MDR/ESBL/carbapenemase, or more
    than one rule type producing findings at once -- a sign of a complex or
    contradictory pattern, not a single clean flag.

    Args:
        rule_evaluations: Every RuleEvaluation the Persona 2 tools returned
            for this plate (intrinsic resistance, phenotype, cascade).
        esbl_screen_signal: ESBLScreenResult.screen_signal for this plate,
            or None when the screen did not run.

    Returns:
        'ultra' if escalation applies, otherwise None.
    """
    if esbl_screen_signal:
        return "ultra"

    types_with_findings = 0
    for evaluation in rule_evaluations:
        if not evaluation.findings:
            continue
        types_with_findings += 1
        for finding in evaluation.findings:
            label = (finding.phenotype_label or "").strip().casefold()
            if label in _ESCALATION_PHENOTYPE_LABELS:
                return "ultra"

    if types_with_findings > 1:
        return "ultra"
    return None
