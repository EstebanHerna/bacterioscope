# Data Sources

This document lists all image datasets used or referenced in BacterioScope
validation and development.

---

## Summary table

| Source | Images | Standard | License | Status |
|---|---|---|---|---|
| Dryad/UZH SIRscan | 225 isolates, measurements and phenotype summaries | EUCAST (edition discrepancy unresolved) | CC0 1.0 | Measurement docs present; phenotype workbook role unverified |
| ASTimp (Pascucci 2021) | Test images (variable) | None (visual only) | Apache 2.0 | Available via import script |
| ASTIMP Roboflow | ~108+ annotated plates | None | CC BY 4.0 | Requires API key |

---

## Dryad/UZH SIRscan Dataset

**Citation:**
Giske CG, Bressan M, Fiechter F, Hinic V, Mancini S, Nolte O, Egli A (2024).
Image dataset of disk diffusion assay scanned with the SIRscan system.
Dryad Digital Repository. doi:10.5061/dryad.5dv41nsfj

**Access:** https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj

**License:** Creative Commons Zero v1.0 Universal (CC0) — no restrictions.

**Content:** 225 Gram-negative isolates and 862 valid phenotypic categories in
the associated study. The Dryad record says `Tables.zip` contains
`Tables/measurements.csv`, but the archive supplied in the project has 450
DOCX files and one actual XLSX workbook, with no CSV. The workbook is named
`Overview GPT JCM.xlsx`; its yes/no phenotype counts differ from the paper's
routine-diagnostic reference counts. Its role may be model output but remains
unconfirmed. The extractor retains its values as unverified
`source_reported_codes`, not reference labels. `Combination` remains
unspecified; this project does not expand it or infer missing mechanisms.

**Standard provenance:** the dataset page describes EUCAST methods. Its README
reports EUCAST 2022, while older repository notes/config report EUCAST 2023.
Keep this discrepancy visible until the downloaded archive README and primary
paper are reconciled. Dataset labels retain EUCAST provenance.

**Scope in BacterioScope:** The per-isolate DOCX tables can support
identity-matched zone-measurement comparisons after source parsing and image
joins. The workbook phenotype flags are not an evaluation target until Dryad
or the authors confirm their semantics. S/I/R classification is not validated
against this dataset because BacterioScope uses CLSI M100-Ed33 (2023), whereas
the data are EUCAST-derived. See `docs/LIMITACIONES.md` and
`docs/PERSON_2_RULE_SPEC.md`.

**Download:**
```bash
python scripts/download_data.py
python scripts/prepare_dataset.py --data-dir data/raw/dryad_uzh
python scripts/extract_uzh_phenotypes.py --input data/raw/dryad_uzh/Tables.zip
```

Dryad currently requires its accepted download flow. `scripts/prepare_dataset.py`
parses the per-isolate DOCX measurement tables. The Persona 2 extractor reads a
documented `measurements.csv` if present; for the current workbook fallback it
records indicators but leaves `reference_label_codes` empty pending provenance
clarification. It writes `data/processed/uzh_phenotype_labels.csv`; this
generated CSV is ignored by Git.

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
