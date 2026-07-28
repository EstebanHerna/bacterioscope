"""Download public antibiogram image datasets for BacterioScope training and evaluation.

Dryad/UZH dataset — manual download instructions
-------------------------------------------------
The UZH SIRscan dataset (Egli et al., 2023) is published under the CC0 1.0 Universal
public-domain dedication and is freely available on Dryad. Dryad requires accepting the
terms of service through their web interface before any download can begin, which prevents
fully automated retrieval. Follow these steps once:

1. Open https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj in a browser.
2. Click the "Download dataset" button (top-right area of the page).
3. If prompted, create a free Dryad account and accept the terms of service.
4. Save the downloaded ZIP archive to data/raw/dryad_uzh.zip.
5. Run: python scripts/download_data.py
   The script will extract and verify the archive structure.
6. Run: python scripts/prepare_dataset.py
   This normalises the measurements CSV and image paths for the validation pipeline.

Expected extracted structure (may vary by Dryad version):
    data/raw/dryad_uzh/
        *.jpg or *.png          — plate photographs, one per isolate
        measurements.csv        — SIRscan zone diameters and EUCAST categories
        README.txt              — dataset description from the authors

Citation:
    Egli A, et al. (2023). Automated reading of disk diffusion antibiograms.
    Dataset on Dryad. https://doi.org/10.5061/dryad.5dv41nsfj
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import httpx

DATA_DIR = Path("data/raw")

_MAX_DOWNLOAD_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB hard cap
_MAX_EXTRACT_BYTES: int = 10 * 1024 * 1024 * 1024  # 10 GB uncompressed cap
_MAX_COMPRESSION_RATIO: float = 100.0  # zip bomb threshold

DATASETS = {
    "dryad_uzh": {
        "url": "https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj",
        "description": (
            "University of Zurich SIRscan dataset (Egli et al., 2023). "
            "225 Gram-negative isolates, 862 phenotypic categories. "
            "CC0 1.0 license. Manual browser download required (see module docstring)."
        ),
        "auto_download": False,
        "zip_name": "dryad_uzh.zip",
        "extract_dir": "dryad_uzh",
    },
}


def download_file(url: str, dest: Path) -> None:
    print(f"Downloading {url}...")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        if total > _MAX_DOWNLOAD_BYTES:
            raise ValueError(
                f"Remote file is {total} bytes, exceeds {_MAX_DOWNLOAD_BYTES} byte cap"
            )
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > _MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"Download aborted: exceeded {_MAX_DOWNLOAD_BYTES} byte cap")
                if total > 0:
                    pct = downloaded / total * 100
                    print(f"\r  {pct:.1f}% ({downloaded}/{total} bytes)", end="", flush=True)
    print()


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    print(f"Extracting {zip_path.name}...")
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        entries = zf.infolist()
        total_compressed = sum(e.compress_size for e in entries)
        total_uncompressed = sum(e.file_size for e in entries)
        if total_uncompressed > _MAX_EXTRACT_BYTES:
            raise ValueError(
                f"Archive would expand to {total_uncompressed} bytes, "
                f"exceeds {_MAX_EXTRACT_BYTES} byte cap"
            )
        if total_compressed > 0:
            ratio = total_uncompressed / total_compressed
            if ratio > _MAX_COMPRESSION_RATIO:
                raise ValueError(
                    f"Zip bomb rejected: compression ratio {ratio:.0f}x "
                    f"exceeds {_MAX_COMPRESSION_RATIO}x limit"
                )
        for member in zf.namelist():
            member_path = (dest_dir / member).resolve()
            if not member_path.is_relative_to(dest_resolved):
                raise ValueError(f"Zip slip rejected: {member!r} escapes destination directory")
            zf.extract(member, dest_dir)
    print(f"  Extracted to {dest_dir}")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("BacterioScope Dataset Downloader")
    print("=" * 50)

    for name, info in DATASETS.items():
        print(f"\n--- {name} ---")
        print(f"  {info['description']}")

        if not info["auto_download"]:
            dest = DATA_DIR / info["extract_dir"]
            dest.mkdir(parents=True, exist_ok=True)
            instructions = dest / "DOWNLOAD_INSTRUCTIONS.txt"
            instructions.write_text(
                "DRYAD/UZH DATASET — DOWNLOAD INSTRUCTIONS\n"
                "==========================================\n\n"
                f"Dataset URL: {info['url']}\n\n"
                "Steps:\n"
                "  1. Open the URL above in a browser.\n"
                "  2. Click 'Download dataset' and accept Dryad terms of service.\n"
                f"  3. Save the ZIP file as:  data/raw/{info['zip_name']}\n"
                "  4. Run: python scripts/download_data.py\n"
                "     (this script will extract and validate the archive)\n"
                "  5. Run: python scripts/prepare_dataset.py\n\n"
                f"Description: {info['description']}\n"
            )
            zip_path = DATA_DIR / info["zip_name"]
            if zip_path.exists():
                print(f"  ZIP found at {zip_path} — extracting...")
                extract_zip(zip_path, dest)
            else:
                print(f"  ZIP not found. Instructions saved to {instructions}")
            continue

        dest_file = DATA_DIR / f"{name}.zip"
        if dest_file.exists():
            print(f"  Already downloaded: {dest_file}")
        else:
            download_file(info["url"], dest_file)

        dest_dir = DATA_DIR / name
        if not dest_dir.exists():
            extract_zip(dest_file, dest_dir)

    print("\nDone. Check data/raw/ for downloaded datasets.")


if __name__ == "__main__":
    main()
