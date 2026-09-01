# Methodology and Tools

This document describes the computational methods, clinical standards, and software tools used in BacterioScope Phase 0.

---

## 1. Image acquisition requirements

BacterioScope imposes no requirements on camera model or focal length. The only hard constraints are:

- The full plate (90 mm diameter) must be visible, with at least 5 mm of background visible around the rim.
- The plate must be photographed from directly above (camera axis perpendicular to plate surface, ±15 degrees tolerance).
- Uniform diffuse lighting is strongly preferred; direct point-source lighting that casts disk shadows degrades zone-edge detection.
- Minimum recommended resolution: 1000 × 1000 pixels for the full image.

---

## 2. Calibration

**Module:** `src/bacterioscope/utils/calibration.py`

The pixel-to-millimetre ratio is derived by fitting a Hough circle to the plate rim:

1. Convert image to grayscale.
2. Apply Gaussian blur (kernel 5×5) to suppress noise.
3. Run `cv2.HoughCircles` (HOUGH_GRADIENT) with parameter ranges tuned for a 90 mm plate at typical capture distances (0.5–2 m).
4. Compute `px_per_mm = detected_radius_px / (plate_diameter_mm / 2)`.

The 90 mm diameter is the standardized Petri dish diameter for Kirby-Bauer. Phase 3 will add a second calibration pass that uses the 6 mm antibiotic disk as a reference object, providing a per-disk calibration that is independent of plate-rim visibility.

---

## 3. Disk detection

**Module:** `src/bacterioscope/detection/detector.py`

Phase 0 uses `cv2.HoughCircles` applied to the interior of the plate ROI, searching for circles in the 5–8 mm diameter range (after conversion to pixels via `px_per_mm`). Detection parameters:

| Parameter | Value | Rationale |
|---|---|---|
| `minDist` | `plate_radius_px * 0.3` | Prevents merging adjacent disks |
| `param1` | 50 | Canny high threshold |
| `param2` | 30 | Accumulator threshold |
| `minRadius` | `int(2.0 * px_per_mm)` | 4 mm minimum disk radius |
| `maxRadius` | `int(5.0 * px_per_mm)` | 10 mm maximum disk radius |

Phase 2 will replace HoughCircles with a YOLOv8 model trained on annotated Kirby-Bauer images. The model will simultaneously detect disk bounding boxes and read the printed antibiotic abbreviation from the disk surface, eliminating the manual assignment step.

---

## 4. Zone segmentation

**Module:** `src/bacterioscope/segmentation/watershed.py`

For each detected disk, the segmenter:

1. Crops a square ROI centered on the disk center (radius × 4 px, clamped to image bounds).
2. Converts the ROI to grayscale.
3. Applies Otsu global thresholding to separate the clear inhibition zone (bright) from the bacterial lawn (dark).
4. Performs morphological operations (erosion, dilation) to remove speckle and fill holes.
5. Finds the largest connected contour in the thresholded mask and fits a bounding circle.
6. Reports `diameter_mm = circle_diameter_px / px_per_mm` and the circularity score (`4π × area / perimeter²`).

The disk itself (opaque, 6 mm) is excluded from the contour search by masking the central 6 mm radius before contouring.

---

## 5. CLSI classification

**Module:** `src/bacterioscope/classification/clsi.py`

Breakpoints are from **CLSI M100, 33rd edition (2023)**, Table 2A (Enterobacteriaceae, disk diffusion). The current table covers 15 antibiotics:

Ampicillin, Ampicillin-sulbactam, Piperacillin-tazobactam, Cefazolin, Cefoxitin, Ceftriaxone, Ceftazidime, Cefepime, Aztreonam, Ertapenem, Imipenem, Meropenem, Gentamicin, Ciprofloxacin, Trimethoprim-sulfamethoxazole.

Each antibiotic entry stores `S` (susceptible) and `R` (resistant) zone diameter thresholds in mm. Classification logic:

```
zone_diameter_mm >= breakpoints["S"]  →  S
zone_diameter_mm <= breakpoints["R"]  →  R
otherwise                              →  I (intermediate)
```

Last-line antibiotics (carbapenems: ertapenem, imipenem, meropenem, doripenem) are flagged automatically in reports to alert clinicians to critical resistance patterns.

The version string `BREAKPOINT_TABLE_VERSION = "CLSI M100-Ed33 2023"` is embedded in every `AnalysisResult` for full audit traceability.

---

## 6. Traceability

Every analysis result carries:

| Field | Content |
|---|---|
| `analysis_id` | UUID4 unique to this analysis run |
| `software_version` | BacterioScope version string (from `pyproject.toml`) |
| `commit_hash` | Git short hash of the running code (`unknown` in packaged builds) |
| `breakpoint_table_version` | CLSI edition used |
| `image_sha256` | SHA-256 hex digest of the input image file |
| `timings_ms` | Wall-clock ms per pipeline stage (load, calibrate, detect, segment, classify, annotate) |

This information is included in the JSON output, the HTML report provenance section, and the REST API response.

---

## 7. Clinical evaluation metrics

**Module:** `src/bacterioscope/evaluation/metrics.py`

Metrics follow **ISO 20776-2** and FDA criteria for AST systems:

| Metric | Formula | Target (Phase 3) |
|---|---|---|
| Essential Agreement (EA) | % measurements within ±2 mm of reference | ≥ 90% |
| Categorical Agreement (CA) | % S/I/R classifications matching reference | ≥ 90% |
| Very Major Error (VME) | % false-susceptible (S predicted, R true) | ≤ 1.5% |
| Major Error (ME) | % false-resistant (R predicted, S true) | ≤ 3% |
| Minor Error (mE) | % any other categorical discordance | ≤ 10% |

---

## 8. Measurement accuracy analysis

**Script:** `scripts/validate_measurement.py`

The validation script compares BacterioScope zone diameters against SIRscan reference measurements from the Dryad/UZH dataset:

1. Matches disks by antibiotic label within each isolate.
2. Computes EA (±2 mm), MAE, and Pearson r over all matched pairs.
3. Performs **Bland-Altman analysis**: mean difference, standard deviation of differences, and ±1.96 SD limits of agreement. A non-zero mean difference indicates systematic bias; wide limits of agreement indicate imprecision.
4. Saves scatter and Bland-Altman plots as PNG to `docs/figures/`.
5. Writes `docs/VALIDATION_REPORT.md` with all metrics and dataset provenance.

---

## 9. Reference dataset

**Dryad/UZH SIRscan dataset** (Egli et al., 2023):
- 225 Gram-negative clinical isolates (Enterobacteriaceae and non-fermenters).
- 862 phenotypic categories.
- Zone diameters measured by SIRscan automated reader (calibrated optical system).
- Breakpoints: EUCAST 2023 (note: BacterioScope uses CLSI 2023; only mm-level EA is compared in Phase 0–2).
- License: CC0 1.0 Universal.
- DOI: [10.5061/dryad.5dv41nsfj](https://doi.org/10.5061/dryad.5dv41nsfj)

---

## 10. Quality assurance

| Tool | Purpose | Configuration |
|---|---|---|
| `pytest` | Test runner | 228 tests, 93.9% line coverage, threshold 80% |
| `ruff` | Linting and import sort | `pyproject.toml [tool.ruff]` |
| `mypy` | Static type checking | Strict mode, `pyproject.toml [tool.mypy]` |
| `bandit` | Security scan | `pyproject.toml [tool.bandit]` |
| `gitleaks` | Secret detection | GitHub Actions pre-push hook |
| GitHub Actions CI | Automated test matrix | Python 3.10, 3.11, 3.12 on ubuntu-latest |

---

## 11. Software dependencies

Core runtime dependencies:

| Package | Version | Role |
|---|---|---|
| `numpy` | ≥ 1.24 | Array operations |
| `opencv-python-headless` | ≥ 4.8 | Hough transforms, image I/O, watershed |
| `scikit-image` | ≥ 0.21 | Morphological operations, contour fitting |
| `scikit-learn` | ≥ 1.3 | Statistical utilities |
| `Pillow` | ≥ 10.0 | Image format support |
| `typer` + `rich` | ≥ 0.9 | CLI |

Optional dependencies (installed with `pip install -e ".[all,dev]"`):

| Extra | Packages | Enables |
|---|---|---|
| `ml` | `torch`, `ultralytics` | YOLOv8 inference (Phase 2+) |
| `api` | `fastapi`, `uvicorn`, `pydantic`, `httpx` | REST API |
| `ui` | `streamlit` | Streamlit demo |
| `dev` | `pytest`, `ruff`, `mypy`, `bandit`, etc. | Development toolchain |
