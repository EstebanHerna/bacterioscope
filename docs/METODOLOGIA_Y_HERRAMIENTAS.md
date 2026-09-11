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

The pixel-to-millimetre ratio is derived by fitting a Hough circle to the plate rim (`detect_plate_circle()` / `calibrate_px_per_mm()`):

1. Convert image to grayscale, apply Gaussian blur (15×15) to suppress noise.
2. Run `cv2.HoughCircles`, sweeping `param2` (40, 30, 20) until a circle is found, radius searched in `[min(h,w)//4, min(h,w)//2]`.
3. Compute `px_per_mm = (detected_radius_px * 2) / plate_diameter_mm` (90 mm default).

Disk-based calibration (`calibrate_from_disk_radius_px()` + `refine_disk_radius_px()`) exists and was investigated directly rather than left as a Phase 3 promise: even measured correctly and independently of the plate-rim estimate, it underperforms plate-rim calibration (28.8% vs 32.9% identity-matched EA on the real-photo validation set) -- a measurement-theory limit, not a bug, since the same edge-detection noise is a much larger relative error against a ~50-60px disk than a ~550-600px plate. `use_disk_calibration` stays `False` by default. See `docs/VALIDATION_REPORT.md` and `docs/LIMITACIONES.md` section 3 for the measured numbers, and do not describe disk calibration as more robust without re-reading that finding.

**Open finding, not yet fixed**: direct visual audit found the UZH validation dataset's plates are square, cropped to fill nearly the entire frame -- not round plates with visible background, which is what `detect_plate_circle()` is designed for and what a real phone photograph looks like. The detector still returns a circle on every UZH image, but its diameter sits suspiciously close to the detector's own search ceiling while its centre is unstable across images -- evidence it is not reliably finding a real boundary on this specific dataset. See `docs/LIMITACIONES.md` section 9.

---

## 3. Disk detection

**Module:** `src/bacterioscope/detection/detector.py`

Phase 0's working detector is `cv2.HoughCircles`, calibration-aware: once `px_per_mm` is known, the search radius is derived from the physical 6 mm disk diameter (`_hough_search_window()`) instead of a fixed pixel range, and the accumulator threshold (`param2`) is swept across `(50, 45, 40, 35, 30, 25, 20)`, taking the disk count that holds stable across the longest run of consecutive values (`_hough_stable_circles()`) -- no single fixed `param2` worked across both real photos and synthetic test plates.

A Phase 2 single-class "disk" YOLOv8 model (`data/models/single_class/`) also exists and is real, not experimental: mAP50=0.995 on its own held-out test split, and matches or slightly beats Hough on real-photo disk count (76-77.5% vs 73.8% exact match) once its confidence threshold is properly tuned (~0.28, not the untuned 0.5 an earlier comparison used). It is not yet the pipeline's default -- that is a deployment decision (added torch/ultralytics dependency, model-load latency, sharper threshold sensitivity than Hough has), not an accuracy verdict. Either detector still resolves antibiotic *identity* through `panels/manager.py` (fixed panel + angular position), not by reading the printed label -- a separate, still-unsolved 29-class label-reading problem (mAP50=0.096, not usable).

---

## 4. Zone segmentation

**Module:** `src/bacterioscope/segmentation/watershed.py`

For each detected disk, `ZoneSegmenter.segment_all()`:

1. Crops a square ROI centred on the disk (`margin_factor=4.0 * disk.radius_px`, capped by two geometric bounds in `_search_radius()`: never past half the distance to the nearest other disk, and never past an absolute 15mm plausible-zone-radius ceiling).
2. Converts to grayscale, Gaussian-blurs (5×5).
3. Computes the Otsu threshold **with the disk itself excluded from the histogram** (`_otsu_excluding_disk()`) -- the paper disk is almost always a far stronger bright/dark signal than the actual zone-vs-lawn contrast (sometimes only 15 grey levels on real photos), so including it made Otsu lock onto disk-vs-everything instead of zone-vs-lawn, filling the entire crop. This is a measured fix, not a design assumption: identity-matched EA moved 24.1% -> 32.9% from this change alone.
4. Restricts the binary mask to this disk's own **Voronoi cell** (nearest-disk-centre partition against every other detected disk), so a confluent neighbour's zone is never counted as this disk's own.
5. Morphological close then open (5×5 kernel) to remove speckle and fill small holes.
6. Finds the contour closest to the disk centre and fits `cv2.minEnclosingCircle`.
7. Reports `diameter_mm = circle_diameter_px / px_per_mm` and circularity (`4π × area / perimeter²`).

CLAHE contrast enhancement exists as an option (`use_clahe`) but is not exposed anywhere in the running pipeline and, measured directly, makes results worse (EA 32.9% -> 24.7%) -- left off by design, not oversight.

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
4. Saves scatter and Bland-Altman plots as PNG to `data/processed/validation_figures/`.
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
| `pytest` | Test runner | 258 tests, 95.3% line coverage, threshold 80% |
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
