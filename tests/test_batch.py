"""Tests for batch_analyze.py — filename parsing and image collection."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from batch_analyze import _collect_images, _parse_filename  # type: ignore[import]


class TestParseFilename:
    def test_standard_three_part_name(self) -> None:
        result = _parse_filename("ecoli_R1_day1")
        assert result == {"cepa": "ecoli", "replica": "R1", "condicion": "day1"}

    def test_condition_with_underscore(self) -> None:
        result = _parse_filename("kpneu_A_37C_8h")
        assert result["cepa"] == "kpneu"
        assert result["replica"] == "A"
        assert result["condicion"] == "37C_8h"

    def test_no_underscores_falls_back(self) -> None:
        result = _parse_filename("plate001")
        assert result["cepa"] == "plate001"
        assert result["replica"] == ""
        assert result["condicion"] == ""

    def test_two_underscores_splits_correctly(self) -> None:
        result = _parse_filename("ecoli_1_control")
        assert result == {"cepa": "ecoli", "replica": "1", "condicion": "control"}


class TestCollectImages:
    def test_collects_jpg_and_png(self, tmp_path: Path) -> None:
        (tmp_path / "a.jpg").touch()
        (tmp_path / "b.png").touch()
        (tmp_path / "c.txt").touch()
        images = _collect_images(tmp_path)
        names = {p.name for p in images}
        assert "a.jpg" in names
        assert "b.png" in names
        assert "c.txt" not in names

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        for name in ["c.jpg", "a.jpg", "b.png"]:
            (tmp_path / name).touch()
        images = _collect_images(tmp_path)
        assert [p.name for p in images] == ["a.jpg", "b.png", "c.jpg"]

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        assert _collect_images(tmp_path) == []

    def test_tiff_extension_included(self, tmp_path: Path) -> None:
        (tmp_path / "scan.tiff").touch()
        images = _collect_images(tmp_path)
        assert any(p.suffix == ".tiff" for p in images)

    def test_only_files_not_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "subdir.jpg").mkdir()
        (tmp_path / "real.jpg").touch()
        images = _collect_images(tmp_path)
        assert all(p.is_file() for p in images)
