"""Deterministic, provenance-aware antimicrobial expert-rule evaluation.

The built-in CLSI catalog is intentionally empty until the project has an
authorized source edition and qualified microbiology review.
"""

from bacterioscope.rules.engine import (
    ASTObservation,
    ExpertRule,
    RuleCondition,
    RuleEvaluation,
    RuleReference,
    RuleType,
    evaluate_expert_rules,
    load_builtin_clsi_rules,
    load_rule_catalog,
)
from bacterioscope.rules.esbl_screen import (
    ED36_STANDARD,
    ESBLScreenContext,
    ESBLScreenMatch,
    ESBLScreenResult,
    ScreeningCriterion,
    ZoneObservation,
    evaluate_esbl_screen,
    load_esbl_screen_catalog,
)
from bacterioscope.rules.tools import (
    apply_cascade_reporting,
    check_intrinsic_resistance,
    evaluate_phenotype_rules,
)

__all__ = [
    "ASTObservation",
    "apply_cascade_reporting",
    "check_intrinsic_resistance",
    "evaluate_phenotype_rules",
    "ExpertRule",
    "ED36_STANDARD",
    "ESBLScreenContext",
    "ESBLScreenMatch",
    "ESBLScreenResult",
    "RuleCondition",
    "RuleEvaluation",
    "RuleReference",
    "RuleType",
    "ScreeningCriterion",
    "ZoneObservation",
    "evaluate_expert_rules",
    "evaluate_esbl_screen",
    "load_builtin_clsi_rules",
    "load_esbl_screen_catalog",
    "load_rule_catalog",
]
