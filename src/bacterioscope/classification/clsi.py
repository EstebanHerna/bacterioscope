from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SusceptibilityResult:
    antibiotic: str
    zone_diameter_mm: float
    category: str
    breakpoints: dict[str, float]


CLSI_2023_ENTEROBACTERIACEAE: dict[str, dict[str, float]] = {
    "meropenem": {"S": 23.0, "I_low": 20.0, "I_high": 22.0, "R": 19.0},
    "imipenem": {"S": 23.0, "I_low": 20.0, "I_high": 22.0, "R": 19.0},
    "ertapenem": {"S": 22.0, "I_low": 19.0, "I_high": 21.0, "R": 18.0},
    "doripenem": {"S": 23.0, "I_low": 20.0, "I_high": 22.0, "R": 19.0},
    "ampicillin": {"S": 17.0, "I_low": 14.0, "I_high": 16.0, "R": 13.0},
    "amoxicillin-clavulanate": {"S": 18.0, "I_low": 14.0, "I_high": 17.0, "R": 13.0},
    "piperacillin-tazobactam": {"S": 21.0, "I_low": 18.0, "I_high": 20.0, "R": 17.0},
    "ceftriaxone": {"S": 23.0, "I_low": 20.0, "I_high": 22.0, "R": 19.0},
    "ceftazidime": {"S": 21.0, "I_low": 18.0, "I_high": 20.0, "R": 17.0},
    "cefepime": {"S": 25.0, "I_low": 19.0, "I_high": 24.0, "R": 18.0},
    "ciprofloxacin": {"S": 26.0, "I_low": 22.0, "I_high": 25.0, "R": 21.0},
    "levofloxacin": {"S": 17.0, "I_low": 14.0, "I_high": 16.0, "R": 13.0},
    "gentamicin": {"S": 15.0, "I_low": 13.0, "I_high": 14.0, "R": 12.0},
    "amikacin": {"S": 17.0, "I_low": 15.0, "I_high": 16.0, "R": 14.0},
    "trimethoprim-sulfamethoxazole": {"S": 16.0, "I_low": 11.0, "I_high": 15.0, "R": 10.0},
}

BREAKPOINT_TABLES: dict[str, dict[str, dict[str, float]]] = {
    "Enterobacteriaceae": CLSI_2023_ENTEROBACTERIACEAE,
}


class CLSIClassifier:
    def __init__(self, organism_group: str = "Enterobacteriaceae", version: str = "2023") -> None:
        self.organism_group = organism_group
        self.version = version
        self.table = BREAKPOINT_TABLES.get(organism_group, {})

    def classify(self, antibiotic: str, zone_diameter_mm: float) -> SusceptibilityResult:
        key = self._normalize_antibiotic(antibiotic)
        breakpoints = self.table.get(key, {})

        if not breakpoints:
            category = "UNKNOWN"
        elif zone_diameter_mm >= breakpoints["S"]:
            category = "S"
        elif zone_diameter_mm <= breakpoints.get("R", 0):
            category = "R"
        else:
            category = "I"

        return SusceptibilityResult(
            antibiotic=antibiotic,
            zone_diameter_mm=zone_diameter_mm,
            category=category,
            breakpoints=breakpoints,
        )

    def _normalize_antibiotic(self, name: str) -> str:
        return name.lower().strip().replace(" ", "-")

    def list_antibiotics(self) -> list[str]:
        return list(self.table.keys())
