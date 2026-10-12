"""Tests for safe, resumable extraction of nested dataset archives."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from scripts import download_data
from scripts.download_data import _archive_is_fully_extracted, _extract_nested


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)


def test_find_zip_accepts_archive_in_dataset_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_dir = tmp_path / "dryad_uzh"
    archive_dir.mkdir()
    archive_path = archive_dir / "doi_10_5061_dryad_5dv41nsfj__v20241013.zip"
    _write_zip(archive_path, {"README.md": b"dataset"})
    monkeypatch.setattr(download_data, "DATA_DIR", tmp_path)

    found = download_data._find_zip(["doi_10_5061_dryad*.zip"])

    assert found == archive_path


def test_partial_outer_extraction_is_not_reported_as_complete(tmp_path: Path) -> None:
    archive_path = tmp_path / "dryad.zip"
    members = {
        "README.md": b"dataset",
        "images_original.zip": b"original-images",
        "images_measured.zip": b"measured-images",
        "Tables.zip": b"tables",
    }
    _write_zip(archive_path, members)
    destination = tmp_path / "dryad_uzh"
    destination.mkdir()
    (destination / "Tables.zip").write_bytes(members["Tables.zip"])

    assert not _archive_is_fully_extracted(archive_path, destination)

    for name, contents in members.items():
        (destination / name).write_bytes(contents)
    (destination / "README.md").write_bytes(members["README.md"])
    assert _archive_is_fully_extracted(archive_path, destination)


def test_nested_extraction_resumes_when_subdirectory_is_partial(tmp_path: Path) -> None:
    tables_zip = tmp_path / "Tables.zip"
    members = {
        "Table 1.1.1..docx": b"reference table",
        "Overview GPT JCM.xlsx": b"phenotype summary",
    }
    _write_zip(tables_zip, members)
    tables_dir = tmp_path / "Tables"
    tables_dir.mkdir()
    (tables_dir / "Table 1.1.1..docx").write_bytes(members["Table 1.1.1..docx"])

    _extract_nested(tmp_path)

    assert (tables_dir / "Table 1.1.1..docx").read_bytes() == members[
        "Table 1.1.1..docx"
    ]
    assert (tables_dir / "Overview GPT JCM.xlsx").read_bytes() == members[
        "Overview GPT JCM.xlsx"
    ]


def test_nested_extraction_skips_source_archive_when_it_is_in_destination(
    tmp_path: Path,
) -> None:
    source_archive = tmp_path / "dryad.zip"
    inner_archive = tmp_path / "Tables.zip"
    _write_zip(inner_archive, {"Table 1.1.1..docx": b"reference table"})
    inner_contents = inner_archive.read_bytes()
    _write_zip(source_archive, {"Tables.zip": inner_contents, "README.md": b"dataset"})

    _extract_nested(tmp_path, exclude=source_archive)

    assert not (tmp_path / "dryad").exists()
    assert (tmp_path / "Tables" / "Table 1.1.1..docx").read_bytes() == b"reference table"
