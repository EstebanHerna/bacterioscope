"""Narrow, deterministic rule tools for the agent integration boundary."""

from __future__ import annotations

from collections.abc import Iterable

from bacterioscope.rules.engine import (
    ASTObservation,
    ExpertRule,
    RuleEvaluation,
    RuleType,
    evaluate_expert_rules,
    load_builtin_clsi_rules,
)


def _run_tool(
    rule_type: RuleType,
    *,
    organism: str,
    standard: str,
    observations: Iterable[ASTObservation],
    rules: Iterable[ExpertRule] | None,
) -> RuleEvaluation:
    selected_rules = (
        load_builtin_clsi_rules(standard=standard) if rules is None else tuple(rules)
    )
    return evaluate_expert_rules(
        organism=organism,
        standard=standard,
        observations=observations,
        rules=(rule for rule in selected_rules if rule.rule_type is rule_type),
    )


def check_intrinsic_resistance(
    *,
    organism: str,
    standard: str,
    observations: Iterable[ASTObservation],
    rules: Iterable[ExpertRule] | None = None,
) -> RuleEvaluation:
    """Flag AST categories that conflict with an approved intrinsic rule."""

    return _run_tool(
        RuleType.INTRINSIC_RESISTANCE,
        organism=organism,
        standard=standard,
        observations=observations,
        rules=rules,
    )


def evaluate_phenotype_rules(
    *,
    organism: str,
    standard: str,
    observations: Iterable[ASTObservation],
    rules: Iterable[ExpertRule] | None = None,
) -> RuleEvaluation:
    """Flag only complete, approved AST patterns; this does not infer from UZH labels."""

    return _run_tool(
        RuleType.PHENOTYPE,
        organism=organism,
        standard=standard,
        observations=observations,
        rules=rules,
    )


def apply_cascade_reporting(
    *,
    organism: str,
    standard: str,
    observations: Iterable[ASTObservation],
    rules: Iterable[ExpertRule] | None = None,
) -> RuleEvaluation:
    """Return source-backed report suppressions without altering AST categories."""

    return _run_tool(
        RuleType.CASCADE,
        organism=organism,
        standard=standard,
        observations=observations,
        rules=rules,
    )
