# Data Sources

This document lists all image datasets used or referenced in BacterioScope
validation and development.

---

## Summary table

| Source | Images | Standard | License | Status |
|---|---|---|---|---|
| Dryad/UZH SIRscan | ~862 phenotypic categories, 225 isolates | EUCAST 2023 | CC0 1.0 | Available via download script |
| ASTimp (Pascucci 2021) | Test images (variable) | None (visual only) | Apache 2.0 | Available via import script |
| ASTIMP Roboflow | ~108+ annotated plates | None | CC BY 4.0 | Requires API key |

---

## Dryad/UZH SIRscan Dataset

**Citation:**
Egli A, Imkamp F, Amlang G, Brunner S, Albrich W, et al. (2023).
Automated reading of disk diffusion antibiograms.
Dryad Digital Repository. doi:10.5061/dryad.5dv41nsfj

**Access:** https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj

**License:** Creative Commons Zero v1.0 Universal (CC0) — no restrictions.

**Content:** 225 Gram-negative clinical isolates, 862 phenotypic categories.
Reference measurements were produced by the SIRscan automated reader (i2a)
using EUCAST 2023 breakpoints.

**Scope in BacterioScope:** Measurement accuracy validation only (zone diameter
in mm). S/I/R classification is not validated against this dataset because
BacterioScope uses CLSI 2023 breakpoints, which differ from EUCAST 2023 for
several antibiotic-organism combinations. See `docs/LIMITACIONES.md`.

**Download:**
```bash
python scripts/download_data.py
python scripts/prepare_dataset.py --data-dir data/raw/dryad_uzh
```

---

## ASTimp — Pascucci et al. 2021

**Citation:**
Pascucci M, Royer G, Adamek J, Al Asmar M, Aristizabal D, et al. (2021).
AI-based mobile application to fight antibiotic resistance.
Nature Communications 12:1173. doi:10.1038/s41467-021-21187-3

**Repository:** https://github.com/mpascucci/AST-image-processing

**License:** Apache License 2.0. Attribution and citation required.
Full terms: https://www.apache.org/licenses/LICENSE-2.0

**Content:** Test plate photographs bundled with the ASTimp C++/Python library.
No numeric reference measurements are provided. These images are used for
visual validation (verifying that segmentation contours look correct) and
detector benchmarking, not for metric computation.

**Scope in BacterioScope:** Visual validation and detector development.

**Import:**
```bash
python scripts/import_astimp.py
# Or without confirmation prompt (CI):
python scripts/import_astimp.py --yes
```

**Disclaimer:** By importing these images you accept the Apache 2.0 License
and commit to citing the Nature Communications 2021 paper in any publication.

---

## ASTIMP — Roboflow Universe

**Citation:**
AST-IMP dataset. Roboflow Universe. Retrieved 2024.
https://universe.roboflow.com/ast-imp/astimp

**License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
Attribution required.

**Content:** Annotated disk diffusion plate photographs with bounding boxes
around individual disks and a trained object detection model. Useful for
Phase 2 YOLOv8 training.

**Scope in BacterioScope:** Training data and visual validation for disk
detection (Phase 2).

**Download (manual — requires free Roboflow account):**

1. Create a free account at https://roboflow.com
2. Navigate to https://universe.roboflow.com/ast-imp/astimp
3. Click "Download" and choose COCO JSON or YOLOv8 format
4. Extract to `data/raw/roboflow_astimp/`

Or via API (replace `YOUR_KEY`):
```bash
pip install roboflow
python - <<'EOF'
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_KEY")
project = rf.workspace("ast-imp").project("astimp")
project.version(1).download("yolov8", location="data/raw/roboflow_astimp")
EOF
```

---

## Adding a new source

1. Create a YAML config in `data/sources/<name>.yaml` following the format of
   the existing files.
2. Place images in `data/raw/<name>/`.
3. Run `python scripts/prepare_dataset.py --sources-dir data/sources` to
   regenerate the combined `ground_truth.csv`.
4. Update this document with the new source.
