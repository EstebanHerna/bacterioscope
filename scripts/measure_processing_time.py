"""Reproduce the per-plate processing time figures cited for the pitch.

Runs the full pipeline on the 80-image real UZH subset and reports mean,
median, min, and max total processing time per plate.

Usage::

    python scripts/measure_processing_time.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig  # noqa: E402

_SUBSET_SIZE = 80


def main() -> int:
    pipeline = BacterioScopePipeline(PipelineConfig())
    paths = sorted(glob.glob("data/raw/dryad_uzh/images_original/*.jpg"))[:_SUBSET_SIZE]

    times_ms = []
    for path in paths:
        try:
            result = pipeline.analyze(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  {Path(path).name}: ERROR {exc}")
            continue
        times_ms.append(result.timings_ms["total_ms"])

    times = np.array(times_ms)
    print(f"n={len(times)} plates")
    print(f"mean={times.mean() / 1000:.2f}s  median={np.median(times) / 1000:.2f}s  "
          f"min={times.min() / 1000:.2f}s  max={times.max() / 1000:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
