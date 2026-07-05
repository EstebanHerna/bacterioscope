"""Pure helper functions for the BacterioScope Streamlit app.

Isolated here so they can be unit-tested without installing Streamlit.
"""

from __future__ import annotations

from bacterioscope.classification.clsi import (
    CLSI_2023_ENTEROBACTERIACEAE,
    CLSIClassifier,
    SusceptibilityResult,
)

_UNASSIGNED = "-- Unassigned --"
_ANTIBIOTIC_OPTIONS: list[str] = [_UNASSIGNED] + sorted(CLSI_2023_ENTEROBACTERIACEAE.keys())


def reclassify_with_assignment(
    zone_mm: float,
    antibiotic: str,
    classifier: CLSIClassifier,
    disk_label: str = "",
) -> SusceptibilityResult:
    """Return a SusceptibilityResult for the given zone and antibiotic assignment.

    If antibiotic is the unassigned sentinel or empty, returns UNKNOWN using
    disk_label as the antibiotic field so the disk identity is preserved.

    Args:
        zone_mm: Inhibition zone diameter in millimetres.
        antibiotic: Antibiotic name selected by the user, or _UNASSIGNED.
        classifier: Configured CLSIClassifier instance.
        disk_label: Disk identifier (e.g. "disk_0") used as fallback antibiotic name
            when antibiotic is unassigned, so the disk identity is not lost.

    Returns:
        SusceptibilityResult with category S/I/R for a known antibiotic, or UNKNOWN
        with an empty breakpoints dict when no antibiotic has been assigned.
    """
    if not antibiotic or antibiotic == _UNASSIGNED:
        return SusceptibilityResult(
            antibiotic=disk_label or antibiotic,
            zone_diameter_mm=zone_mm,
            category="UNKNOWN",
            breakpoints={},
        )
    return classifier.classify(antibiotic, zone_mm)
