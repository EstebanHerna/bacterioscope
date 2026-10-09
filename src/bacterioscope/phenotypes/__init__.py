"""Reference phenotype labels with explicit dataset provenance."""

from bacterioscope.phenotypes.uzh import (
    UZH_SOURCE_URL,
    extract_uzh_phenotype_labels,
    normalize_uzh_mechanism_label,
)

__all__ = [
    "UZH_SOURCE_URL",
    "extract_uzh_phenotype_labels",
    "normalize_uzh_mechanism_label",
]
