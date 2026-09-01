"""Download and extract public antibiogram datasets for BacterioScope.

Dryad/UZH dataset — manual download
-------------------------------------
The UZH SIRscan dataset (Egli et al., 2023) is published under CC0 1.0 and is freely
available on Dryad. Dryad requires a manual browser step to generate the download link.

1. Open https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj in a browser.
2. Click "Download dataset" and accept Dryad terms of service.
3. Save the downloaded ZIP to data/raw/   (keep the original filename).
4. Run: python scripts/download_data.py
5. Run: python scripts/prepare_dataset.py

The outer ZIP contains three inner ZIPs (images_original.zip, images_measured.zip,
Tables.zip) plus a README.md.  This script extracts all layers automatically.

Roboflow/KB-AST dataset — manual download
------------------------------------------
Download the YOLOv8-format version of the Kirby-Bauer antibiotic disk dataset from
Roboflow and save the ZIP to data/raw/ (keep the original filename, e.g.
Antibiotic.v6i.yolov8.zip).  This script extracts it to data/raw/roboflow_yolo/.

Citation — Dryad/UZH:
    Egli A, et al. (2023). Automated reading of disk diffusion antibiograms.
    Dryad. https://doi.org/10.5061/dryad.5dv41nsfj
"""

from __future__ import annotations

import zipfile
from pathlib import Path

DATA_DIR = Path("data/raw")

_MAX_EXTRACT_BYTES: int = 10 * 1024 * 1024 * 1024  # 10 GB uncompressed cap
_MAX_COMPRESSION_RATIO: float = 100.0  # zip bomb threshold

_DATASETS: dict[str, dict[str, object]] = {
    "dryad_uzh": {
        "description": (
            "University of Zurich SIRscan dataset (Egli et al., 2023). "
            "225 Gram-negative isolates, 862 phenotypic categories. CC0 1.0."
        ),
        "zip_globs": ["doi_10_5061_dryad*.zip", "dryad_uzh.zip", "dryad*.zip"],
        "extract_dir": "dryad_uzh",
        "nested_zips": True,
    },
    "roboflow_yolo": {
        "description": (
            "Roboflow KB-AST Kirby-Bauer disk dataset with YOLOv8 annotations. "
            "train/val/test splits, bounding boxes per disk."
        ),
        "zip_globs": ["Antibiotic*.yolov8.zip", "*.yolov8.zip", "roboflow*.zip"],
        "extract_dir": "roboflow_yolo",
        "nested_zips": False,
    },
}


def _find_zip(globs: list[str]) -> Path | None:
    for pattern in globs:
        matches = sorted(DATA_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def _safe_extract(zip_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        entries = zf.infolist()
        total_uncompressed = sum(e.file_size for e in entries)
        total_compressed = sum(e.compress_size for e in entries)
        if total_uncompressed > _MAX_EXTRACT_BYTES:
            raise ValueError(
                f"Archive would expand to {total_uncompressed} bytes, "
                f"exceeds cap of {_MAX_EXTRACT_BYTES} bytes"
            )
        ratio = (total_uncompressed / total_compressed) if total_compressed > 0 else 0.0
        if ratio > _MAX_COMPRESSION_RATIO:
            raise ValueError(
                f"Zip bomb rejected: ratio {total_uncompressed / total_compressed:.0f}x"
            )
        for member in zf.namelist():
            member_path = (dest_dir / member).resolve()
            if not member_path.is_relative_to(dest_resolved):
                raise ValueError(f"Zip slip rejected: {member!r} escapes destination")
            zf.extract(member, dest_dir)
    print(f"    Extracted {zip_path.name} -> {dest_dir}")


def _extract_nested(outer_dest: Path) -> None:
    for inner_zip in sorted(outer_dest.glob("*.zip")):
        sub_dir = outer_dest / inner_zip.stem
        if sub_dir.exists():
            print(f"    Already extracted: {inner_zip.name}")
            continue
        sub_dir.mkdir(parents=True, exist_ok=True)
        print(f"    Extracting inner ZIP: {inner_zip.name}")
        _safe_extract(inner_zip, sub_dir)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("BacterioScope Dataset Downloader")
    print("=" * 50)

    for name, info in _DATASETS.items():
        print(f"\n--- {name} ---")
        print(f"  {info['description']}")

        globs: list[str] = info["zip_globs"]  # type: ignore[assignment]
        zip_path = _find_zip(globs)
        dest_dir = DATA_DIR / str(info["extract_dir"])

        if zip_path is None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            instructions = dest_dir / "DOWNLOAD_INSTRUCTIONS.txt"
            instructions.write_text(
                f"Dataset: {name}\n"
                f"Description: {info['description']}\n\n"
                "Download the ZIP manually and save it to data/raw/, "
                "then run: python scripts/download_data.py\n"
            )
            print("  ZIP not found. Place the ZIP in data/raw/ and re-run this script.")
            print(f"  Instructions saved to {instructions}")
            continue

        print(f"  ZIP found: {zip_path.name} ({zip_path.stat().st_size // 1_048_576} MB)")

        sentinels = (
            list(dest_dir.glob("README*"))
            + list(dest_dir.glob("*.zip"))
            + list(dest_dir.glob("data.yaml"))
        )
        already_done = dest_dir.exists() and bool(sentinels)
        if already_done:
            print(f"  Already extracted to {dest_dir} — skipping.")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Extracting to {dest_dir}...")
            _safe_extract(zip_path, dest_dir)

        if info["nested_zips"]:
            print("  Extracting nested ZIPs...")
            _extract_nested(dest_dir)

    print("\nDone. Check data/raw/ for extracted datasets.")
    print("Next step: python scripts/prepare_dataset.py")


if __name__ == "__main__":
    main()
