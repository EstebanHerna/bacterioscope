"""Download public antibiogram image datasets for BacterioScope training and evaluation."""
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
            "University of Zurich SIRscan dataset. "
            "225 Gram-negative isolates, 862 phenotypic categories. "
            "Manual download required from Dryad (license terms)."
        ),
        "auto_download": False,
    },
}


def download_file(url: str, dest: Path) -> None:
    print(f"Downloading {url}...")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        if total > _MAX_DOWNLOAD_BYTES:
            raise ValueError(f"Remote file is {total} bytes, exceeds {_MAX_DOWNLOAD_BYTES} byte cap")
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
            print(f"  Manual download required: {info['url']}")
            dest = DATA_DIR / name
            dest.mkdir(exist_ok=True)
            readme = dest / "DOWNLOAD_INSTRUCTIONS.txt"
            readme.write_text(
                f"Download the dataset manually from:\n{info['url']}\n\n"
                f"Place the downloaded files in this directory ({dest}).\n"
                f"Description: {info['description']}\n"
            )
            print(f"  Instructions saved to {readme}")
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
