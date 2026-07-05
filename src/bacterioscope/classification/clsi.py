"""CLSI M100-Ed33 (2023) breakpoint-based antimicrobial susceptibility classification.

What CLSI is
------------
The Clinical and Laboratory Standards Institute (CLSI) is a non-profit
organisation that publishes evidence-based standards for clinical laboratory
testing.  Its document **M100** ("Performance Standards for Antimicrobial
Susceptibility Testing") is updated every year and defines, for each antibiotic
and organism group, the minimum inhibition zone diameters that distinguish:

- **S — Susceptible**: the pathogen is inhibited by the drug at normally
  achievable concentrations.  Standard dosing is likely effective.
- **I — Intermediate**: the pathogen is inhibited at higher-than-normal
  concentrations or at body sites where the drug concentrates.  Dose
  escalation or local therapy may be effective.
- **R — Resistant**: the pathogen is not inhibited at achievable concentrations.
  Treatment with this antibiotic is unlikely to succeed.

Worked example (Ciprofloxacin, Enterobacteriaceae, CLSI 2023)
--------------------------------------------------------------
::

    zone >= 26 mm  →  S  (standard ciprofloxacin dose will likely work)
    22–25 mm       →  I  (borderline; higher dose or urinary tract focus)
    zone <= 21 mm  →  R  (ciprofloxacin-resistant; choose a different drug)

What this module contains
--------------------------
``CLSI_2023_ENTEROBACTERIACEAE``
    A dictionary with breakpoints for 15 antibiotics commonly used against
    Gram-negative Enterobacteriaceae (e.g. *E. coli*, *K. pneumoniae*).
``CLSIClassifier``
    A class that looks up an antibiotic in the table and compares a measured
    zone diameter to return a ``SusceptibilityResult`` with the S/I/R category.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SusceptibilityResult:
    """Classification result for one antibiotic disk on the plate.

    Attributes:
        antibiotic: Antibiotic name as used for the breakpoint lookup (may be
            the raw label from YOLOv8 or a manually assigned name).
        zone_diameter_mm: Measured inhibition zone diameter in millimetres.
            This is the clinically meaningful measurement.
        category: CLSI classification — ``'S'`` (Susceptible),
            ``'I'`` (Intermediate), ``'R'`` (Resistant), or ``'UNKNOWN'``
            if the antibiotic was not found in the breakpoint table.
        breakpoints: Dictionary of the CLSI threshold values used for this
            antibiotic.  Keys: ``'S'`` (susceptible threshold),
            ``'I_low'``, ``'I_high'`` (intermediate range),
            ``'R'`` (resistant threshold).  Empty dict when UNKNOWN.
    """
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
    """Classifies zone diameters into S/I/R using CLSI 2023 breakpoints.

    The classifier normalises the antibiotic name (lowercase, spaces →
    hyphens), looks it up in the breakpoint table for the specified organism
    group, and applies the thresholds to assign a category.

    If the antibiotic is not in the table (e.g. a misspelling, or a disk
    named "disk_0" by the Hough fallback), the result is UNKNOWN with
    empty breakpoints.

    Attributes:
        organism_group: Bacterial species group for breakpoint lookup.
            Currently only ``'Enterobacteriaceae'`` is supported.
        version: Year of the CLSI M100 edition used (currently ``'2023'``).
        table: Loaded breakpoint dictionary for the selected organism group.
    """
    def __init__(self, organism_group: str = "Enterobacteriaceae", version: str = "2023") -> None:
        self.organism_group = organism_group
        self.version = version
        self.table = BREAKPOINT_TABLES.get(organism_group, {})

    def classify(self, antibiotic: str, zone_diameter_mm: float) -> SusceptibilityResult:
        """Classify one zone diameter against the CLSI breakpoint table.

        Args:
            antibiotic: Antibiotic name.  Case-insensitive; spaces are treated
                as hyphens, so ``"Ciprofloxacin"`` and ``"ciprofloxacin"``
                both resolve correctly.  Names not in the table return UNKNOWN.
            zone_diameter_mm: Measured inhibition zone diameter in mm as
                returned by the zone segmenter.

        Returns:
            ``SusceptibilityResult`` with the category set to ``'S'``,
            ``'I'``, ``'R'``, or ``'UNKNOWN'`` and the thresholds used.
        """
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
        """Normalise an antibiotic name for case-insensitive table lookup."""
        return name.lower().strip().replace(" ", "-")

    def list_antibiotics(self) -> list[str]:
        """Return all antibiotic names available in the loaded breakpoint table."""
        return list(self.table.keys())
