"""Evaluate explicitly reviewed expert rules without changing AST results.

This module is a deterministic execution layer. It does not contain clinical
rules by itself; the bundled catalog is empty pending licensed source material
and qualified review. Findings are flags for review, never treatment advice.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from bacterioscope.classification.clsi import BREAKPOINT_TABLE_VERSION


class RuleType(str, Enum):
    INTRINSIC_RESISTANCE = "intrinsic_resistance"
    PHENOTYPE = "phenotype"
    CASCADE = "cascade"


@dataclass(frozen=True)
class ASTObservation:
    """One deterministic AST category supplied by the existing pipeline."""

    antibiotic_code: str
    category: str

    def __post_init__(self) -> None:
        if not self.antibiotic_code.strip():
            raise ValueError("antibiotic_code must not be empty")
        if self.category.strip().upper() not in {"S", "I", "R"}:
            raise ValueError("category must be S, I, or R")

    @property
    def normalized_code(self) -> str:
        return self.antibiotic_code.strip().upper()

    @property
    def normalized_category(self) -> str:
        return self.category.strip().upper()


@dataclass(frozen=True)
class RuleCondition:
    """A required observed category for one antimicrobial code."""

    antibiotic_code: str
    categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.antibiotic_code.strip():
            raise ValueError("condition antibiotic_code must not be empty")
        normalized = {category.strip().upper() for category in self.categories}
        if not normalized or not normalized <= {"S", "I", "R"}:
            raise ValueError("condition categories must contain S, I, and/or R")


@dataclass(frozen=True)
class RuleReference:
    """Evidence and review metadata required before a rule can run."""

    source_id: str
    citation: str
    url: str
    standard: str
    reuse_status: str
    reviewer: str | None = None
    reviewed_on: str | None = None
    source_locator: str | None = None
    reuse_evidence: str | None = None

    @property
    def approved_for_execution(self) -> bool:
        if self.reuse_status not in {"authorized", "cc0", "public_domain"}:
            return False
        if not all((self.source_id.strip(), self.citation.strip(), self.standard.strip())):
            return False
        if not self.url.startswith("https://"):
            return False
        if not self.reviewer or not self.reviewer.strip() or not self.reviewed_on:
            return False
        if not self.source_locator or not self.source_locator.strip():
            return False
        if not self.reuse_evidence or not self.reuse_evidence.strip():
            return False
        try:
            date.fromisoformat(self.reviewed_on)
        except ValueError:
            return False
        return True


@dataclass(frozen=True)
class ExpertRule:
    """One versioned rule with explicit applicability and evidence."""

    rule_id: str
    rule_type: RuleType
    organisms: tuple[str, ...]
    conditions: tuple[RuleCondition, ...]
    reference: RuleReference
    status: str = "draft"
    version: str = "1.0.0"
    finding_code: str = "expert_rule_review"
    phenotype_label: str | None = None
    suppress_antibiotics: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        return (
            self.status == "approved"
            and re.fullmatch(r"\d+\.\d+\.\d+", self.version) is not None
            and bool(self.rule_id.strip())
            and bool(self.organisms)
            and bool(self.conditions)
            and self.reference.approved_for_execution
            and (
                self.rule_type is not RuleType.PHENOTYPE
                or bool(self.phenotype_label and self.phenotype_label.strip())
            )
            and (self.rule_type is not RuleType.CASCADE or bool(self.suppress_antibiotics))
        )


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    rule_version: str
    rule_type: RuleType
    code: str
    phenotype_label: str | None
    observed_codes: tuple[str, ...]
    source_id: str
    citation: str
    source_url: str


@dataclass(frozen=True)
class RuleEvaluation:
    findings: tuple[RuleFinding, ...] = ()
    suppressed_antibiotics: tuple[str, ...] = ()
    skipped_rule_ids: tuple[str, ...] = ()
    catalog_status: str = "no_rules_configured"


def _organism_key(value: str) -> str:
    return " ".join(value.casefold().split())


def evaluate_expert_rules(
    *,
    organism: str,
    standard: str,
    observations: Iterable[ASTObservation],
    rules: Iterable[ExpertRule],
) -> RuleEvaluation:
    """Return sourced flags and cascade suppressions for exact rule matches.

    Only rules whose status, source reuse rights, reviewer, review date, and
    standard all match are executed. The input categories are never rewritten.
    """

    by_code: dict[str, str] = {}
    for observation in observations:
        code = observation.normalized_code
        if code in by_code:
            raise ValueError(f"duplicate AST observation for antibiotic {code}")
        by_code[code] = observation.normalized_category

    rule_list = tuple(rules)
    findings: list[RuleFinding] = []
    suppressed: set[str] = set()
    skipped: list[str] = []
    organism_key = _organism_key(organism)

    for rule in rule_list:
        if not rule.enabled or rule.reference.standard != standard:
            skipped.append(rule.rule_id)
            continue
        applicable_organisms = {_organism_key(item) for item in rule.organisms}
        if organism_key not in applicable_organisms:
            continue
        if not rule.conditions or any(
            condition.antibiotic_code.strip().upper() not in by_code
            or by_code[condition.antibiotic_code.strip().upper()]
            not in {category.strip().upper() for category in condition.categories}
            for condition in rule.conditions
        ):
            continue

        observed_codes = tuple(
            condition.antibiotic_code.strip().upper() for condition in rule.conditions
        )
        findings.append(
            RuleFinding(
                rule_id=rule.rule_id,
                rule_version=rule.version,
                rule_type=rule.rule_type,
                code=rule.finding_code,
                phenotype_label=(
                    rule.phenotype_label if rule.rule_type is RuleType.PHENOTYPE else None
                ),
                observed_codes=observed_codes,
                source_id=rule.reference.source_id,
                citation=rule.reference.citation,
                source_url=rule.reference.url,
            )
        )
        if rule.rule_type is RuleType.CASCADE:
            suppressed.update(code.strip().upper() for code in rule.suppress_antibiotics)

    return RuleEvaluation(
        findings=tuple(findings),
        suppressed_antibiotics=tuple(sorted(suppressed)),
        skipped_rule_ids=tuple(skipped),
        catalog_status=(
            "rules_available"
            if any(rule.enabled and rule.reference.standard == standard for rule in rule_list)
            else "rules_not_enabled_for_standard_or_review"
            if rule_list
            else "no_rules_configured"
        ),
    )


def _parse_rule(raw: Mapping[str, Any]) -> ExpertRule:
    reference = raw["reference"]
    return ExpertRule(
        rule_id=str(raw["rule_id"]),
        rule_type=RuleType(raw["rule_type"]),
        organisms=tuple(str(item) for item in raw.get("organisms", [])),
        conditions=tuple(
            RuleCondition(
                antibiotic_code=str(condition["antibiotic_code"]),
                categories=tuple(str(item) for item in condition["categories"]),
            )
            for condition in raw.get("conditions", [])
        ),
        reference=RuleReference(
            source_id=str(reference.get("source_id", "")),
            citation=str(reference.get("citation", "")),
            url=str(reference.get("url", "")),
            standard=str(reference.get("standard", "")),
            reuse_status=str(reference.get("reuse_status", "pending")),
            reviewer=(str(reference["reviewer"]) if reference.get("reviewer") else None),
            reviewed_on=(
                str(reference["reviewed_on"]) if reference.get("reviewed_on") else None
            ),
            source_locator=(
                str(reference["source_locator"]) if reference.get("source_locator") else None
            ),
            reuse_evidence=(
                str(reference["reuse_evidence"]) if reference.get("reuse_evidence") else None
            ),
        ),
        status=str(raw.get("status", "draft")),
        version=str(raw.get("version", "0.1.0")),
        finding_code=str(raw.get("finding_code", "expert_rule_review")),
        phenotype_label=(
            str(raw["phenotype_label"]) if raw.get("phenotype_label") else None
        ),
        suppress_antibiotics=tuple(
            str(item) for item in raw.get("suppress_antibiotics", [])
        ),
    )


def load_rule_catalog(path: Path | str) -> tuple[ExpertRule, ...]:
    """Load and structurally validate a versioned rule catalog JSON file."""

    catalog_path = Path(path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("unsupported rule catalog schema_version")
    catalog_version = str(catalog.get("catalog_version", ""))
    if re.fullmatch(r"\d+\.\d+\.\d+", catalog_version) is None:
        raise ValueError("rule catalog needs a semantic catalog_version")
    raw_rules = catalog.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError("rule catalog 'rules' must be a list")
    parsed = tuple(_parse_rule(item) for item in raw_rules)
    identifiers = [rule.rule_id for rule in parsed]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate rule_id in rule catalog")
    catalog_standard = catalog.get("standard")
    for rule in parsed:
        if not rule.rule_id.strip() or not rule.organisms or not rule.conditions:
            raise ValueError(f"rule {rule.rule_id!r} needs an id, organism, and condition")
        if re.fullmatch(r"\d+\.\d+\.\d+", rule.version) is None:
            raise ValueError(f"rule {rule.rule_id!r} needs a semantic version")
        if rule.reference.standard != catalog_standard:
            raise ValueError(f"rule {rule.rule_id!r} standard differs from catalog standard")
        if rule.status not in {"draft", "approved", "retired"}:
            raise ValueError(f"rule {rule.rule_id!r} has an unsupported status")
        if rule.rule_type is RuleType.PHENOTYPE and not rule.phenotype_label:
            raise ValueError(f"phenotype rule {rule.rule_id!r} needs phenotype_label")
        if rule.rule_type is RuleType.CASCADE and not rule.suppress_antibiotics:
            raise ValueError(f"cascade rule {rule.rule_id!r} needs suppress_antibiotics")
    return parsed


def load_builtin_clsi_rules(standard: str | None = None) -> tuple[ExpertRule, ...]:
    """Load the bundled catalog matching ``standard``.

    The no-argument default remains the classifier's current edition. Newer
    catalogs can be inspected and tested before the pipeline adopts them; all
    draft rules remain fail-closed until a qualified reviewer approves them.
    """

    catalog_paths = {
        "CLSI M100-Ed33 2023": "clsi_m100_ed33.json",
        "CLSI M100-Ed36 2026": "clsi_m100_ed36.json",
    }
    selected_standard = standard or BREAKPOINT_TABLE_VERSION
    try:
        catalog_name = catalog_paths[selected_standard]
    except KeyError as exc:
        raise ValueError(f"no bundled CLSI rule catalog for {selected_standard!r}") from exc

    catalog_path = Path(__file__).with_name(catalog_name)
    rules = load_rule_catalog(catalog_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("standard") != selected_standard:
        raise ValueError("CLSI expert-rule catalog edition differs from requested standard")
    return rules
