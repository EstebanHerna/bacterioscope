"""Tests for UZH measurement-table and image joins."""

from __future__ import annotations

from pathlib import Path

from scripts.prepare_dataset import _find_images, _match_image


def test_find_images_ignores_appledouble_metadata(tmp_path: Path) -> None:
    original_dir = tmp_path / "images_original"
    metadata_dir = original_dir / "__MACOSX"
    metadata_dir.mkdir(parents=True)
    original = original_dir / "7.17.1 original.jpg"
    original.write_bytes(b"image")
    (original_dir / "._7.17.1 original.jpg").write_bytes(b"metadata")
    (metadata_dir / "._7.17.1 original.jpg").write_bytes(b"metadata")

    images = _find_images(tmp_path)

    assert images == {"7.17.1 original": original}


def test_match_image_prefers_original_and_handles_trailing_dot() -> None:
    original = Path("images_original/7.17.1 original.jpg")
    measured = Path("images_measured/7.17.1. measured.jpg")
    another_isolate = Path("images_original/7.17.10 original.jpg")
    images = {
        original.stem: original,
        measured.stem: measured,
        another_isolate.stem: another_isolate,
    }

    assert _match_image("7.17.1.", images) == original
