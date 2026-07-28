# BacterioScope Validation Report

> Dataset: Egli A, et al. (2023) — University of Zurich SIRscan.
> doi:[10.5061/dryad.5dv41nsfj](https://doi.org/10.5061/dryad.5dv41nsfj)
>
> **Status: PENDING DATASET DOWNLOAD.**
> This file is a template. Run the steps in "How to reproduce" once the
> Dryad dataset has been downloaded to populate it with real metrics.

---

## Scope and limitations

This report validates **zone-diameter measurement accuracy only** (mm vs SIRscan reference).
S/I/R classification is **not** compared here because:

- The UZH reference uses **EUCAST 2023** breakpoints (from the SIRscan automated reader).
- BacterioScope classifies using **CLSI M100-Ed33 2023** breakpoints.
- EUCAST and CLSI thresholds differ for many antibiotic-organism combinations
  (e.g. ciprofloxacin S threshold: EUCAST ≥ 25 mm vs CLSI ≥ 26 mm for Enterobacteriaceae).
- Comparing S/I/R categories across two different standards would produce misleading
  discordance rates that reflect the standard difference, not system performance.

Full S/I/R validation against a CLSI-annotated reference set is planned for Phase 3.

### Matching strategy — Phase 0 limitation

In Phase 0, the Hough-based detector cannot read the antibiotic label printed on each disk.
Disks are matched to reference measurements by **rank-order pairing** (both sets sorted by
diameter ascending). This is an approximation valid when the rank order of inhibition zone
sizes is consistent across images, which holds for most antibiotic-organism combinations.

Images where the detected disk count differs from the reference count are flagged and
excluded from the EA calculation (see `data/processed/failed_images.log`).

Full per-antibiotic matching becomes possible in **Phase 2**, when the YOLOv8 model reads
the printed label on each disk.

---

## Dataset summary

| Item | Value |
|---|---|
| Dataset | University of Zurich SIRscan (Egli et al., 2023) |
| Reference system | SIRscan automated reader (EUCAST 2023) |
| Total images evaluated | _pending_ |
| Images with matching disk count | _pending_ |
| Disk-antibiotic pairs used for EA | _pending_ |
| Images excluded (disk count mismatch) | _pending_ |

---

## Measurement accuracy

| Metric | Value | Target | Criterion |
|---|---|---|---|
| Essential Agreement (EA, ±2 mm) | _pending_ | ≥ 90% | ISO 20776-2 / EUCAST EDef 13.2 |
| Mean Absolute Error (MAE) | _pending_ | — | mm |
| Pearson r | _pending_ | — | — |

### Definition of Essential Agreement used here

Classical EA (ISO 20776-2) is defined for MIC broth microdilution: the test-system MIC
must fall within one two-fold dilution of the reference MIC.
BacterioScope measures inhibition zone diameters in mm, not MIC values.
EA is therefore **adapted** as the fraction of diameter measurements within **±2 mm** of
the SIRscan reference diameter. This is the same tolerance used in EUCAST EDef 13.2 for
inter-laboratory reproducibility of disk diffusion measurements.
This adaptation must be disclosed when comparing results to ISO 20776-2 EA figures.

---

## Annotated examples

Annotated plate images showing detected zones vs reference diameters are saved in
`docs/figures/` after running `validate_measurement.py`.

_Examples will appear here once the dataset is downloaded and the script is run._

---

## How to reproduce

```bash
# 1. Download dataset (requires manual browser step — see module docstring)
python scripts/download_data.py

# 2. Normalise reference measurements
python scripts/prepare_dataset.py

# 3. Run measurement validation (all images)
python scripts/validate_measurement.py

# 4. Run on a quick subset (first 20 images)
python scripts/validate_measurement.py --subset 20
```

Failures (images where the pipeline crashed or disk count mismatched) are logged to
`data/processed/failed_images.log` and excluded from EA computation.

---

## Limitations

1. **Phase 0 disk labeling**: The Hough detector cannot identify which disk corresponds
   to which antibiotic. Rank-order matching is an approximation.
2. **Standard mismatch**: The reference uses EUCAST; BacterioScope uses CLSI.
   Only measurement accuracy is reported in this phase.
3. **Image diversity**: The UZH dataset consists of clinical isolates from a single
   institution with a standardised photography protocol. Performance on images taken
   with different cameras, distances, or lighting may differ.
4. **Plate centering**: Real plates may not be centred in the photograph. The Phase 0
   Hough calibration uses a fallback (90% of shorter dimension) when the plate rim
   is not detected, which reduces calibration accuracy.

---

## Citation

> Egli A, Imkamp F, Amlang G, Brunner S, Albrich W, et al. (2023).
> *Automated reading of disk diffusion antibiograms.*
> Dataset on Dryad Digital Repository.
> https://doi.org/10.5061/dryad.5dv41nsfj

---

*This report is generated automatically by `scripts/validate_measurement.py`.*
*Last run: pending dataset download.*
