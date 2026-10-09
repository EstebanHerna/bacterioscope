"""Map pipeline output into the Persona 2 rule-tool contract and the report.

Owned by Persona 1 (Esteban) per docs/TEAM_EXECUTION_PLAN.md, work package P1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bacterioscope.rules import ASTObservation

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

_UNRESOLVED_REASON = "unresolved_antibiotic_identity"


@dataclass(frozen=True)
class MeasurementObservation:
    """One disk's measurement, independent of whether it entered rule evaluation.

    Mirrors one entry of ``measurement.observations`` in
    docs/contracts/agent-review-v1.schema.json.
    """

    disk_index: int
    antibiotic_code: str
    category: str
    zone_mm: float
    quality_flags: tuple[str, ...]
    included_in_rule_evaluation: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class NormalizedObservations:
    """Result of mapping one AnalysisResult into the rule-tool contract."""

    observations: tuple[ASTObservation, ...]
    measurement: tuple[MeasurementObservation, ...]


def _exclusion_reason(
    category: str, antibiotic: str, seen_codes: dict[str, int]
) -> str | None:
    if category == "UNKNOWN":
        return _UNRESOLVED_REASON
    code = antibiotic.strip().upper()
    if code in seen_codes:
        return f"duplicate_antibiotic_code:{antibiotic}"
    return None


def normalize_ast_observations(result: AnalysisResult) -> NormalizedObservations:
    """Map pipeline classifications into ASTObservation, skipping what the tools reject.

    ASTObservation requires a resolved S/I/R category and rejects duplicate
    antibiotic codes (``evaluate_expert_rules`` raises ``ValueError`` on
    either). Most real plates today still carry UNKNOWN disks -- no
    antibiotic has been assigned yet, by panel or manually (see app.py) --
    so every disk is kept in the richer ``measurement`` list for the report,
    and only the subset that is both identified and unique is passed on as
    ASTObservation for rule evaluation. Each skip is recorded with a reason
    rather than silently dropped.

    Args:
        result: Completed AnalysisResult from BacterioScopePipeline.analyze(),
            after any manual or panel-based antibiotic assignment.

    Returns:
        NormalizedObservations with the rule-ready ASTObservation tuple and
        the full per-disk measurement tuple for the report.
    """
    seen_codes: dict[str, int] = {}
    observations: list[ASTObservation] = []
    measurement: list[MeasurementObservation] = []

    for i, cls in enumerate(result.classifications):
        flags = tuple(result.flags[i]) if i < len(result.flags) else ()
        reason = _exclusion_reason(cls.category, cls.antibiotic, seen_codes)
        included = reason is None
        if included:
            seen_codes[cls.antibiotic.strip().upper()] = i
            observations.append(
                ASTObservation(antibiotic_code=cls.antibiotic, category=cls.category)
            )
        measurement.append(
            MeasurementObservation(
                disk_index=i,
                antibiotic_code=cls.antibiotic,
                category=cls.category,
                zone_mm=cls.zone_diameter_mm,
                quality_flags=flags,
                included_in_rule_evaluation=included,
                exclusion_reason=reason,
            )
        )

    return NormalizedObservations(observations=tuple(observations), measurement=tuple(measurement))


def build_measurement_section(
    result: AnalysisResult, measurement: tuple[MeasurementObservation, ...]
) -> dict[str, object]:
    """Build the ``measurement`` object of the agent-review-v1 report.

    Args:
        result: Completed AnalysisResult, for its breakpoint_table_version.
        measurement: Per-disk tuple from ``normalize_ast_observations()``.

    Returns:
        A dict matching the ``measurement`` schema in
        docs/contracts/agent-review-v1.schema.json.
    """
    return {
        "standard": result.breakpoint_table_version,
        "observations": [
            {
                "disk_index": m.disk_index,
                "antibiotic_code": m.antibiotic_code,
                "category": m.category,
                "zone_mm": m.zone_mm,
                "quality_flags": list(m.quality_flags),
                "included_in_rule_evaluation": m.included_in_rule_evaluation,
                "exclusion_reason": m.exclusion_reason,
            }
            for m in measurement
        ],
    }
