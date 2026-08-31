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


def reclassify_with_override(
    zone_mm: float,
    override_mm: float | None,
    antibiotic: str,
    classifier: CLSIClassifier,
    disk_label: str = "",
) -> tuple[SusceptibilityResult, str]:
    """Reclassify a disk with an optional user-provided diameter override.

    When override_mm is provided, it replaces the pipeline-measured diameter
    for classification purposes.  The returned source string indicates whether
    the diameter used was 'automatic' (pipeline) or 'manual' (user-corrected).

    Args:
        zone_mm: Diameter measured by the pipeline in mm.
        override_mm: User-specified diameter in mm, or None to use zone_mm.
        antibiotic: Antibiotic name or _UNASSIGNED sentinel.
        classifier: Configured CLSIClassifier instance.
        disk_label: Disk identifier used as fallback when antibiotic is unassigned.

    Returns:
        Tuple of (SusceptibilityResult, source) where source is 'manual' when
        override_mm was applied and 'automatic' otherwise.
    """
    effective_mm = override_mm if override_mm is not None else zone_mm
    source = "manual" if override_mm is not None else "automatic"
    result = reclassify_with_assignment(effective_mm, antibiotic, classifier, disk_label)
    return result, source


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
