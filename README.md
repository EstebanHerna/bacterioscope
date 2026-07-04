# BacterioScope

[![CI](https://github.com/EstebanHerna/bacterioscope/actions/workflows/ci.yml/badge.svg)](https://github.com/EstebanHerna/bacterioscope/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CLSI M100-Ed33](https://img.shields.io/badge/CLSI-M100--Ed33%20(2023)-orange.svg)](https://clsi.org)

**Automated antimicrobial resistance detection from Kirby-Bauer disk diffusion images using deep learning and classical computer vision.**

BacterioScope takes a photograph of a Kirby-Bauer antibiogram plate and returns: detected antibiotic disks, segmented inhibition zones, diameter measurements in millimeters, and S/I/R classification against CLSI 2023 breakpoints. Designed for clinical microbiology labs in low- and middle-income settings where automated AST systems (VITEK, Phoenix) are unavailable.

![BacterioScope pipeline demo](docs/pipeline_demo.gif)

## Why this matters

Antimicrobial resistance kills 1.27 million people per year (Murray et al., 2022). In Colombia, carbapenem-resistant *Klebsiella pneumoniae* is among the most frequent pathogens in healthcare-associated infection outbreaks (INS, 2019-2025). The standard Kirby-Bauer method requires manual zone measurement with a ruler — a slow, error-prone process. BacterioScope automates that measurement pipeline and adds a trained classification model, bringing diagnostic-grade AST analysis to any lab with a smartphone camera.

## Pipeline

```
Input (plate image)
    |
    v
[Calibration] -------- HoughCircles plate detection → pixels per mm
    |
    v
[Disk Detection] ----- YOLOv8 object detection (Hough fallback)
    |
    v
[Zone Segmentation] -- Otsu threshold + watershed (OpenCV)
    |
    v
[Measurement] -------- Pixel-to-mm conversion via plate calibration
    |
    v
[Classification] ----- CLSI M100-Ed33 (2023) breakpoint lookup → S / I / R
    |
    v
[Report] ------------- JSON + annotated image + Streamlit UI + REST API
```

## Quick start

```bash
git clone https://github.com/EstebanHerna/bacterioscope.git
cd bacterioscope
pip install -e ".[all,dev]"

# Run the pipeline on a plate image
python -m bacterioscope analyze path/to/plate.jpg

# Interactive demo (Streamlit)
streamlit run src/bacterioscope/app.py

# REST API
uvicorn bacterioscope.api.routes:app --reload
# POST http://localhost:8000/analyze  (multipart image upload)
# GET  http://localhost:8000/health
```

## Clinical evaluation metrics

The `bacterioscope.evaluation` module computes ISO 20776-2 / FDA clinical agreement metrics. Run against a labeled CSV:

```bash
python scripts/evaluate.py \
  --image-dir data/processed/images \
  --csv      data/processed/labels.csv \
  --output   results/
```

| Metric | Description | Acceptance |
|--------|-------------|------------|
| **CA** | Categorical Agreement — pred = ref | ≥ 90% |
| **EA** | Essential Agreement — diameter within ±2 mm | ≥ 90% |
| **VME** | Very Major Error — pred S when ref R | ≤ 1.5% |
| **ME** | Major Error — pred R when ref S | ≤ 3% |
| **mE** | Minor Error — any I-involving discordance | ≤ 10% |
| **MAE** | Mean Absolute Error of zone diameters | — |
| **r** | Pearson correlation (measured vs. reference mm) | — |

EA definition adapted from ISO 20776-2: diameter within ±2 mm (EUCAST EDef 13.2) rather than the MIC ±1 two-fold dilution classical definition.

## Datasets

- **Dryad/UZH** (Giske et al., 2024): 225 Gram-negative isolates, 862 phenotypic categories including ESBL, AmpC, and carbapenemase producers.
- **Roboflow/KB-AST**: Community-annotated Kirby-Bauer images with bounding boxes.
- **AntibiogramJ reference set**: Benchmark images from Heras et al. (2017).

See `scripts/download_data.py` for automated download.

## Project phases

| Phase | Scope | Status |
|-------|-------|--------|
| **0 — Detection & Measurement** | Disk detection, zone segmentation, diameter measurement, S/I/R classification, Streamlit demo, REST API, evaluation module | Complete |
| **1 — Temporal Prediction** | 6-10 h prediction of 24 h zone diameter | Planned |
| **2 — Clinical Validation** | Validation with clinical isolates, pilot deployment | Planned |

## Development

```bash
pip install -e ".[dev]"      # core + dev tools
pip install -e ".[all,dev]"  # all extras (ML, API, UI) + dev tools

make test                    # pytest
make lint                    # ruff check
mypy src/bacterioscope/      # type check
bandit -r src/ -c pyproject.toml  # security scan
```

Run `notebooks/pipeline_walkthrough.ipynb` for a step-by-step guided tour of the pipeline.

## Research context

This repository is the engineering backbone of an ongoing research collaboration between Systems Engineering and Microbiology at Universidad de los Andes (Bogota, Colombia), supervised by Prof. Astrid Blanco.

**Related publications:**
- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Prediction of Carbapenem Resistance in Klebsiella pneumoniae via Computer Vision Applied to Kirby-Bauer Antibiograms.* Universidad de los Andes. [Preprint]
- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Visual Detection of Bacterial Growth in Blood Cultures via Computer Vision.* Universidad de los Andes. [Preprint]

## Tech stack

- **Detection**: Ultralytics YOLOv8 (PyTorch), OpenCV HoughCircles fallback
- **Segmentation**: OpenCV 4.x, scikit-image (Otsu + watershed)
- **Classification**: CLSI M100-Ed33 (2023) breakpoint tables
- **Evaluation**: ISO 20776-2 / FDA clinical agreement metrics
- **API**: FastAPI + python-multipart
- **Demo**: Streamlit
- **Infrastructure**: Docker, GitHub Actions CI, pytest, ruff, mypy, bandit, gitleaks

## License

MIT

## Authors

- **Esteban A. Hernandez Sulvara** — Systems Engineering, Universidad de los Andes ([GitHub](https://github.com/EstebanHerna))
- **Paula A. Becerra Lara** — Microbiology, Universidad de los Andes
