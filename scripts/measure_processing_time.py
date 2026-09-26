"""Reproduce the per-plate processing time figures cited for the pitch.

Runs the full pipeline on the 80-image real UZH subset and reports mean,
median, min, and max total processing time per plate, plus the slowest
plates with their disk count and dominant stage, so any explanation of the
worst case is read off the measurement instead of assumed.

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
_SLOWEST_SHOWN = 5


def main() -> int:
    pipeline = BacterioScopePipeline(PipelineConfig())
    paths = sorted(glob.glob("data/raw/dryad_uzh/images_original/*.jpg"))[:_SUBSET_SIZE]

    times_ms = []
    per_plate: list[tuple[float, str, int, str]] = []
    for path in paths:
        try:
            result = pipeline.analyze(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  {Path(path).name}: ERROR {exc}")
            continue
        total = result.timings_ms["total_ms"]
        times_ms.append(total)
        stages = {k: v for k, v in result.timings_ms.items() if k != "total_ms"}
        dominant = max(stages, key=lambda k: stages[k])
        per_plate.append((total, Path(path).name, len(result.disks), dominant))

    times = np.array(times_ms)
    print(f"n={len(times)} plates")
    print(f"mean={times.mean() / 1000:.2f}s  median={np.median(times) / 1000:.2f}s  "
          f"min={times.min() / 1000:.2f}s  max={times.max() / 1000:.2f}s")
    print(f"Slowest {_SLOWEST_SHOWN} plates:")
    for total, name, n_disks, dominant in sorted(per_plate, reverse=True)[:_SLOWEST_SHOWN]:
        print(f"  {name}: {total / 1000:.2f}s, {n_disks} disks, dominant stage {dominant}")
    counts = np.array([n for _, _, n, _ in per_plate])
    print(f"Pearson r (disk count vs total time) = {np.corrcoef(counts, times)[0, 1]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
