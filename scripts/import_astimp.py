"""Import test plate images from the ASTimp project by Marco Pascucci.

The ASTimp project (Automated Susceptibility Testing image processing) is a
C++/Python library for antibiogram image analysis.  Its repository contains
a set of test plate photographs used for validation and demonstration.

Repository: https://github.com/mpascucci/AST-image-processing
License:    Apache License 2.0

IMPORTANT — license and citation requirement
---------------------------------------------
By running this script you accept the Apache 2.0 License terms.
Any publication using these images must cite:

  Pascucci M, Royer G, Adamek J, Al Asmar M, Aristizabal D, et al. (2021).
  AI-based mobile application to fight antibiotic resistance.
  Nature Communications 12:1173. doi:10.1038/s41467-021-21187-3

Usage::

    python scripts/import_astimp.py
    python scripts/import_astimp.py --output-dir data/raw/astimp --yes
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_URL = "https://github.com/mpascucci/AST-image-processing.git"
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
_DISCLAIMER = (
    "You are about to download images from the ASTimp project.\n"
    "  Repository: https://github.com/mpascucci/AST-image-processing\n"
    "  License:    Apache License 2.0\n"
    "  Citation:   Pascucci M, et al. Nature Communications 2021;12:1173.\n"
    "              doi:10.1038/s41467-021-21187-3\n\n"
    "By proceeding you agree to the license terms and commit to citing the\n"
    "above paper in any publication that uses these images."
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import ASTimp test images.")
    p.add_argument(
        "--output-dir", type=Path, default=Path("data/raw/astimp"),
        help="Destination directory for the images (default: data/raw/astimp).",
    )
    p.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the interactive disclaimer prompt (for CI use).",
    )
    return p.parse_args()


def _confirm_disclaimer() -> bool:
    print(_DISCLAIMER)
    print()
    answer = input("Accept and continue? [y/N] ").strip().lower()
    return answer == "y"


def _clone_repo(clone_dir: Path) -> None:
    result = subprocess.run(
        ["git", "clone", "--depth=1", _REPO_URL, str(clone_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error: git clone failed.\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def _collect_images(repo_dir: Path) -> list[Path]:
    images = []
    for p in repo_dir.rglob("*"):
        if p.suffix.lower() in _IMAGE_SUFFIXES and "test" in str(p).lower():
            images.append(p)
    if not images:
        for p in repo_dir.rglob("*"):
            if p.suffix.lower() in _IMAGE_SUFFIXES:
                images.append(p)
    return images


def main() -> None:
    args = _parse_args()

    if not args.yes and not _confirm_disclaimer():
        print("Cancelled.")
        sys.exit(0)

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "astimp_repo"
        print(f"Cloning {_REPO_URL} ...")
        _clone_repo(clone_dir)

        images = _collect_images(clone_dir)
        if not images:
            print("Error: no images found in the cloned repository.", file=sys.stderr)
            sys.exit(1)

        args.output_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for src in images:
            dst = args.output_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied += 1

    print(f"Done. Copied {copied} image(s) to {args.output_dir}")
    print("Next step: python scripts/prepare_dataset.py --sources-dir data/sources")


if __name__ == "__main__":
    main()
