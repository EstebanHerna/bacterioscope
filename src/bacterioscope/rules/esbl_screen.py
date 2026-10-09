"""Fail-closed CLSI ESBL screening support using measured disk diameters.

The M100 Ed36 candidates are draft and unavailable for execution until the
catalog is reviewed. A positive screen is only a signal for further review;
this module never diagnoses ESBL or changes an S/I/R interpretation.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bacterioscope.rules.engine import RuleReference

ED36_STANDARD = "CLSI M100-Ed36 2026"


@dataclass(frozen=True)
class ZoneObservation:
    """One measured disk-diffusion diameter and its exact disk identity."""

    antibiotic_code: str
    disk_potency_ug: int
    zone_mm: float
    quality_accepted: bool

    def __post_init__(self) -> None:
        if not self.antibiotic_code.strip():
            raise ValueError("antibiotic_code must not be empty")
        if (
            isinstance(self.disk_potency_ug, bool)
            or not isinstance(self.disk_potency_ug, int)
            or self.disk_potency_ug <= 0
        ):
            raise ValueError("disk_potency_ug must be a positive integer")
        if isinstance(self.zone_mm, bool) or not isinstance(self.zone_mm, (int, float)):
            raise ValueError("zone_mm must be a numeric diameter in millimeters")
        if not math.isfinite(self.zone_mm) or not 0 <= self.zone_mm <= 100:
            raise ValueError("zone_mm must be finite and between 0 and 100")
        if not isinstance(self.quality_accepted, bool):
            raise ValueError("quality_accepted must be an explicit boolean")

    @property
    def normalized_code(self) -> str:
        return self.antibiotic_code.strip().casefold()


@dataclass(frozen=True)
class ESBLScreenContext:
    """Assay details required to decide whether Ed36 screen criteria apply."""

    method: str | None
    medium: str | None
    temperature_c: float | None
    incubation_hours: float | None
    atmosphere: str | None
    standard_disk_diffusion_procedure: bool | None

    def __post_init__(self) -> None:
        for name, value in (
            ("temperature_c", self.temperature_c),
            ("incubation_hours", self.incubation_hours),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be a finite number or None")
        if self.standard_disk_diffusion_procedure is not None and not isinstance(
            self.standard_disk_diffusion_procedure, bool
        ):
            raise ValueError("standard_disk_diffusion_procedure must be bool or None")


@dataclass(frozen=True)
class ScreeningCriterion:
    rule_id: str
    version: str
    organisms: tuple[str, ...]
    antibiotic_code: str
    disk_potency_ug: int
    maximum_zone_mm: float
    standard: str
    status: str
    reference: RuleReference

    @property
    def enabled(self) -> bool:
        return (
            self.status == "approved"
            and re.fullmatch(r"\d+\.\d+\.\d+", self.version) is not None
            and bool(self.rule_id.strip())
            and bool(self.organisms)
            and bool(self.antibiotic_code.strip())
            and isinstance(self.disk_potency_ug, int)
            and self.disk_potency_ug > 0
            and math.isfinite(self.maximum_zone_mm)
            and self.maximum_zone_mm >= 0
            and self.reference.standard == self.standard
            and self.reference.approved_for_execution
        )


@dataclass(frozen=True)
class ESBLScreenMatch:
    rule_id: str
    antibiotic_code: str
    zone_mm: float
    maximum_zone_mm: float
    source_id: str
    citation: str
    source_url: str


@dataclass(frozen=True)
class ESBLScreenResult:
    status: str
    screen_signal: bool | None
    matches: tuple[ESBLScreenMatch, ...] = ()
    evaluated_rule_ids: tuple[str, ...] = ()
    missing_rule_ids: tuple[str, ...] = ()
    quality_rejected_rule_ids: tuple[str, ...] = ()
    skipped_rule_ids: tuple[str, ...] = ()
    coverage_complete: bool = False
    catalog_status: str = "no_rules_configured"
    source_id: str | None = None
    citation: str | None = None
    source_url: str | None = None
    source_locator: str | None = None


def load_esbl_screen_catalog(standard: str = ED36_STANDARD) -> tuple[ScreeningCriterion, ...]:
    """Load a structurally checked screen catalog for one exact CLSI edition."""

    if standard != ED36_STANDARD:
        return ()
    path = Path(__file__).with_name("clsi_m100_ed36_esbl_screen.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1 or raw.get("standard") != standard:
        raise ValueError("unsupported or mismatched ESBL screen catalog")
    if re.fullmatch(r"\d+\.\d+\.\d+", str(raw.get("catalog_version", ""))) is None:
        raise ValueError("ESBL screen catalog needs a semantic catalog_version")

    reference_data = raw["reference"]
    reference = RuleReference(
        source_id=str(reference_data["source_id"]),
        citation=str(reference_data["citation"]),
        url=str(reference_data["url"]),
        standard=standard,
        reuse_status=str(reference_data.get("reuse_status", "pending")),
        source_locator=str(reference_data.get("source_locator", "")),
        reuse_evidence=str(reference_data.get("reuse_evidence", "")),
    )
    criteria = tuple(
        ScreeningCriterion(
            rule_id=str(item["rule_id"]),
            version=str(item["version"]),
            organisms=tuple(str(value) for value in item["organisms"]),
            antibiotic_code=str(item["antibiotic_code"]),
            disk_potency_ug=int(item["disk_potency_ug"]),
            maximum_zone_mm=float(item["maximum_zone_mm"]),
            standard=standard,
            status=str(item.get("status", "draft")),
            reference=reference,
        )
        for item in raw.get("criteria", [])
    )
    if not criteria:
        raise ValueError("ESBL screen catalog must contain at least one criterion")
    if len({criterion.rule_id for criterion in criteria}) != len(criteria):
        raise ValueError("duplicate rule_id in ESBL screen catalog")
    if any(
        not criterion.rule_id
        or not criterion.organisms
        or criterion.disk_potency_ug <= 0
        or not 0 <= criterion.maximum_zone_mm <= 100
        or criterion.status not in {"draft", "approved", "retired"}
        for criterion in criteria
    ):
        raise ValueError("invalid criterion in ESBL screen catalog")
    return criteria


def _organism_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _context_gaps(context: ESBLScreenContext) -> tuple[str, ...]:
    gaps: list[str] = []
    if (context.method or "").strip().casefold() != "disk diffusion":
        gaps.append("method")
    if (context.medium or "").strip().casefold() not in {
        "mha",
        "mueller-hinton agar",
    }:
        gaps.append("medium")
    if (
        context.temperature_c is None
        or not math.isfinite(context.temperature_c)
        or not 33 <= context.temperature_c <= 37
    ):
        gaps.append("temperature_c")
    if (
        context.incubation_hours is None
        or not math.isfinite(context.incubation_hours)
        or not 16 <= context.incubation_hours <= 18
    ):
        gaps.append("incubation_hours")
    if (context.atmosphere or "").strip().casefold() != "ambient air":
        gaps.append("atmosphere")
    if context.standard_disk_diffusion_procedure is not True:
        gaps.append("standard_disk_diffusion_procedure")
    return tuple(gaps)


def evaluate_esbl_screen(
    *,
    organism: str,
    standard: str,
    context: ESBLScreenContext,
    observations: Iterable[ZoneObservation],
    criteria: Iterable[ScreeningCriterion] | None = None,
) -> ESBLScreenResult:
    """Evaluate only reviewed, exact-match zone criteria; never alter AST S/I/R.

    The built-in M100 Ed36 criteria are drafts. They return an unavailable
    state until individually approved. Test-only criteria may be injected to
    exercise threshold mechanics without activating clinical content.
    """

    selected = tuple(load_esbl_screen_catalog(standard) if criteria is None else criteria)
    organism_key = _organism_key(organism)
    applicable = tuple(
        criterion
        for criterion in selected
        if criterion.standard == standard
        and organism_key in {_organism_key(item) for item in criterion.organisms}
    )
    if not applicable:
        return ESBLScreenResult(
            status="no_applicable_screen_rules",
            screen_signal=None,
            catalog_status=(
                "no_rules_configured"
                if not selected
                else "rules_not_enabled_for_standard_or_review"
            ),
        )

    reference = applicable[0].reference

    enabled = tuple(criterion for criterion in applicable if criterion.enabled)
    skipped = tuple(criterion.rule_id for criterion in applicable if not criterion.enabled)
    if not enabled:
        return ESBLScreenResult(
            status="screen_rules_unavailable",
            screen_signal=None,
            skipped_rule_ids=skipped,
            catalog_status="rules_not_enabled_for_standard_or_review",
            source_id=reference.source_id,
            citation=reference.citation,
            source_url=reference.url,
            source_locator=reference.source_locator,
        )

    gaps = _context_gaps(context)
    if gaps:
        return ESBLScreenResult(
            status="assay_context_incomplete",
            screen_signal=None,
            skipped_rule_ids=gaps,
            catalog_status="rules_available",
            source_id=reference.source_id,
            citation=reference.citation,
            source_url=reference.url,
            source_locator=reference.source_locator,
        )

    by_key: dict[tuple[str, int], ZoneObservation] = {}
    for observation in observations:
        key = (observation.normalized_code, observation.disk_potency_ug)
        if key in by_key:
            raise ValueError(f"duplicate zone observation for disk {key[0]} {key[1]} ug")
        by_key[key] = observation

    matches: list[ESBLScreenMatch] = []
    evaluated: list[str] = []
    missing: list[str] = []
    rejected: list[str] = []
    for criterion in enabled:
        key = (criterion.antibiotic_code.casefold(), criterion.disk_potency_ug)
        matched_observation = by_key.get(key)
        if matched_observation is None:
            missing.append(criterion.rule_id)
            continue
        if not matched_observation.quality_accepted:
            rejected.append(criterion.rule_id)
            continue
        evaluated.append(criterion.rule_id)
        if matched_observation.zone_mm <= criterion.maximum_zone_mm:
            matches.append(
                ESBLScreenMatch(
                    rule_id=criterion.rule_id,
                    antibiotic_code=criterion.antibiotic_code,
                    zone_mm=float(matched_observation.zone_mm),
                    maximum_zone_mm=criterion.maximum_zone_mm,
                    source_id=criterion.reference.source_id,
                    citation=criterion.reference.citation,
                    source_url=criterion.reference.url,
                )
            )

    if not evaluated:
        return ESBLScreenResult(
            status="no_usable_matching_measurements",
            screen_signal=None,
            evaluated_rule_ids=tuple(evaluated),
            missing_rule_ids=tuple(missing),
            quality_rejected_rule_ids=tuple(rejected),
            coverage_complete=False,
            catalog_status="rules_available",
            source_id=reference.source_id,
            citation=reference.citation,
            source_url=reference.url,
            source_locator=reference.source_locator,
        )
    coverage_complete = not missing and not rejected
    if matches:
        status = "screen_signal_for_review"
        signal: bool | None = True
    else:
        status = (
            "no_signal_observed"
            if coverage_complete
            else "no_signal_observed_in_partial_panel"
        )
        signal = False
    return ESBLScreenResult(
        status=status,
        screen_signal=signal,
        matches=tuple(matches),
        evaluated_rule_ids=tuple(evaluated),
        missing_rule_ids=tuple(missing),
        quality_rejected_rule_ids=tuple(rejected),
        coverage_complete=coverage_complete,
        catalog_status="rules_available",
        source_id=reference.source_id,
        citation=reference.citation,
        source_url=reference.url,
        source_locator=reference.source_locator,
    )
