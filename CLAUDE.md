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
| F0 | End-to-end pipeline: Hough disk detection, Otsu+watershed zone segmentation, CLSI M100-Ed33 2023 classifier (15 antibiotics, Enterobacteriaceae), Streamlit demo, CLI, FastAPI, evaluation module (CA/EA/VME/ME/mE ISO 20776-2), design system (Clinical Slate tokens, dark/light CSS), traceability fields (analysis_id UUID, image SHA-256, commit hash, CLSI edition, stage timings), 9-section scientific HTML plate reports, Bland-Altman measurement validation, panel configuration, batch processing, 247 tests (93.8%+ coverage), CI green on Python 3.10/3.11/3.12 | **Complete** |
| F1 | Curate Dryad/UZH dataset ground truth. Real measurements extracted from 225 per-isolate DOCX tables (not the summary XLSX, which only has phenotype flags) via a custom parser in `prepare_dataset.py` -> 3598 records in `data/processed/ground_truth.csv`. 20 images identity-annotated (`scripts/annotate_pairs.py`, `data/processed/pair_annotations/`) with human-verified disk-to-antibiotic pairing, reaching the 20-30 stable-estimate range: the first 3 were read directly off the printed disk labels; the panel turned out to use a fixed position-to-antibiotic template with two known variants (FF/F100 vs AK/TOB at two grid cells), so the remaining 17 were identity-annotated by matching disk position against the verified template, with the variant confirmed per image by direct visual reading of the swing-position labels (not assumed from series naming, which does not predict it). Train/val/test split for YOLO annotation still pending. | **In Progress** |
| F2 | 29-class YOLOv8n (Roboflow KB-AST, 102 train / 10 val / 3 test images) trained 50 epochs, mAP50=0.096 -- documented as an experiment, not usable at any defensible confidence threshold (`confidence_threshold` restored to 0.25; do not lower it to force detections). A single-class "disk" detector (`scripts/convert_single_class_dataset.py` collapses the 29 antibiotic classes to one "disk" label; identity resolves via panel position, unchanged) finished training at `data/models/single_class/yolov8_disks.pt` (100 epochs, imgsz=1280; peak mAP50=0.981 at epoch 23, the deployed `best.pt` checkpoint, not the overfit epoch-100 `last.pt`) and scores mAP50=0.995, precision=0.992, recall=1.0 on its own held-out Roboflow test split. `detector.py::_detect_yolo()` had a real bug for this model: every detection shared the literal class name `'disk'`, colliding in the CLSI lookup and UI table; fixed by numbering sequentially (`disk_0`, `disk_1`, ...) when the loaded model has exactly one class, matching the Hough convention. **Correction to an earlier finding in this same phase**: a first head-to-head against Hough on the 80 real UZH photos (expected disk count from `ground_truth.csv`, independent of both detectors) used `conf=0.5` and concluded the single-class model underperformed Hough (60.0% exact-count match vs Hough's 73.8%). That comparison was not meaningful -- `conf=0.5` was never tuned for this model, only carried over as a plausible-looking default. A confidence sweep (0.15 to 0.65) found a sharp optimum around `conf=0.27-0.30`: **76-77.5% exact-count match, matching or slightly beating Hough**, with the curve collapsing to near-zero outside a fairly narrow band (1.2% at 0.15, 0% at 0.65) -- this model is usable but sensitive to threshold choice, unlike Hough which has no equivalent knob. `PipelineConfig.detector_weights` still stays pointed at the 29-class path by default (Hough remains the pipeline's real default) because switching the default detector is a deployment decision beyond pure count-accuracy (ultralytics/torch dependency weight, model-load latency, no threshold-sensitivity risk with Hough) -- not because the single-class model was shown inferior; it was not. The single-class weights are usable today by passing `detector_weights=Path("data/models/single_class/yolov8_disks.pt")` with `confidence_threshold` around `0.28`. `detector.py`'s hybrid fallback (YOLO first, Hough if YOLO returns nothing) had a separate, already-fixed bug: a single ~0.05-confidence 29-class false positive could pre-empt 16 reliable Hough detections; fixed by the confidence floor above (disk count matching real UZH photos: 24/80 -> 70/80 images). | **In Progress** |
| F3 | Detection-side fixes: Hough disk-radius search derived from px/mm calibration instead of a fixed pixel range (`detector.py::_hough_search_window`), reducing a systematic +28% disk-size overestimate and eliminating false-circle storms on large real photos; canonical image resize (`resize_canonical`, <=1400px, downscale-only) keeps one geometry parameter set valid across camera resolutions; Hough's accumulator threshold now sweeps to the longest stable count instead of one fixed value (`_hough_stable_circles`), since no single value worked for both real photos and synthetic plates. Segmentation-side fix: `ZoneSegmenter.segment_all()` now splits confluent (touching/overlapping) zones with a Voronoi partition instead of measuring one shared Otsu blob per neighbourhood -- verified correct on a controlled case (two disks, deliberately different true sizes, recovered exactly as 40mm and 20mm; `tests/test_watershed.py::TestSegmentAllVoronoiSplit`). Real-world effect on the densest UZH panels was modest because several adjacent disk pairs there have literally zero recoverable boundary signal in the photograph (checked directly: flat pixel intensity across the whole gap) -- not a segmentation bug, a photograph limitation of the 16-disk-dense research protocol. Disk-based calibration (`use_disk_calibration`) investigated directly: it was never measuring the disk independently at all -- `pipeline.analyze()` calls `detector.detect(image, px_per_mm=px_per_mm_rim)` *before* disk calibration runs, and Hough's disk-radius search window is derived from that same plate-rim estimate (`detector.py::_hough_search_window`), so the "disk-calibrated" px/mm was plate-rim calibration scaled by whatever Hough voted for inside a window centred on it -- confirmed directly: across 20 real photos the ratio was a suspiciously tight ~0.80x, not an independent measurement. Fixed with `calibration.py::refine_disk_radius_px()`: a local, calibration-independent Otsu threshold re-measures each disk's true edge directly in a small crop around its detected centre. This closed most of the gap (identity-matched EA on the 20-image set: 14.9% -> 28.8%, MAE 8.88mm -> 7.42mm) but disk calibration still trails plate-rim calibration (32.9% EA, 6.28mm MAE) even once measured correctly -- not a remaining bug, a measurement-theory limit: the same few pixels of edge-detection noise are a much larger *relative* error against a 6mm disk (~50-60px) than against a 90mm plate (~550-600px), so `use_disk_calibration` stays `False` by default. Full clinical validation targets (EA/CA >=90%, VME <=1.5%, ME <=3%, mE <=10%) not met. A ROI-crop geometric safety fix (`ZoneSegmenter._search_radius()`: cap by nearest-neighbour distance and by an absolute plausible-zone-size ceiling) was validated against the controlled 40mm/20mm case but did not, by itself, fix the real-photo numbers -- growing the crop alone left Otsu still filling nearly the whole crop regardless of size; margin_factor stayed at 4.0. Root cause found by direct pixel measurement: the paper disk itself (bright, ~150-200) is almost always a far stronger bimodal signal than the actual zone-vs-lawn contrast (sometimes as little as 15 grey levels on real photos), so Otsu, run over the whole crop, reliably locks onto disk-vs-everything instead of zone-vs-lawn -- confirmed directly (a between-class-variance quality score was *highest*, 0.91-0.92, on exactly the real photos whose masks filled 100% of their crop, because that score was measuring the disk/background split, not zone/lawn). Fixed by excluding the disk's own area from Otsu's histogram before picking the threshold (`ZoneSegmenter._otsu_excluding_disk()`). This is a real, measured improvement, not a reparameterization: identity-matched real-photo result (20 images, 316 pairs, the defensible number) moved from EA=24.1%/MAE=7.44mm/r=0.089 to **EA=32.9%, MAE=6.28mm, r=0.193** (see docs/VALIDATION_REPORT.md, docs/LIMITACIONES.md); rank-order moved from EA=27.3%/MAE=5.27mm/r=0.608 to EA=38.1%/MAE=3.93mm/r=0.783. Still well below the ISO 20776-2/EUCAST target of 90% EA -- a real improvement, not a fix. **Major caveat on all EA/MAE numbers above**: found by direct visual audit that the UZH validation dataset uses square plates cropped to nearly fill the frame, not round plates with visible background like plate-rim calibration is designed for -- detected plate-rim diameter sits at a suspiciously constant 91-99% of the detector's own search ceiling while its centre swings +-330px with no stable pattern, meaning that detector is not reliably finding a real boundary on this dataset. Deliberately not fixed (a bounding-box fallback would overfit to this dataset's square/full-frame convention at the expense of the tool's real round-plate target use case); see docs/LIMITACIONES.md section 9. | **In Progress** |
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
            watershed.py             <- ZoneSegmenter: Otsu + contour fitting, Voronoi-split
                                        for confluent zones on multi-disk plates
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
    +---> watershed.py: ZoneSegmenter.segment_all() (all disks jointly)
    |         Per disk: extract ROI -> grayscale -> Otsu threshold -> morphological
    |         cleanup -> restrict to this disk's Voronoi cell (nearest-neighbour
    |         split against every other disk, so a confluent neighbour's zone
    |         isn't measured as this disk's own) -> find contours -> measure diameter
    |         Returns: list[ZoneResult] with diameter_px, diameter_mm, circularity
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
