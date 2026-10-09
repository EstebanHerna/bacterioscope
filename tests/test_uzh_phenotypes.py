"""Tests for provenance-preserving UZH source phenotype labels."""

from __future__ import annotations

import csv
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from bacterioscope.phenotypes.uzh import (
    UZH_SOURCE_URL,
    extract_uzh_phenotype_labels,
    normalize_uzh_mechanism_label,
)


def test_known_source_label_aliases_are_normalized_without_guessing() -> None:
    assert normalize_uzh_mechanism_label("ESBL") == "ESBL"
    assert normalize_uzh_mechanism_label("AmpC beta-lactamase") == "AMPC"
    assert normalize_uzh_mechanism_label("Carbapenemase") == "CARBAPENEMASE"
    assert normalize_uzh_mechanism_label("Combination") == "COMBINATION_UNSPECIFIED"
    assert normalize_uzh_mechanism_label("Unlisted mechanism") is None
    assert normalize_uzh_mechanism_label("") is None


def test_extract_groups_source_labels_and_preserves_unmapped_values(tmp_path) -> None:
    source = tmp_path / "measurements.csv"
    source.write_text(
        "SampleID,Antibiotic,ResistanceMechanism\n"
        "Sample002,CRO,Combination\n"
        "Sample001,CAZ,ESBL\n"
        "Sample001,CRO,ESBL\n"
        "Sample001,MEM,New source label\n"
        "Sample003,AMP,None\n"
        ",CIP,ESBL\n",
        encoding="utf-8",
    )
    destination = tmp_path / "processed" / "phenotypes.csv"

    records = extract_uzh_phenotype_labels(source, destination)

    assert [record["sample_id"] for record in records] == ["Sample001", "Sample002", "Sample003"]
    first = records[0]
    assert json.loads(first["reference_label_codes"]) == ["ESBL"]
    assert json.loads(first["source_reported_codes"]) == ["ESBL"]
    assert first["label_provenance_status"] == "documented_measurement_table"
    assert json.loads(first["raw_labels"]) == ["ESBL", "New source label"]
    assert json.loads(first["unmapped_labels"]) == ["New source label"]
    assert json.loads(records[1]["reference_label_codes"]) == ["COMBINATION_UNSPECIFIED"]
    assert json.loads(records[2]["reference_label_codes"]) == ["NO_MECHANISM_REPORTED"]
    assert first["standard"] == "EUCAST"
    assert "not inferred" in first["evidence_type"]
    assert first["source_url"] == UZH_SOURCE_URL
    assert destination.exists()
    with destination.open(encoding="utf-8", newline="") as output:
        written = list(csv.DictReader(output))
    assert len(written) == 3


def test_requires_isolate_id_and_mechanism_columns(tmp_path) -> None:
    source = tmp_path / "measurements.csv"
    source.write_text("SampleID,Antibiotic\nSample001,CRO\n", encoding="utf-8")
    with pytest.raises(ValueError, match="isolate identifier and a resistance-mechanism"):
        extract_uzh_phenotype_labels(source)


def test_extracts_measurements_csv_directly_from_tables_zip(tmp_path) -> None:
    archive_path = tmp_path / "Tables.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "Tables/measurements.csv",
            "SampleID,Antibiotic,ResistanceMechanism\nSample001,CRO,ESBL\n",
        )

    records = extract_uzh_phenotype_labels(archive_path)

    assert len(records) == 1
    assert json.loads(records[0]["reference_label_codes"]) == ["ESBL"]


def test_extracts_source_overview_workbook_and_preserves_uncertain_flags(tmp_path) -> None:
    workbook = Workbook()
    workbook.properties.creator = "Dataset author"
    sheet = workbook.active
    sheet.append(
        [
            "Image",
            "SPECIES",
            "None (Y/N)",
            "ESBL (Y/N)",
            "AMPC (Y/N)",
            "CARBAPENEMASE (Y/N)",
        ]
    )
    sheet.append(["1.1.1.", "Escherichia coli", "no", "yes", "no", "no"])
    sheet.append(["1.1.2.", "Klebsiella pneumoniae", "yes", "no", "no", "no"])
    sheet.append(["1.1.3.", "Proteus mirabilis", "?", "not tested", "not assessable", "no"])
    content = io.BytesIO()
    workbook.save(content)
    workbook.close()

    archive_path = tmp_path / "Tables.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("Overview GPT JCM.xlsx", content.getvalue())
        archive.writestr("Table 1.1.1..docx", b"unrelated document")

    destination = tmp_path / "processed" / "phenotypes.csv"
    records = extract_uzh_phenotype_labels(archive_path, destination)

    assert [record["sample_id"] for record in records] == ["1.1.1.", "1.1.2.", "1.1.3."]
    assert records[0]["source_identifier_type"] == "source_image_id"
    assert records[0]["image_join_key"] == "1.1.1"
    assert records[0]["organism"] == "Escherichia coli"
    assert records[0]["source_asset"] == "Overview GPT JCM.xlsx"
    assert records[0]["source_author"] == "Dataset author"
    assert json.loads(records[0]["source_reported_codes"]) == ["ESBL"]
    assert json.loads(records[0]["reference_label_codes"]) == []
    assert records[0]["label_provenance_status"] == "unverified_workbook_summary"
    assert "possible model-output" in records[0]["evidence_type"]
    assert json.loads(records[1]["source_reported_codes"]) == ["NO_MECHANISM_REPORTED"]
    assert json.loads(records[1]["reference_label_codes"]) == []
    assert records[2]["label_status"] == "partial"
    assert json.loads(records[2]["reference_label_codes"]) == []
    assert "not tested" in records[2]["unmapped_labels"]
    assert len(records[0]["source_file_sha256"]) == 64
    assert destination.exists()
