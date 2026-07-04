# BacterioScope

**Automated antimicrobial resistance detection from Kirby-Bauer disk diffusion images using deep learning and classical computer vision.**

BacterioScope takes a photograph of a Kirby-Bauer antibiogram plate and returns: detected antibiotic disks, segmented inhibition zones, diameter measurements in millimeters, and S/I/R classification against CLSI 2023 breakpoints. Designed for clinical microbiology labs in low- and middle-income settings where automated AST systems (VITEK, Phoenix) are unavailable.

## Why this matters

Antimicrobial resistance kills 1.27 million people per year (Murray et al., 2022). In Colombia, carbapenem-resistant *Klebsiella pneumoniae* is among the most frequent pathogens in healthcare-associated infection outbreaks (INS, 2019-2025). The standard Kirby-Bauer method requires manual zone measurement with a ruler — a slow, error-prone process. BacterioScope automates that measurement pipeline and adds a trained classification model, bringing diagnostic-grade AST analysis to any lab with a smartphone camera.

## Architecture

```
Input (plate image)
    |
    v
[Disk Detection] ---- YOLOv8 object detection
    |
    v
[Zone Segmentation] - Watershed + adaptive thresholding (OpenCV)
    |
    v
[Measurement] ------- Pixel-to-mm calibration via plate diameter
    |
    v
[Classification] ---- CLSI 2023 breakpoint lookup (S / I / R)
    |
    v
[Report] ------------ Structured JSON + annotated image + Streamlit UI
```

## Quick start

```bash
git clone https://github.com/EstebanHerna/bacterioscope.git
cd bacterioscope
pip install -e ".[dev]"

# Download public datasets
python scripts/download_data.py

# Run the pipeline on a sample image
python -m bacterioscope.cli analyze data/raw/sample_plate.jpg

# Launch the interactive demo
streamlit run src/bacterioscope/app.py
```

## Datasets

BacterioScope trains and evaluates on publicly available antibiogram image datasets:

- **Dryad/UZH** (Giske et al., 2024): 225 Gram-negative isolates, 862 phenotypic categories including ESBL, AmpC, and carbapenemase producers. High-resolution SIRscan images with EUCAST annotations.
- **Roboflow/KB-AST**: Community-annotated Kirby-Bauer test images with bounding boxes for disks and zones.
- **AntibiogramJ reference set**: Benchmark images from the AntibiogramJ open-source tool (Heras et al., 2017).

See `scripts/download_data.py` for automated download and preprocessing.

## Project phases

| Phase | Scope | Data source | Status |
|-------|-------|-------------|--------|
| **0 - Detection & Measurement** | Disk detection, zone segmentation, diameter measurement, S/I/R classification | Public datasets | In progress |
| **1 - Temporal Prediction** | Time-series analysis of inhibition zone growth (6-10h prediction of 24h result) | Lab experiments (ATCC strains) | Planned |
| **2 - Clinical Validation** | Validation with clinical isolates, pilot deployment | Fundacion Santa Fe de Bogota | Planned |

## Research context

This repository is the engineering backbone of an ongoing research collaboration between Systems Engineering and Microbiology at Universidad de los Andes (Bogota, Colombia), supervised by Prof. Astrid Blanco. The temporal prediction hypothesis (Phase 1) — that morphological features of the inhibition zone at 6-10 hours predict the 24-hour CLSI result — is the subject of a forthcoming thesis and publication.

**Related publications:**
- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Prediction of Carbapenem Resistance in Klebsiella pneumoniae via Computer Vision Applied to Kirby-Bauer Antibiograms.* Universidad de los Andes. [Preprint]
- Hernandez-Sulvara, E. A. & Becerra-Lara, P. A. (2026). *Early Visual Detection of Bacterial Growth in Blood Cultures via Computer Vision.* Universidad de los Andes. [Preprint]

## Tech stack

- **Detection**: Ultralytics YOLOv8 (PyTorch)
- **Segmentation**: OpenCV 4.x, scikit-image
- **Classification**: scikit-learn (Random Forest, SVM), CLSI breakpoint tables
- **API**: FastAPI + Streamlit demo
- **Infrastructure**: Docker, GitHub Actions CI, pytest

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Type check
mypy src/bacterioscope/
```

## License

MIT

## Authors

- **Esteban A. Hernandez Sulvara** — Systems Engineering, Universidad de los Andes ([GitHub](https://github.com/EstebanHerna))
- **Paula A. Becerra Lara** — Microbiology, Universidad de los Andes
