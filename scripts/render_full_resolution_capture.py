"""Render the shipped pipeline's real output on the original, full-resolution photo.

The pipeline analyses a downscaled copy (longer side <= 1400 px). This script
runs it unchanged, then redraws the measured contours, flag rings and mm values
on the *original* photograph by mapping every coordinate back through the
canonical scale factor, so the capture keeps the photo's native detail instead
of upscaling an already-annotated small image. Nothing about the measurement is
altered: same disks, same masks, same flags.

Usage::

    python scripts/render_full_resolution_capture.py
    python scripts/render_full_resolution_capture.py --image examples/real/real_plate_box4.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from survey_pitch_images import DiskAssessment, _assess_disk  # noqa: E402

from bacterioscope.pipeline import (  # noqa: E402
    AnalysisResult,
    BacterioScopePipeline,
    PipelineConfig,
)
from bacterioscope.utils.image import resize_canonical  # noqa: E402
from bacterioscope.utils.visualization import _FLAG_COLOR, stamp_watermark  # noqa: E402

_CONTOUR_COLOR = (240, 240, 240)
_TEXT_OUTLINE_COLOR = (20, 20, 20)
_FLAG_RING_OFFSET_PX = 6


def _scaled_contours(mask: NDArray[np.uint8], k: float) -> list[NDArray[np.int32]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return [np.round(c * k).astype(np.int32) for c in contours]


def _draw_label(image: NDArray[np.uint8], text: str, origin: tuple[int, int], k: float) -> None:
    scale, thickness = 0.5 * k, max(1, int(round(k)))
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(image, text, origin, font, scale, _TEXT_OUTLINE_COLOR, thickness * 3, cv2.LINE_AA)
    cv2.putText(image, text, origin, font, scale, _CONTOUR_COLOR, thickness, cv2.LINE_AA)


def _draw_disk(image: NDArray[np.uint8], idx: int, result: AnalysisResult, k: float) -> None:
    disk, zone = result.disks[idx], result.zones[idx]
    stroke = max(2, int(round(2 * k)))
    if zone.mask is not None:
        cv2.drawContours(image, _scaled_contours(zone.mask, k), -1, _CONTOUR_COLOR, stroke)
    cx, cy = int(round(disk.center_x * k)), int(round(disk.center_y * k))
    cv2.circle(image, (cx, cy), int(round(disk.radius_px * k)), _CONTOUR_COLOR, max(1, stroke // 2))
    if result.flags and result.flags[idx]:
        ring = int(round((zone.radius_px + _FLAG_RING_OFFSET_PX) * k))
        zx, zy = int(round(zone.center_x * k)), int(round(zone.center_y * k))
        cv2.circle(image, (zx, zy), ring, _FLAG_COLOR, stroke)
    label_y = cy - int(round(disk.radius_px * k)) - int(round(10 * k))
    _draw_label(image, f"{zone.diameter_mm:.1f} mm", (cx - int(round(28 * k)), label_y), k)


def render(image_path: Path, output_dir: Path) -> tuple[Path, list[DiskAssessment]]:
    """Run the pipeline and render its result at the photo's native resolution."""
    pipeline = BacterioScopePipeline(PipelineConfig())
    result = pipeline.analyze(image_path)
    native = cv2.imread(str(image_path))
    if native is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    _, scale = resize_canonical(native, PipelineConfig().canonical_max_dimension)
    k = 1.0 / scale
    canvas = native.copy()
    for idx in range(len(result.disks)):
        _draw_disk(canvas, idx, result, k)
    stamp_watermark(canvas)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{image_path.stem}_fullres_annotated.png"
    cv2.imwrite(str(out_path), canvas)
    assessments = [
        a for i in range(len(result.disks))
        if (a := _assess_disk(image_path.name, i, result)) is not None
    ]
    return out_path, assessments


def _tier(a: DiskAssessment) -> str:
    if a.flags:
        return "low confidence (flagged, ring drawn)"
    if a.is_presentable:
        return "clean contour"
    return "intermediate (unflagged, contour visibly squarish)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("examples/real/real_plate_box4.jpg"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/pitch_capture"))
    args = parser.parse_args()

    out_path, assessments = render(args.image, args.output_dir)
    saved = cv2.imread(str(out_path))
    height, width = saved.shape[:2] if saved is not None else (0, 0)
    print(f"Saved {out_path} ({width}x{height})")
    for a in sorted(assessments, key=lambda x: x.disk_index):
        print(
            f"  disk_{a.disk_index:<2} {a.diameter_mm:5.1f} mm  "
            f"fill={a.fill_ratio:.3f}  {_tier(a)}"
        )
    tiers = [_tier(a) for a in assessments]
    for name in dict.fromkeys(tiers):
        print(f"{tiers.count(name):>3} x {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
