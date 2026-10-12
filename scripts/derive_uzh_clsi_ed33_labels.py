"""Derive analytical Ed33 categories from UZH SIRscan reference diameters."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from bacterioscope.evaluation.derived_clsi_reference import (
    derive_uzh_clsi_reference_rows,
    read_csv_rows,
    write_derived_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply BacterioScope's CLSI M100-Ed33 classifier to compatible UZH "
            "reference zone measurements. Output labels are derived, not independent."
        )
    )
    parser.add_argument(
        "--measurements",
        type=Path,
        default=Path("data/processed/ground_truth.csv"),
    )
    parser.add_argument(
        "--phenotypes",
        type=Path,
        default=Path("data/processed/uzh_phenotype_labels.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/uzh_derived_clsi_ed33_labels.csv"),
    )
    args = parser.parse_args()

    rows = derive_uzh_clsi_reference_rows(
        read_csv_rows(args.measurements),
        read_csv_rows(args.phenotypes),
    )
    write_derived_rows(args.output, rows)
    included = sum(row["derivation_status"] == "derived_analytical_label" for row in rows)
    exclusions = Counter(row["exclusion_reason"] for row in rows if row["exclusion_reason"])
    categories = Counter(
        row["derived_category_clsi_ed33"]
        for row in rows
        if row["derived_category_clsi_ed33"]
    )
    print(f"Wrote {len(rows)} source-preserving rows to {args.output}")
    print(f"Derived analytical labels: {included}")
    print(f"Category distribution: {dict(sorted(categories.items()))}")
    print(f"Excluded rows: {dict(sorted(exclusions.items()))}")
    print("Labels are derived from the BacterioScope classifier, not independent ground truth.")


if __name__ == "__main__":
    main()
