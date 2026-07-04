"""Generate the pipeline demonstration GIF saved to docs/pipeline_demo.gif.

Creates a synthetic Kirby-Bauer plate with six antibiotic disks and four
animation frames showing the pipeline stages:
  1. Input plate image
  2. Disk detection
  3. Zone segmentation
  4. S/I/R classification (CLSI 2023)

Usage:
    python scripts/generate_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Plate geometry
# ---------------------------------------------------------------------------
SIZE = 540
CENTER = (SIZE // 2, SIZE // 2)
PLATE_R = 252          # plate radius in pixels
DISK_R = 14            # antibiotic disk radius (within HoughCircles range 10-40)
PX_PER_MM = SIZE / (90 * 1.14)   # ≈ 5.26 px/mm for a 90 mm plate at this scale

# Six disk positions on a hexagonal ring, radius 170 px from center
_ANGLES = [90, 30, 330, 270, 210, 150]
POSITIONS: list[tuple[int, int]] = [
    (
        CENTER[0] + int(170 * np.cos(np.radians(a))),
        CENTER[1] - int(170 * np.sin(np.radians(a))),
    )
    for a in _ANGLES
]

# (antibiotic, zone_radius_px, category, color_BGR)
DISKS = [
    ("Meropenem",     76, "S", (30, 180, 30)),
    ("Ciprofloxacin", 62, "I", (20, 180, 220)),
    ("Ampicillin",    36, "R", (30, 30, 210)),
    ("Ceftriaxone",   82, "S", (30, 180, 30)),
    ("Imipenem",      64, "I", (20, 180, 220)),
    ("Gentamicin",    44, "S", (30, 180, 30)),
]


def _make_base_plate() -> np.ndarray:
    """Create a realistic synthetic Mueller-Hinton agar plate."""
    img = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)

    # Dark background outside the plate
    img[:] = [38, 38, 38]

    # Agar base: cream/beige
    agar = np.full((SIZE, SIZE, 3), [150, 183, 205], dtype=np.uint8)

    # Bacterial lawn: slightly darker and cooler
    lawn_color = np.array([136, 165, 186], dtype=np.uint8)
    mask_plate = np.zeros((SIZE, SIZE), dtype=np.uint8)
    cv2.circle(mask_plate, CENTER, PLATE_R, 255, -1)
    agar[mask_plate > 0] = lawn_color

    # Inhibition zones: lighter halos with blurred edges
    for (cx, cy), (_, zr, _, _) in zip(POSITIONS, DISKS):
        zone = np.zeros((SIZE, SIZE), dtype=np.float32)
        cv2.circle(zone, (cx, cy), zr, 1.0, -1)
        zone = cv2.GaussianBlur(zone, (25, 25), 9)
        for c in range(3):
            agar[:, :, c] = np.clip(
                agar[:, :, c].astype(np.float32) + zone * 28, 0, 255
            ).astype(np.uint8)

    # Subtle granular texture (simulates agar surface)
    rng = np.random.default_rng(42)
    noise = rng.integers(-7, 8, (SIZE, SIZE, 3), dtype=np.int16)
    agar = np.clip(agar.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    img[mask_plate > 0] = agar[mask_plate > 0]

    # Disk circles: off-white paper
    for cx, cy in POSITIONS:
        cv2.circle(img, (cx, cy), DISK_R, (232, 232, 225), -1)
        cv2.circle(img, (cx, cy), DISK_R, (190, 190, 183), 1)

    # Plate border
    cv2.circle(img, CENTER, PLATE_R, (88, 108, 118), 2)
    cv2.circle(img, CENTER, PLATE_R + 1, (55, 68, 75), 1)

    return img


def _add_step_label(img: np.ndarray, text: str) -> np.ndarray:
    out = img.copy()
    cv2.rectangle(out, (0, SIZE - 40), (SIZE, SIZE), (22, 22, 22), -1)
    cv2.putText(
        out, text, (12, SIZE - 13),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (210, 210, 210), 1, cv2.LINE_AA,
    )
    return out


def _frame_detection(base: np.ndarray) -> np.ndarray:
    out = base.copy()
    for (cx, cy), (name, _, _, _) in zip(POSITIONS, DISKS):
        cv2.circle(out, (cx, cy), DISK_R + 2, (220, 220, 50), 2)
        cv2.circle(out, (cx, cy), 3, (220, 220, 50), -1)
        cv2.putText(
            out, name[:4], (cx - 14, cy - DISK_R - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.36, (220, 220, 50), 1, cv2.LINE_AA,
        )
    return _add_step_label(out, "Step 2: Disk detection (HoughCircles)")


def _frame_segmentation(base: np.ndarray) -> np.ndarray:
    out = base.copy()
    for (cx, cy), (_, zr, cat, color) in zip(POSITIONS, DISKS):
        cv2.circle(out, (cx, cy), zr, color, 2)
        diam_mm = round(2 * zr / PX_PER_MM, 1)
        cv2.putText(
            out, f"{diam_mm}mm", (cx - 20, cy - zr - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA,
        )
    return _add_step_label(out, "Step 3: Zone segmentation + diameter measurement")


def _frame_classified(base: np.ndarray) -> np.ndarray:
    out = base.copy()
    for (cx, cy), (name, zr, cat, color) in zip(POSITIONS, DISKS):
        cv2.circle(out, (cx, cy), zr, color, 2)
        cv2.circle(out, (cx, cy), DISK_R, (232, 232, 225), -1)
        diam_mm = round(2 * zr / PX_PER_MM, 1)
        label = f"{name[:5]}: {diam_mm}mm ({cat})"
        cv2.putText(
            out, label, (cx - 36, cy - zr - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA,
        )
    return _add_step_label(out, "Step 4: S/I/R classification (CLSI M100-Ed33, 2023)")


def _bgr_to_pil(img: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def main() -> int:
    out_dir = Path(__file__).parent.parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    base = _make_base_plate()

    frame_step1 = _add_step_label(base, "Step 1: Input plate image")
    frame_step2 = _frame_detection(base)
    frame_step3 = _frame_segmentation(base)
    frame_step4 = _frame_classified(base)

    frames = [_bgr_to_pil(f) for f in [frame_step1, frame_step2, frame_step3, frame_step4]]
    durations = [1800, 1800, 1800, 2800]

    gif_path = out_dir / "pipeline_demo.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"GIF written: {gif_path}  ({gif_path.stat().st_size // 1024} KB)")

    # Also save individual PNG frames for the notebook
    frame_names = ["plate_original", "plate_detected", "plate_zones", "plate_classified"]
    for name, frm in zip(frame_names, [frame_step1, frame_step2, frame_step3, frame_step4]):
        p = out_dir / f"{name}.png"
        cv2.imwrite(str(p), frm)
        print(f"Frame saved: {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
