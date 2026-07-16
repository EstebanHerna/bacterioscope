# BacterioScope — Development Roadmap

> "La tecnología al servicio de la salud pública."

This document describes the five development phases of BacterioScope. Each phase builds on the previous one and has clearly defined deliverables and acceptance criteria.

---

## Phase 0 — End-to-end pipeline and CI baseline

**Status: Complete**

### Goal

Establish a working end-to-end pipeline from raw plate photograph to S/I/R report, with full test coverage and a green CI, before any ML model is trained.

### Deliverables

- **Calibration:** plate rim detected by Hough Circle Transform; px/mm ratio computed for every image regardless of camera distance.
- **Disk detection:** HoughCircles fallback that locates antibiotic disks geometrically, no ML required.
- **Zone segmentation:** per-disk Otsu thresholding + morphological cleanup + contour fitting returns zone diameter in px and mm.
- **CLSI classifier:** lookup table for CLSI M100-Ed33 (2023), 15 antibiotics, Enterobacteriaceae; returns S/I/R and breakpoints.
- **Streamlit demo:** upload image, assign antibiotic per disk via dropdown, see live S/I/R classification and downloadable report.
- **CLI:** `python -m bacterioscope analyze <image>` with Rich-formatted output.
- **REST API:** FastAPI with `/health` and `/analyze` endpoints, Pydantic v2 schemas, 50 MB file-size guard.
- **Evaluation module:** CA, EA (±2 mm), VME, ME, mE per ISO 20776-2; Markdown + HTML report generation.
- **Test suite:** 107 tests covering all modules; mirrors `src/` structure.
- **CI:** GitHub Actions, Python 3.10 / 3.11 / 3.12; ruff, mypy strict, bandit, gitleaks, pytest.

### Acceptance criteria

- All 107 tests pass on every Python version in CI.
- `ruff check`, `mypy`, `bandit` report zero violations.
- `streamlit run src/bacterioscope/app.py` loads and processes `docs/plate_original.png` without errors.

---

## Phase 1 — Dataset curation and annotation

**Status: Planned**

### Goal

Prepare a clean, labelled training and validation set from the Dryad/UZH public dataset so that Phase 2 model training has reproducible inputs.

### Dataset

**Dryad/UZH (Giske et al., 2024):** 225 Gram-negative clinical isolates, 862 phenotypic categories. Includes ESBL, AmpC, and carbapenemase-producing strains. Full clinical ground truth (zone diameter in mm and S/I/R per antibiotic per isolate).

Download: `python scripts/download_data.py`

### Tasks

1. **Download and integrity check:** verify SHA-256 checksums; guard against zip-slip.
2. **Image preprocessing:** normalize brightness and contrast; crop to plate region; save to `data/processed/images/`.
3. **Disk annotation:** draw bounding boxes around each disk and label with the antibiotic name. Format: YOLO v8 `.txt` (class x_center y_center width height, normalized). Save to `data/processed/labels/`.
4. **Ground-truth CSV:** one row per (image, disk) with columns `image_id`, `antibiotic`, `zone_diameter_mm_reference`, `category_reference`.
5. **Train/val/test split:** 70/15/15 stratified by organism and resistance profile to avoid leakage.
6. **Dataset card:** document class distribution, split sizes, and known biases in `data/processed/README.md`.

### Acceptance criteria

- Annotation coverage >= 95% of disks across all 225 isolates.
- Ground-truth CSV has no missing `zone_diameter_mm_reference` values.
- Train/val/test split documented and reproducible via fixed random seed.

---

## Phase 2 — YOLOv8 training: disk detection and antibiotic label reading

**Status: Planned**

### Goal

Train a YOLOv8 model that simultaneously detects each disk and reads the printed antibiotic abbreviation from its surface, removing the manual assignment step that exists in Phase 0.

### Architecture decision

A single YOLOv8 model with one class per antibiotic (15 classes for Enterobacteriaceae) handles both localization and label recognition. The printed abbreviation on the disk (e.g. CIP, MEM, AMP) is treated as a visual class. No OCR pipeline, no secondary classifier.

### Tasks

1. **Baseline training:** train YOLOv8n on the Phase 1 dataset; establish mAP@0.5 baseline.
2. **Scale-up:** train YOLOv8s and YOLOv8m; compare accuracy vs. inference time.
3. **Augmentation:** random brightness/contrast, blur, rotation, perspective warp to simulate variable lighting and camera angles.
4. **Integration:** replace `HoughCircles` fallback in `detector.py` with YOLO inference when weights are present. The fallback path is preserved for offline use.
5. **Demo update:** remove the per-disk antibiotic selectbox from the Streamlit UI when YOLO weights are loaded; replace with the model's predicted label and confidence score.
6. **Model card:** document training data, hyperparameters, per-class AP, and failure modes in `data/models/model_card.md`.

### Acceptance criteria

- mAP@0.5 >= 0.85 on the held-out test split.
- Per-class AP >= 0.75 for all 15 antibiotic classes.
- Inference time <= 500 ms per image on CPU (no GPU required at deployment).
- All existing 107 tests still pass with the new detector integrated.

---

## Phase 3 — Millimetre calibration and quantitative clinical validation

**Status: Planned**

### Goal

Validate that BacterioScope's zone diameter measurements and S/I/R classifications meet the accuracy thresholds required for clinical use under ISO 20776-2.

### Calibration method

Each antibiotic disk has a standard diameter of **6 mm**. This physical reference is always present in the image. Phase 3 replaces the plate-rim Hough calibration with a disk-size calibration: the detected disk radius in pixels is divided by 3 mm to obtain px/mm for that image. This is more robust than rim detection because the disk is always sharp and well-contrasted.

### Validation protocol

1. Run the full pipeline (Phase 2 detector + Phase 3 calibration + watershed + CLSI classifier) on the held-out test split from Phase 1.
2. Compare each measured `zone_diameter_mm` against `zone_diameter_mm_reference` from the ground-truth CSV.
3. Compare each predicted S/I/R category against `category_reference`.
4. Compute all five metrics using `bacterioscope.evaluation.metrics`.

### Target metrics

| Metric | Target |
|---|---|
| Essential Agreement (EA, ±2 mm) | >= 90% |
| Categorical Agreement (CA) | >= 90% |
| Very Major Error (VME) | <= 1.5% |
| Major Error (ME) | <= 3% |
| Minor Error (mE) | <= 10% |

### Deliverables

- Calibration update in `utils/calibration.py` using the 6 mm disk reference.
- Validation report generated by `bacterioscope.evaluation.report` saved to `results/validation_report.md`.
- Confusion matrix (S/I/R x S/I/R) and per-antibiotic breakdown.
- Bland-Altman plot of measured vs. reference zone diameters.

### Acceptance criteria

- All five metrics meet or exceed their targets on the test split.
- Validation report is reproducible from the same test split and model weights.

---

## Phase 4 — Open-source packaging and public deployment

**Status: Planned**

### Goal

Make BacterioScope accessible to clinical microbiology labs and to the research community without requiring local Python installation.

### Tasks

1. **Streamlit Community Cloud deployment:** public demo at a stable URL; read-only, no patient data stored.
2. **Docker image:** production-ready, non-root, published to GitHub Container Registry. Single command: `docker run ghcr.io/estebanHerna/bacterioscope:latest`.
3. **PyPI release:** `pip install bacterioscope` installs the core pipeline without ML/API/UI extras.
4. **Versioned model weights:** Phase 2 weights published as a GitHub Release asset; `download_data.py` downloads and verifies them.
5. **Documentation site:** auto-generated from docstrings with MkDocs + Material theme; hosted on GitHub Pages.
6. **Peer-reviewed write-up:** methods, dataset, and validation results submitted to a clinical microbiology or medical informatics venue.

### Acceptance criteria

- Public Streamlit demo processes an uploaded image end-to-end in under 10 seconds.
- `pip install bacterioscope && python -m bacterioscope version` works on a clean Python 3.10 environment.
- Documentation site covers installation, API reference, and the clinical evaluation report.

---

## Summary

| Phase | Key output | Status |
|---|---|---|
| F0 | Pipeline + CI baseline, 107 tests | **Complete** |
| F1 | Annotated Dryad/UZH dataset, ground-truth CSV | Planned |
| F2 | YOLOv8 disk detector with antibiotic label reading | Planned |
| F3 | Disk-calibrated mm measurement, full clinical validation | Planned |
| F4 | PyPI package, Docker image, public demo, documentation | Planned |
