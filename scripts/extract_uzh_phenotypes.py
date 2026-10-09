"""Export source-reported mechanism labels from the UZH/Dryad table CSV or ZIP."""

from __future__ import annotations

import argparse
from pathlib import Path

from bacterioscope.phenotypes.uzh import extract_uzh_phenotype_labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/dryad_uzh/Tables.zip"),
        help=(
            "Path to Dryad Tables.zip, its measurements.csv, or its phenotype "
            "overview workbook (requires the project dev dependencies)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/uzh_phenotype_labels.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()
    records = extract_uzh_phenotype_labels(args.input, args.output)
    print(f"Wrote {len(records)} isolate phenotype-label records to {args.output}")


if __name__ == "__main__":
    main()
