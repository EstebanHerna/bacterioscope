# BacterioScope

[![CI](https://github.com/EstebanHerna/bacterioscope/actions/workflows/ci.yml/badge.svg)](https://github.com/EstebanHerna/bacterioscope/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CLSI M100-Ed33](https://img.shields.io/badge/CLSI-M100--Ed33%20(2023)-orange.svg)](https://clsi.org)

**Automated antimicrobial resistance detection from Kirby-Bauer disk diffusion photographs.**

BacterioScope takes a photograph of a standard antibiogram plate and returns, within seconds, the detected antibiotic disks, their inhibition zone diameters in millimetres, and an S/I/R classification against CLSI M100-Ed33 (2023) breakpoints. Built for clinical microbiology labs in low-resource settings where automated AST systems (VITEK, MicroScan, Phoenix) are unavailable.

![BacterioScope pipeline demo](docs/pipeline_demo.gif)

---

## Background — what is a Kirby-Bauer antibiogram?

A **Kirby-Bauer disk diffusion test** (also called an antibiogram) is the standard method used in clinical labs worldwide to determine whether a bacterium is resistant or susceptible to antibiotics. Here is how it works:

1. A Petri dish filled with agar (a jelly-like growth medium) is spread with the bacteria isolated from the patient.
2. Small paper disks, each pre-soaked in a different antibiotic, are placed on the agar surface.
3. The plate is incubated overnight at 37 °C.
4. Antibiotics diffuse outward from each disk. Where the concentration is high enough, bacteria cannot grow — leaving a clear circular area called the **inhibition zone**.
5. A technician measures the **diameter of the inhibition zone** in millimetres with a ruler and compares it against a reference table published by CLSI.

The further the inhibition zone extends, the more effective the antibiotic is against that particular bacterium.

### What do S, I, and R mean?

| Category | Full name | Clinical meaning |
|---|---|---|
| **S** | Susceptible | Standard dosing is expected to be effective. |
| **I** | Intermediate | May work at higher doses or at infection sites where the drug concentrates (e.g. urinary tract for ciprofloxacin). |
| **R** | Resistant | The antibiotic is unlikely to work at achievable concentrations. Choose a different drug. |

---

## How BacterioScope works

```
Photograph of plate (JPEG / PNG / TIFF)
    │
    ▼
 1. CALIBRATION  ──────  Detects the plate rim with Hough Circle Transform.
    │                     Computes pixels-per-mm so all measurements are in
    │                     real physical units, regardless of camera distance.
    ▼
 2. DISK DETECTION ────  Locates each paper antibiotic disk.
    │                     • Phase 1 (planned): YOLOv8 reads the printed label
    │                       and returns the antibiotic name automatically.
    │                     • Phase 0 (current): Hough circles find disk positions;
    │                       the user assigns antibiotic names in the UI.
    ▼
 3. ZONE SEGMENTATION ─  For each disk, crops a region of interest, applies
    │                     Otsu thresholding to separate the clear inhibition zone
    │                     from the bacterial lawn, and fits a circle to measure
    │                     the zone diameter in millimetres.
    ▼
 4. CLASSIFICATION ────  Looks up each antibiotic in the CLSI M100-Ed33 (2023)
    │                     breakpoint table and assigns S / I / R.
    ▼
 5. REPORT ────────────  Returns an annotated image, a JSON result, and a
                          downloadable Markdown report.
```

---

## Try the demo (no coding needed)

If you only want to try the interactive web interface:

```bash
# 1. Clone the repository
git clone https://github.com/EstebanHerna/bacterioscope.git
cd bacterioscope

# 2. Install (requires Python 3.10 or newer)
pip install -e ".[all,dev]"

# 3. Launch the Streamlit demo
streamlit run src/bacterioscope/app.py
```

A browser tab opens automatically at `http://localhost:8501`.

**Steps inside the demo:**

1. Upload a raw Kirby-Bauer plate photograph (JPEG, PNG, or TIFF).
2. The pipeline detects and measures all visible disks automatically.
3. For each disk, select the antibiotic name from the dropdown.
4. The S/I/R counters and the per-disk category badges update immediately.
5. Click **Download report** to save a Markdown file with the results.

> **Tip:** use `docs/plate_original.png` (included in this repository) as a
> test image if you do not have a plate photograph available.

---

## Full installation

### Requirements

- Python 3.10 or newer
- pip (comes with Python)
- Git

### Install core + all extras

```bash
git clone https://github.com/EstebanHerna/bacterioscope.git
cd bacterioscope
pip install -e ".[all,dev]"
```

The `[all]` extra installs Ultralytics YOLOv8, FastAPI, and Streamlit.
The `[dev]` extra adds testing and linting tools.

If you only need the core pipeline without the web interface or API:

```bash
pip install -e ".[dev]"
```

### Verify the installation

```bash
pytest tests/ -v          # runs 107 tests — all should pass
python -m bacterioscope version
```

---

## Usage

### Interactive Streamlit demo

```bash
streamlit run src/bacterioscope/app.py
# Opens http://localhost:8501
```

### Command-line interface

```bash
# Analyse a plate and print a colour-coded results table
python -m bacterioscope analyze docs/plate_original.png

# Save the annotated image to a file
python -m bacterioscope analyze plate.jpg --output annotated.jpg

# Override the organism group (only Enterobacteriaceae supported in Phase 0)
python -m bacterioscope analyze plate.jpg --organism Enterobacteriaceae

# Set a custom detection confidence threshold (YOLOv8 mode only)
python -m bacterioscope analyze plate.jpg --confidence 0.4
```

### REST API

```bash
# Start the API server
uvicorn bacterioscope.api.routes:app --reload

# Check the service is running
curl http://localhost:8000/health

# Analyse a plate image
curl -X POST http://localhost:8000/analyze \
     -F "image=@plate.jpg"
```

Interactive API documentation is available at `http://localhost:8000/docs`.

### Python API

```python
from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

config = PipelineConfig(plate_diameter_mm=90.0, organism_group="Enterobacteriaceae")
pipeline = BacterioScopePipeline(config)
result = pipeline.analyze("plate.jpg")

for item in result.classifications:
    print(f"{item.antibiotic:30s}  {item.zone_diameter_mm:5.1f} mm  {item.category}")
```

---

## Repository layout

```
bacterioscope/
├── src/
│   └── bacterioscope/              ← importable Python package
│       ├── __init__.py             ← package entry point (see docstring for overview)
│       ├── __main__.py             ← enables `python -m bacterioscope`
│       ├── pipeline.py             ← end-to-end orchestrator ← START HERE
│       ├── cli.py                  ← command-line interface (Typer + Rich)
│       ├── app.py                  ← Streamlit interactive demo
│       ├── detection/
│       │   ├── detector.py         ← DiskDetector: YOLOv8 or Hough fallback
│       │   └── train.py            ← YOLOv8 training script (Phase 1)
│       ├── segmentation/
│       │   └── watershed.py        ← ZoneSegmenter: Otsu + contour fitting
│       ├── classification/
│       │   └── clsi.py             ← CLSIClassifier + CLSI 2023 breakpoint tables
│       ├── api/
│       │   ├── routes.py           ← FastAPI endpoints
│       │   └── schemas.py          ← Pydantic request/response schemas
│       ├── utils/
│       │   ├── calibration.py      ← plate rim detection → px/mm ratio
│       │   ├── visualization.py    ← annotated image generation
│       │   └── image.py            ← image I/O helpers (Phase 1)
│       └── evaluation/
│           ├── metrics.py          ← CA, EA, VME, ME, mE calculation
│           └── report.py           ← CSV + Markdown evaluation report
├── tests/                          ← mirrors src/ structure
│   ├── test_clsi.py
│   ├── test_detector.py
│   ├── test_api.py
│   └── test_app.py
├── scripts/
│   ├── download_data.py            ← downloads Dryad/UZH dataset safely
│   └── generate_demo.py            ← generates docs/pipeline_demo.gif
├── notebooks/
│   └── pipeline_walkthrough.ipynb  ← step-by-step guided tour
├── docs/
│   ├── plate_original.png          ← synthetic test plate (use for demo)
│   └── pipeline_demo.gif           ← animated pipeline demonstration
├── data/                           ← gitignored: raw images, processed labels, weights
├── pyproject.toml                  ← all configuration: deps, ruff, mypy, pytest, bandit
├── Dockerfile                      ← non-root container for production deployment
├── Makefile                        ← shortcuts: make test, make lint, make demo
└── CLAUDE.md                       ← AI agent context file
```

**Where to start reading the code:**

1. `pipeline.py` — the orchestrator that calls everything else.
2. `classification/clsi.py` — the breakpoint tables and S/I/R logic.
3. `detection/detector.py` — Hough fallback and YOLOv8 wrapper.
4. `segmentation/watershed.py` — zone measurement algorithm.

---

## Clinical evaluation metrics

The `bacterioscope.evaluation` module computes ISO 20776-2 / FDA clinical agreement metrics. Run against a labelled ground-truth CSV:

```bash
python scripts/evaluate.py \
  --image-dir data/processed/images \
  --csv       data/processed/labels.csv \
  --output    results/
```

| Metric | Description | Acceptance threshold |
|--------|-------------|----------------------|
| **CA** | Categorical Agreement — predicted category matches reference | ≥ 90 % |
| **EA** | Essential Agreement — measured diameter within ±2 mm of reference | ≥ 90 % |
| **VME** | Very Major Error — predicted S when true category is R (dangerous miss) | ≤ 1.5 % |
| **ME** | Major Error — predicted R when true category is S | ≤ 3 % |
| **mE** | Minor Error — any discordance involving the Intermediate category | ≤ 10 % |
| **MAE** | Mean Absolute Error of zone diameters | — |
| **r** | Pearson correlation between measured and reference diameters | — |

EA definition adapted from ISO 20776-2: diameter within ±2 mm (EUCAST EDef 13.2) rather than the classical MIC ±1 two-fold dilution definition.

---

## Datasets

| Dataset | Description | How to download |
|---------|-------------|-----------------|
| **Dryad/UZH** (Giske et al., 2024) | 225 Gram-negative isolates, 862 phenotypic categories including ESBL, AmpC, and carbapenemase producers | `python scripts/download_data.py` |
| **Roboflow/KB-AST** | Community-annotated Kirby-Bauer images with bounding boxes for YOLOv8 training | Manual download from Roboflow |
| **AntibiogramJ reference set** | Benchmark images from Heras et al. (2017) | Included in the AntibiogramJ repository |

---

## Project phases

| Phase | Scope | Status |
|-------|-------|--------|
| **0 — Detection & Measurement** | Hough disk detection, Otsu zone segmentation, CLSI classification, Streamlit demo, REST API, CLI, evaluation module, 107 tests, CI | **Complete** |
| **1 — YOLOv8 Training** | Train on Dryad/UZH dataset, automated antibiotic label reading, validate zone measurements against ground truth | Planned |
| **2 — Clinical Validation** | Validation study with clinical isolates, pilot deployment in low-resource lab | Planned |

---

## Development

```bash
pip install -e ".[dev]"           # core + dev tools (no ML/API/UI)
pip install -e ".[all,dev]"       # everything

make test                          # pytest tests/ -v
make lint                          # ruff check src/ tests/
ruff check --fix src/ tests/       # auto-fix import order and style issues
mypy src/bacterioscope/            # static type checking
bandit -r src/ -c pyproject.toml   # security scan
```

### Code standards

- Python 3.10+ type hints on all function signatures.
- Google-style docstrings on all public and private functions.
- Functions under 40 lines of executable logic.
- `ruff`, `mypy`, `bandit`, and `pytest` must all pass before committing.

For a guided tour of the pipeline, open `notebooks/pipeline_walkthrough.ipynb`.

---

## Research context

This repository is the engineering backbone of an ongoing research collaboration between the Departments of Systems Engineering and Microbiology at Universidad de los Andes (Bogotá, Colombia), supervised by Prof. Astrid Blanco.

Domain expertise and CLSI protocol guidance provided by Paula Becerra Lara (Microbiology, Uniandes).

**Related publications (preprint):**

- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Prediction of Carbapenem Resistance in Klebsiella pneumoniae via Computer Vision Applied to Kirby-Bauer Antibiograms.* Universidad de los Andes.
- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Visual Detection of Bacterial Growth in Blood Cultures via Computer Vision.* Universidad de los Andes.

**Related projects by the same developer:**

- **NexusMind** — AWS AI League top 100/1000. Nine Lambda functions, Bedrock + Claude 3 Haiku, DynamoDB, EventBridge, React.
- **CaminAI** — 3rd place, Young AI Leaders Bogotá.
- **Altus** — B2B alternative credit scoring API. Cornell EMC2 Mark Mobius Pitch 2026.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Disk detection | Ultralytics YOLOv8 (PyTorch), OpenCV HoughCircles fallback |
| Zone segmentation | OpenCV 4.x, scikit-image (Otsu thresholding + contour fitting) |
| Classification | CLSI M100-Ed33 (2023) breakpoint tables |
| Evaluation | ISO 20776-2 / FDA clinical agreement metrics |
| REST API | FastAPI + python-multipart |
| Interactive demo | Streamlit |
| Infrastructure | Docker, GitHub Actions CI, pytest, ruff, mypy, bandit, gitleaks |

---

## License

MIT — see [LICENSE](LICENSE).

## Authors

- **Esteban A. Hernandez Sulvara** — Systems Engineering, Universidad de los Andes ([GitHub](https://github.com/EstebanHerna))
- **Paula A. Becerra Lara** — Microbiology, Universidad de los Andes
