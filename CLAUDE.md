# CLAUDE.md

## What this project is

BacterioScope es un sistema de visión computacional de código abierto que, a partir de una sola fotografía de una placa de antibiograma Kirby-Bauer tomada con cualquier cámara, entrega el reporte de sensibilidad/resistencia (S/I/R) completo sin intervención humana: detecta cada disco, lee automáticamente el antibiótico impreso, mide la zona de inhibición en mm y la clasifica según CLSI. Pensado para laboratorios de mediana y baja complejidad en América Latina sin acceso a VITEK/MicroScan.

Lema: "La tecnología al servicio de la salud pública."

Selected for the Biodiscovery Design Innovation Challenge (BDIC) 2026, Universidad de los Andes / Nodo de Innovación.

## Team

| Role | Member |
|---|---|
| Technical lead / ML | Esteban A. Hernandez Sulvara — Systems Engineering, Uniandes |
| Microbiology | Paula Becerra Lara — Microbiology, Uniandes |
| Microbiology | Farid — Uniandes |
| Interface & data | Santiago Gomez — Uniandes |
| Advisor | Prof. Aurelio — Uniandes |
| Advisor | Astrid Berena Herrera — Uniandes |

## Key design decisions (binding for all agents)

**Full automation of antibiotic label reading is the target.** The Phase 2 YOLOv8 model detects each disk and reads the printed antibiotic abbreviation from its surface. The manual selectbox in the Streamlit demo (Phase 0) is a temporary workaround, not the final UX.

**No temporal prediction. No halo time-series.** BacterioScope measures a single static photograph taken after incubation. There is no model that predicts resistance from halos measured over time. Any code, comment, docstring, or documentation that references "early prediction of carbapenem resistance", "time-series halo measurement", or "temporal zone evolution" is incorrect and must be removed.

**Calibration reference: the disk itself.** Phase 3 calibrates px/mm using the physical disk diameter (6 mm standard) rather than the plate rim. This is more robust because the disk is always sharp and well-contrasted in the image.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| F0 | End-to-end pipeline: Hough disk detection, Otsu+watershed zone segmentation, CLSI M100-Ed33 2023 classifier (15 antibiotics, Enterobacteriaceae), Streamlit demo, CLI, FastAPI, evaluation module (CA/EA/VME/ME/mE ISO 20776-2), 107 tests, CI green on Python 3.10/3.11/3.12 | **Complete** |
| F1 | Curate and annotate Dryad/UZH dataset (225 Gram-negative isolates, 862 phenotypic categories, clinical ground truth); produce train/val/test split and ground-truth CSV | Planned |
| F2 | Train YOLOv8 to detect each disk and read its printed antibiotic label; integrate into detector.py replacing HoughCircles; remove manual selectbox from demo | Planned |
| F3 | Recalibrate px/mm using 6 mm disk reference; run full clinical validation on held-out test split: EA >=90%, CA >=90%, VME <=1.5%, ME <=3%, mE <=10% | Planned |
| F4 | PyPI package, Docker image (GHCR), Streamlit Community Cloud deployment, MkDocs documentation site, peer-reviewed write-up | Planned |

See docs/ROADMAP.md for full phase specifications.

## Code standards (non-negotiable)

- No emojis anywhere (code, comments, docstrings, commit messages).
- No unnecessary comments. Self-documenting code.
- Type hints on all function signatures.
- Google-style docstrings.
- English for all code, docstrings, README, and docs.
- Imports: stdlib, then third-party, then local. One blank line between groups.
- No wildcard imports.
- Functions under 40 lines.
- Tests mirror src/ structure.
- Always run `ruff check --fix src/ tests/` before committing.
- Always run `ruff check src/ tests/` to verify zero violations.
- Always run `pytest tests/ -v` to verify tests pass.
- Commit messages in Spanish, no AI co-authorship lines.

## Tech stack

- Python 3.10+
- PyTorch + Ultralytics YOLOv8 (Phase 2 onwards; optional in Phase 0)
- OpenCV 4.x (opencv-python-headless) + scikit-image
- scikit-learn
- FastAPI + Pydantic v2
- Streamlit
- Docker, GitHub Actions CI, pytest, ruff, mypy strict, bandit, gitleaks

## Project layout explained

This is a standard Python src-layout project:

```
bacterioscope/
    src/
        bacterioscope/
            __init__.py
            __main__.py         <- enables `python -m bacterioscope`
            pipeline.py         <- end-to-end orchestrator
            cli.py              <- CLI entry point (Typer)
            app.py              <- Streamlit demo
            _app_logic.py       <- pure helpers with no Streamlit import (testable without UI)
            detection/
                detector.py     <- DiskDetector: YOLOv8 when weights exist, HoughCircles fallback
                train.py        <- YOLOv8 training script (Phase 2)
            segmentation/
                watershed.py    <- ZoneSegmenter: Otsu + watershed
            classification/
                clsi.py         <- CLSIClassifier: CLSI M100-Ed33 2023 breakpoints
            evaluation/
                metrics.py      <- CA, EA, VME, ME, mE per ISO 20776-2
                report.py       <- Markdown + HTML report generation
            api/
                routes.py       <- FastAPI endpoints
                schemas.py      <- Pydantic v2 request/response schemas
            utils/
                calibration.py  <- pixel-to-mm (Phase 3: disk-based; Phase 0: plate-rim)
                visualization.py <- annotated output images
                image.py        <- image I/O helpers (Phase 1)
    tests/                      <- 107 tests, mirrors src/ structure
    scripts/
        download_data.py        <- Dryad/UZH downloader with zip-slip protection
        generate_demo.py        <- generates synthetic demo images in docs/
    data/
        raw/                    <- gitignored
        processed/              <- gitignored
        models/                 <- gitignored
    docs/
        ROADMAP.md              <- full phase specifications
        plate_original.png      <- synthetic test plate (generated by generate_demo.py)
        pipeline_demo.gif       <- animated pipeline walkthrough
    pyproject.toml
    CLAUDE.md                   <- this file
    SECURITY.md
    Dockerfile
    Makefile
```

Why `_app_logic.py` exists: the CI job installs without Streamlit (`[dev]` extra only). Tests that import from `app.py` would fail at import time because `app.py` has `import streamlit as st` at the module level. Pure logic (`reclassify_with_assignment`, `_UNASSIGNED`, `_ANTIBIOTIC_OPTIONS`) lives in `_app_logic.py`, which has no Streamlit dependency, so `test_app.py` can import from it without Streamlit installed.

## How the pipeline works (Phase 0)

```
Image file (jpg/png)
    |
    v
pipeline.py: BacterioScopePipeline.analyze()
    |
    +---> calibration.py: detect plate circle via Hough -> compute px_per_mm
    |
    +---> detector.py: DiskDetector.detect()
    |         If YOLOv8 weights exist -> YOLO inference (Phase 2+)
    |         Else -> HoughCircles fallback (Phase 0)
    |         Returns: list[DiskResult] with center, radius, label, confidence
    |
    +---> watershed.py: ZoneSegmenter.segment() (one call per disk)
    |         Extract ROI -> grayscale -> Otsu threshold -> morphological cleanup
    |         -> find contours -> measure diameter
    |         Returns: ZoneResult with diameter_px, diameter_mm, circularity
    |
    +---> clsi.py: CLSIClassifier.classify() (one call per disk)
    |         Look up antibiotic in CLSI 2023 breakpoint table
    |         Compare zone_diameter_mm against S/I/R thresholds
    |         Returns: SusceptibilityResult with category
    |
    +---> visualization.py: draw_results()
    |         Annotate image with colored circles and labels
    |
    v
AnalysisResult (dataclass: image_path, plate_diameter_px, px_per_mm,
                disks, zones, classifications, annotated_image)
```

The three lists `disks`, `zones`, `classifications` are parallel: index i refers to the same physical disk across all three.

## Dataset

- Dryad/UZH (Giske et al., 2024): 225 Gram-negative isolates, 862 phenotypic categories. Download: `python scripts/download_data.py`
- Roboflow/KB-AST: community-annotated Kirby-Bauer images with bounding boxes

## Commands

```bash
pip install -e ".[dev]"                              # core + dev tools
pip install -e ".[all,dev]"                          # everything (ML, API, UI)
make test                                            # pytest tests/ -v
make lint                                            # ruff check src/ tests/
ruff check --fix src/ tests/                         # auto-fix
mypy src/bacterioscope/                              # type check (strict)
bandit -r src/bacterioscope/ -c pyproject.toml       # security scan
python -m bacterioscope analyze <image>              # run pipeline
streamlit run src/bacterioscope/app.py               # launch demo
```

## Skills to register in Claude Code sessions

```bash
uv tool install graphifyy && graphify claude install
npx -y skills add emilkowalski/skill --skill emil-design-eng --agent claude-code
```

## Related projects by the same developer

- NexusMind: AWS AI League top 100/1000. 9 Lambda functions, Bedrock + Claude 3 Haiku, DynamoDB, EventBridge, React.
- CaminAI: 3rd place Young AI Leaders Bogota.
- Altus: B2B alt credit scoring API. Cornell EMC2 Mark Mobius Pitch 2026.
- UniMarket: messaging layer for campus marketplace (ISIS-3510).
- CODEFEST AD ASTRA 2026: multi-agent system for Colombian Air Force.
