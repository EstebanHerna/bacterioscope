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
| F0 | End-to-end pipeline: Hough disk detection, Otsu+watershed zone segmentation, CLSI M100-Ed33 2023 classifier (15 antibiotics, Enterobacteriaceae), Streamlit demo, CLI, FastAPI, evaluation module (CA/EA/VME/ME/mE ISO 20776-2), design system (Clinical Slate tokens, dark/light CSS), traceability fields (analysis_id UUID, image SHA-256, commit hash, CLSI edition, stage timings), 9-section scientific HTML plate reports, Bland-Altman measurement validation, panel configuration, batch processing, 241 tests (93.8%+ coverage), CI green on Python 3.10/3.11/3.12 | **Complete** |
| F1 | Curate Dryad/UZH dataset ground truth. Real measurements extracted from 225 per-isolate DOCX tables (not the summary XLSX, which only has phenotype flags) via a custom parser in `prepare_dataset.py` -> 3598 records in `data/processed/ground_truth.csv`. 3 images identity-annotated (`scripts/annotate_pairs.py`, `data/processed/pair_annotations/`) with human-verified disk-to-antibiotic pairing, read directly off the printed disk labels; growing this to 20-30 images is the next step. Train/val/test split for YOLO annotation still pending. | **In Progress** |
| F2 | 29-class YOLOv8n (Roboflow KB-AST, 102 train / 10 val / 3 test images) trained 50 epochs, mAP50=0.096 -- documented as an experiment, not usable at any defensible confidence threshold (`confidence_threshold` restored to 0.25; do not lower it to force detections). A single-class "disk" detector (`scripts/convert_single_class_dataset.py` collapses the 29 antibiotic classes to one "disk" label; identity resolves via panel position, unchanged) reaches mAP50 ~0.9 within ~20 epochs on the same 102 images -- training in progress at imgsz=1280, `data/models/single_class/`. `detector.py`'s hybrid fallback (YOLO first, Hough if YOLO returns nothing) had a real bug: a single ~0.05-confidence 29-class false positive could pre-empt 16 reliable Hough detections; fixed by the confidence floor above (disk count matching real UZH photos: 24/80 -> 70/80 images). | **In Progress** |
| F3 | Two real fixes landed: (1) Hough disk-radius search is now derived from the already-known px/mm calibration instead of a fixed pixel range tuned for 540px synthetic images (`detector.py::_hough_search_window`), reducing a systematic +28% disk-size overestimate and eliminating false-circle storms (100-217 spurious detections) on large real photos; (2) canonical image resize (`resize_canonical`, longer side <=1400px, downscale-only) keeps one geometry parameter set valid across camera resolutions. Disk-based calibration (`use_disk_calibration`) is implemented but still underperforms plate-rim calibration -- root cause under investigation, see below. Full clinical validation targets (EA/CA >=90%, VME <=1.5%, ME <=3%, mE <=10%) not met. Identity-matched real-photo result (3 images, 48 pairs, the defensible number): EA=22.9%, MAE=7.18mm, r=-0.354. Leading suspected cause, confirmed this round: Otsu+watershed zone segmentation does not separate individual zones on real plates with 16 closely-packed, confluent disks -- measured diameters cluster within ~1.5mm of each other regardless of antibiotic (see docs/VALIDATION_REPORT.md, docs/LIMITACIONES.md). Not yet fixed. | **In Progress** |
| F4 | PyPI package, Docker image (GHCR), Streamlit Community Cloud deployment, MkDocs documentation site, peer-reviewed write-up. Colab/Drive notebook already available (`colab/BacterioScope_Colab.ipynb`) as an interim shareable deliverable. Streamlit demo now carries a permanent validation-status banner and rejects re-uploaded pipeline outputs (watermark check in `pipeline.analyze()`). | Planned |

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

This is a standard Python src-layout project. Every top-level folder has exactly one job —
if you're unsure where something goes, match it to the purpose below rather than adding a
new folder.

```
bacterioscope/
    src/bacterioscope/           <- all application code
        __init__.py
        __main__.py               <- enables `python -m bacterioscope`
        pipeline.py                <- end-to-end orchestrator (BacterioScopePipeline)
        cli.py                     <- CLI entry point (Typer)
        app.py                     <- Streamlit demo
        _app_logic.py              <- pure helpers with no Streamlit import (testable without UI)
        design/
            tokens.py               <- Clinical Slate palette/typography tokens (single source of color)
        detection/
            detector.py             <- DiskDetector: YOLOv8 if weights exist, else HoughCircles; falls
                                        back to Hough mid-call too if YOLO finds zero disks
            label_map.py            <- ROBOFLOW_TO_CLSI: disk abbreviation -> CLSI antibiotic key
            train.py                <- YOLOv8 training script (Phase 2)
        segmentation/
            watershed.py             <- ZoneSegmenter: Otsu + contour fitting
        classification/
            clsi.py                  <- CLSIClassifier: CLSI M100-Ed33 2023 breakpoints
        evaluation/
            metrics.py                <- CA, EA, VME, ME, mE per ISO 20776-2
            report.py                 <- Markdown evaluation report generation
            plate_report.py           <- self-contained per-plate HTML report (base64 image)
        panels/
            manager.py                 <- PanelManager: load YAML, assign antibiotics by angular position
        api/
            routes.py                   <- FastAPI endpoints
            schemas.py                   <- Pydantic v2 request/response schemas
        utils/
            calibration.py                <- px/mm: plate-rim (Phase 0) or disk-diameter (Phase 3)
            visualization.py               <- annotated output images
            image.py                        <- image I/O helpers

    tests/                        <- mirrors src/ structure, 236 tests

    scripts/                      <- one-off / operational scripts, not imported by src/
        download_data.py           <- Dryad/UZH downloader with zip-slip protection
        prepare_dataset.py         <- parses UZH DOCX/CSV/XLSX measurement tables -> ground_truth.csv
        validate_measurement.py    <- runs the pipeline on real plates, computes EA/MAE/Pearson r,
                                       writes docs/VALIDATION_REPORT.md and data/processed/validation_figures/
        evaluate.py                 <- batch S/I/R evaluation against a labelled CSV
        batch_analyze.py            <- folder batch processing (results.csv + errors.log)
        generate_demo.py            <- generates docs/plate_original.png and friends
        generate_test_plates.py     <- generates examples/synthetic/ scenarios

    panels/                        <- YAML panel configs (antibiotics by clockwise position)
        enterobacteria_clsi_12.yaml
        enterobacteria_clsi_6.yaml

    examples/                     <- sample plate photos to feed INTO the tool (inputs, not outputs)
        README.md                   <- explains synthetic/ vs real/ vs reference_annotated/
        synthetic/                   <- 8 generated plates, committed to git (self-owned)
            reference_annotated/      <- same plates pre-annotated for comparison; do not upload these
        real/                         <- real clinical photos for manual testing

    notebooks/
        pipeline_walkthrough.ipynb    <- exploratory Jupyter tour of the pipeline stages

    colab/                        <- Google Colab / Drive deliverable (separate from docs/ on purpose)
        BacterioScope_Colab.ipynb     <- self-contained notebook, auto-detects Drive folder nesting
        BacterioScope_Drive_Package.zip <- gitignored bundle (notebook + examples + weights)

    data/                         <- all gitignored except the two small validation summary plots
        raw/                        <- downloaded datasets (Dryad/UZH, Roboflow/KB-AST, astimp)
        processed/                   <- generated: ground_truth.csv, roboflow_dataset.yaml,
                                        validation_figures/ (annotated real-photo outputs + bland_altman.png
                                        + scatter_measured_vs_reference.png, the latter two ARE committed)
        models/                      <- trained weights (yolov8_disks.pt), gitignored

    docs/                         <- documentation ONLY — no test images, no deliverable bundles
        ROADMAP.md                   <- full phase specifications
        VALIDATION_REPORT.md         <- generated by validate_measurement.py
        METODOLOGIA_Y_HERRAMIENTAS.md
        RESUMEN_EVALUADORES.md
        FUENTES_DATOS.md
        LIMITACIONES.md
        SECURITY_AUDIT.md
        STATE_OF_THE_ART.md
        plate_original.png / plate_detected.png / plate_zones.png / plate_classified.png
                                       <- small illustration images referenced by app.py / README
        pipeline_demo.gif             <- animated pipeline walkthrough

    pyproject.toml
    CLAUDE.md                    <- this file
    SECURITY.md
    Dockerfile
    Makefile
```

**Rule of thumb for where new files go**: application logic -> `src/`; anything that
demonstrates or explains the system for a human reader -> `docs/`; images or files meant
to be *uploaded into* the tool -> `examples/`; anything a script generates and could
regenerate again -> `data/processed/` (gitignored unless it's a small committed summary
plot). Do not create a new top-level folder without a reason that doesn't fit one of these.

Why `_app_logic.py` exists: the CI job installs without Streamlit (`[dev]` extra only). Tests that import from `app.py` would fail at import time because `app.py` has `import streamlit as st` at the module level. Pure logic (`reclassify_with_assignment`, `_UNASSIGNED`, `_ANTIBIOTIC_OPTIONS`) lives in `_app_logic.py`, which has no Streamlit dependency, so `test_app.py` can import from it without Streamlit installed.

## How the pipeline works (current)

```
Image file (jpg/png)
    |
    v
pipeline.py: BacterioScopePipeline.analyze()
    |
    +---> calibration.py: detect plate circle via Hough -> compute px_per_mm
    |         (or calibrate_from_disk_radius_px() if use_disk_calibration=True, Phase 3 --
    |          currently performs worse than plate-rim until F2 detection is more confident,
    |          see docs/VALIDATION_REPORT.md)
    |
    +---> detector.py: DiskDetector.detect()
    |         If YOLOv8 weights exist -> YOLO inference, labels mapped via label_map.py
    |         If YOLO finds zero disks (or no weights) -> HoughCircles fallback automatically
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

- Dryad/UZH (Giske et al., 2024): 225 Gram-negative isolates. Download: `python scripts/download_data.py`.
  Ground truth (3598 real measurements) lives in 225 per-isolate `.docx` tables under
  `data/raw/dryad_uzh/Tables/`, parsed by `scripts/prepare_dataset.py` into `data/processed/ground_truth.csv`.
- Roboflow/KB-AST: community-annotated Kirby-Bauer images with bounding boxes, used to train YOLOv8
  (`data/processed/roboflow_dataset.yaml`, 102 train / 10 val / 3 test images, 29 disk classes)

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
