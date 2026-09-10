"""Mapping from Roboflow KB-AST class names to BacterioScope CLSI antibiotic keys.

The Roboflow/KB-AST dataset (29 classes) uses disk abbreviations common in
South American and European clinical laboratories (e.g. "CIP 10", "MEM 10").
This module maps each abbreviation to the corresponding key in
``CLSI_2023_ENTEROBACTERIACEAE`` so the classifier can look up breakpoints
directly from the YOLO label.

Classes without an entry in ``ROBOFLOW_TO_CLSI`` are not in the CLSI M100-Ed33
Enterobacteriaceae breakpoint table, or their identity is ambiguous.  The
detector returns the raw class name; the classifier reports UNKNOWN for them.
"""

from __future__ import annotations

ROBOFLOW_TO_CLSI: dict[str, str] = {
    "AK 30": "amikacin",
    "APX 30": "ampicillin",
    "AUG 30": "amoxicillin-clavulanate",
    "CAZ 30": "ceftazidime",
    "CIP 10": "ciprofloxacin",
    "CPM 30": "cefepime",
    "CRO 30": "ceftriaxone",
    # CTX is the standard code for cefotaxime, a distinct drug from
    # ceftriaxone (CRO) -- not an abbreviation-convention merge like GM/GEN
    # below. Mapped here because CLSI_2023_ENTEROBACTERIACEAE (clsi.py) has
    # no separate cefotaxime entry; flagged as unverified in
    # docs/LIMITACIONES.md section 8 pending microbiology team sign-off on
    # whether CLSI M100-Ed33 breakpoints for the two drugs are in fact
    # identical for Enterobacteriaceae. Do not assume this is settled.
    "CTX 30": "ceftriaxone",
    "GEN 10": "gentamicin",
    "GM 10": "gentamicin",
    "IPM 10": "imipenem",
    "LE 5": "levofloxacin",
    "MEM 10": "meropenem",
    "PTZ 110": "piperacillin-tazobactam",
}
