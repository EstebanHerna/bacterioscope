"""Tests for Task 4 — traceability fields in AnalysisResult and CLSI versioning."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

from bacterioscope.classification.clsi import (
    BREAKPOINT_TABLE_VERSION,
    LAST_LINE_ANTIBIOTICS,
)
from bacterioscope.pipeline import (
    AnalysisResult,
    _compute_image_sha256,
    _get_commit_hash,
)


class TestBreakpointTableVersion:
    def test_version_string_not_empty(self) -> None:
        assert BREAKPOINT_TABLE_VERSION != ""

    def test_version_string_contains_clsi(self) -> None:
        assert "CLSI" in BREAKPOINT_TABLE_VERSION

    def test_version_string_contains_year(self) -> None:
        assert "2023" in BREAKPOINT_TABLE_VERSION


class TestLastLineAntibiotics:
    def test_carbapenems_are_last_line(self) -> None:
        for name in ("meropenem", "imipenem", "ertapenem", "doripenem"):
            assert name in LAST_LINE_ANTIBIOTICS

    def test_non_carbapenem_not_last_line(self) -> None:
        assert "ciprofloxacin" not in LAST_LINE_ANTIBIOTICS
        assert "ampicillin" not in LAST_LINE_ANTIBIOTICS


class TestAnalysisResultDefaults:
    def _make_result(self) -> AnalysisResult:
        return AnalysisResult(
            image_path="test.jpg",
            plate_diameter_px=500.0,
            px_per_mm=5.0,
        )

    def test_analysis_id_is_valid_uuid(self) -> None:
        result = self._make_result()
        parsed = uuid.UUID(result.analysis_id)
        assert str(parsed) == result.analysis_id

    def test_analysis_id_unique_per_instance(self) -> None:
        r1 = self._make_result()
        r2 = self._make_result()
        assert r1.analysis_id != r2.analysis_id

    def test_commit_hash_default_is_unknown(self) -> None:
        result = self._make_result()
        assert result.commit_hash == "unknown"

    def test_software_version_default_empty(self) -> None:
        result = self._make_result()
        assert result.software_version == ""

    def test_breakpoint_table_version_default_empty(self) -> None:
        result = self._make_result()
        assert result.breakpoint_table_version == ""

    def test_image_sha256_default_empty(self) -> None:
        result = self._make_result()
        assert result.image_sha256 == ""

    def test_to_dict_includes_traceability_keys(self) -> None:
        result = self._make_result()
        d = result.to_dict()
        for key in ("analysis_id", "software_version", "commit_hash",
                    "breakpoint_table_version", "image_sha256"):
            assert key in d, f"Missing key: {key}"


class TestGetCommitHash:
    def test_returns_string(self) -> None:
        result = _get_commit_hash()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_when_git_fails(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _get_commit_hash()
        assert result == "unknown"

    def test_fallback_when_git_returns_nonzero(self) -> None:
        from unittest.mock import MagicMock
        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = _get_commit_hash()
        assert result == "unknown"


class TestComputeImageSha256:
    def test_sha256_deterministic(self, tmp_path: Path) -> None:
        img = tmp_path / "plate.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 1024)
        h1 = _compute_image_sha256(img)
        h2 = _compute_image_sha256(img)
        assert h1 == h2

    def test_sha256_is_64_hex_chars(self, tmp_path: Path) -> None:
        img = tmp_path / "plate.png"
        img.write_bytes(b"fake image data")
        digest = _compute_image_sha256(img)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_sha256_differs_for_different_content(self, tmp_path: Path) -> None:
        img1 = tmp_path / "a.jpg"
        img2 = tmp_path / "b.jpg"
        img1.write_bytes(b"content A")
        img2.write_bytes(b"content B")
        assert _compute_image_sha256(img1) != _compute_image_sha256(img2)
