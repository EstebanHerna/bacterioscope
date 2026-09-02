"""Generate a set of synthetic test plates with varied clinical scenarios.

Produces PNG images in examples/synthetic/ ready to drop into the Streamlit demo.
Each plate is 540x540 px, simulating a 90 mm Mueller-Hinton agar plate.

Usage:
    python scripts/generate_test_plates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

SIZE = 540
CENTER = (SIZE // 2, SIZE // 2)
PLATE_R = 252
DISK_R = 14
PX_PER_MM = SIZE / (90 * 1.14)

# 6-disk hexagonal layout (angles in degrees, counter-clockwise from 3 o'clock)
_ANGLES_6 = [90, 30, 330, 270, 210, 150]
_RING_6 = 170

# 12-disk layout
_ANGLES_12 = [90, 60, 30, 0, 330, 300, 270, 240, 210, 180, 150, 120]
_RING_12 = 170

PANEL_6 = ["Meropenem", "Ciprofloxacin", "Ampicillin", "Ceftriaxone", "Imipenem", "Gentamicin"]
PANEL_12 = [
    "Meropenem", "Ciprofloxacin", "Ampicillin", "Ceftriaxone",
    "Imipenem", "Gentamicin", "Cefepime", "Piperacillin-Tazo",
    "Ertapenem", "Amikacin", "Levofloxacin", "TMP-SMX",
]


def _positions(angles: list[int], ring: int) -> list[tuple[int, int]]:
    return [
        (CENTER[0] + int(ring * np.cos(np.radians(a))),
         CENTER[1] - int(ring * np.sin(np.radians(a))))
        for a in angles
    ]


def _cat_color(cat: str) -> tuple[int, int, int]:
    if cat == "S":
        return (106, 200, 120)
    if cat == "I":
        return (80, 185, 230)
    return (100, 110, 240)


def _make_plate(
    positions: list[tuple[int, int]],
    zone_radii: list[int],
    categories: list[str],
    names: list[str],
    seed: int = 42,
    illumination_tilt: float = 0.0,
) -> np.ndarray:
    img = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    img[:] = [35, 35, 35]

    agar = np.full((SIZE, SIZE, 3), [150, 183, 205], dtype=np.uint8)
    lawn_color = np.array([134, 163, 183], dtype=np.uint8)
    mask_plate = np.zeros((SIZE, SIZE), dtype=np.uint8)
    cv2.circle(mask_plate, CENTER, PLATE_R, 255, -1)
    agar[mask_plate > 0] = lawn_color

    for (cx, cy), zr in zip(positions, zone_radii):
        zone = np.zeros((SIZE, SIZE), dtype=np.float32)
        cv2.circle(zone, (cx, cy), zr, 1.0, -1)
        zone = cv2.GaussianBlur(zone, (25, 25), 9)
        for c in range(3):
            agar[:, :, c] = np.clip(
                agar[:, :, c].astype(np.float32) + zone * 26, 0, 255
            ).astype(np.uint8)

    rng = np.random.default_rng(seed)
    noise = rng.integers(-8, 9, (SIZE, SIZE, 3), dtype=np.int16)
    agar = np.clip(agar.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if illumination_tilt != 0.0:
        yy, xx = np.mgrid[0:SIZE, 0:SIZE]
        gradient = (xx / SIZE * illumination_tilt * 40).astype(np.int16)
        for c in range(3):
            agar[:, :, c] = np.clip(agar[:, :, c].astype(np.int16) + gradient, 0, 255).astype(np.uint8)

    img[mask_plate > 0] = agar[mask_plate > 0]

    for cx, cy in positions:
        cv2.circle(img, (cx, cy), DISK_R, (230, 230, 222), -1)
        cv2.circle(img, (cx, cy), DISK_R, (188, 188, 180), 1)

    cv2.circle(img, CENTER, PLATE_R, (86, 106, 116), 2)
    cv2.circle(img, CENTER, PLATE_R + 1, (52, 66, 73), 1)

    return img


def _annotated(img: np.ndarray, positions: list[tuple[int, int]],
               zone_radii: list[int], categories: list[str],
               names: list[str]) -> np.ndarray:
    out = img.copy()
    for (cx, cy), zr, cat, name in zip(positions, zone_radii, categories, names):
        color = _cat_color(cat)
        cv2.circle(out, (cx, cy), zr, color, 2)
        diam_mm = round(2 * zr / PX_PER_MM, 1)
        label = f"{name[:5]}: {diam_mm}mm ({cat})"
        cv2.putText(out, label, (cx - 38, cy - zr - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)
    return out


def _mm_to_px(mm: float) -> int:
    return int(mm / 2 * PX_PER_MM)


def main() -> int:
    root = Path(__file__).parent.parent / "examples" / "synthetic"
    out = root
    out_annotated = root / "reference_annotated"
    out.mkdir(parents=True, exist_ok=True)
    out_annotated.mkdir(parents=True, exist_ok=True)

    plates: list[tuple[str, dict]] = [
        # 1. Susceptible majority — organism that responds well to most antibiotics
        ("plate_pan_susceptible", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 10,
            "zone_mm": [27.0, 28.0, 20.0, 26.0, 25.0, 18.0],
        }),
        # 2. MDR — multidrug-resistant: most antibiotics fail
        ("plate_mdr_organism", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 77,
            "zone_mm": [12.0, 10.0, 9.0, 15.0, 11.0, 8.0],
        }),
        # 3. Mixed profile — typical clinical isolate with partial resistance
        ("plate_mixed_sir", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 33,
            "zone_mm": [24.0, 23.0, 11.0, 21.0, 22.5, 16.0],
        }),
        # 4. 12-disk panel — full enterobacteria workup
        ("plate_12disk_panel", {
            "angles": _ANGLES_12, "ring": _RING_12, "names": PANEL_12, "seed": 55,
            "zone_mm": [25.0, 24.0, 10.0, 23.0, 22.0, 18.0, 27.0, 21.0, 23.0, 19.0, 14.0, 16.0],
        }),
        # 5. Carbapenem-resistant — critical alert scenario
        ("plate_carbapenem_resistant", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 91,
            "zone_mm": [11.0, 10.0, 9.0, 9.0, 12.0, 8.0],
        }),
        # 6. Illumination tilt — tests robustness to uneven lighting
        ("plate_uneven_light", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 44,
            "zone_mm": [26.0, 22.0, 14.0, 24.0, 21.0, 17.0],
            "illumination_tilt": 1.0,
        }),
        # 7. Large zones — very susceptible organism with wide halos
        ("plate_large_zones", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 22,
            "zone_mm": [33.0, 35.0, 30.0, 36.0, 32.0, 28.0],
        }),
        # 8. ESBL-like profile — resistant to most cephalosporins, preserved carbapenems
        ("plate_esbl_like", {
            "angles": _ANGLES_6, "ring": _RING_6, "names": PANEL_6, "seed": 66,
            "zone_mm": [27.0, 12.0, 9.0, 11.0, 26.0, 14.0],
        }),
    ]

    generated = []
    for fname, cfg in plates:
        pos = _positions(cfg["angles"], cfg["ring"])
        zone_px = [_mm_to_px(mm) for mm in cfg["zone_mm"]]
        categories = []
        for name, mm in zip(cfg["names"], cfg["zone_mm"]):
            from bacterioscope.classification.clsi import CLSI_2023_ENTEROBACTERIACEAE
            key = name.lower().replace(" ", "_").replace("-", "_")
            bp = CLSI_2023_ENTEROBACTERIACEAE.get(key) or CLSI_2023_ENTEROBACTERIACEAE.get(
                next((k for k in CLSI_2023_ENTEROBACTERIACEAE if k.startswith(key[:5].lower())), "")
            )
            if bp:
                if mm >= bp["S"]:
                    categories.append("S")
                elif mm <= bp["R"]:
                    categories.append("R")
                else:
                    categories.append("I")
            else:
                categories.append("?")

        tilt = cfg.get("illumination_tilt", 0.0)
        plate = _make_plate(pos, zone_px, categories, cfg["names"],
                            seed=cfg["seed"], illumination_tilt=tilt)
        path = out / f"{fname}.png"
        cv2.imwrite(str(path), plate)
        annotated_path = out_annotated / f"{fname}_annotated.png"
        cv2.imwrite(str(annotated_path), _annotated(plate, pos, zone_px, categories, cfg["names"]))
        generated.append(path.name)
        cat_str = "/".join(f"{c}" for c in categories)
        print(f"  {path.name}  [{cat_str}]")

    print(f"\n{len(generated) * 2} images written to examples/synthetic/")
    print("Drop any *.png from examples/synthetic/ (not reference_annotated/) into the Streamlit demo to test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
