# BacterioScope Validation Report

> Dataset: Egli et al. (2023) / University of Zurich SIRscan.
> doi:10.5061/dryad.5dv41nsfj

## Scope and limitations

This report validates **zone-diameter measurement accuracy only** (mm vs SIRscan reference).
S/I/R classification is **not** compared because:

- The UZH reference uses **EUCAST 2023** breakpoints (SIRscan automated reader).
- BacterioScope classifies using **CLSI M100-Ed33 2023** breakpoints.
- EUCAST and CLSI thresholds differ for many antibiotic-organism combinations (e.g. ciprofloxacin S: EUCAST >= 25 mm vs CLSI >= 26 mm for Enterobacteriaceae).
- Comparing S/I/R across standards produces misleading discordance rates.

Full S/I/R validation against a CLSI-annotated reference is planned for Phase 3.

### Matching strategy — Phase 0 limitation

Disks are matched to reference measurements by **rank-order pairing** (both sets sorted ascending by diameter). This is an approximation valid when zone-size rank order is consistent across images. Full per-antibiotic matching requires Phase 2 (YOLOv8 label reading).

## Dataset summary

| Item | Value |
|---|---|
| Dataset | University of Zurich SIRscan (Egli et al., 2023) |
| Reference system | SIRscan automated reader (EUCAST 2023) |
| Total images evaluated | 80 |
| Images with matching disk count | 20 |
| Disk-antibiotic pairs used for EA | 320 |
| Images excluded (disk count mismatch or error) | 60 |

## Measurement accuracy

| Metric | Value | Target | Criterion |
|---|---|---|---|
| Essential Agreement (EA, +-2 mm) | **32.2%** | >= 90% | ISO 20776-2 / EUCAST EDef 13.2 |
| Mean Absolute Error (MAE) | **4.27 mm** | — | mm |
| Pearson r | **0.588** | — | — |

### Bland-Altman limits of agreement

| Stat | Value |
|---|---|
| Bias (mean diff) | +1.41 mm |
| SD of differences | 5.88 mm |
| Upper LoA (+1.96 SD) | +12.92 mm |
| Lower LoA (−1.96 SD) | -10.11 mm |
| Pairs analysed | 320 |

### Definition of Essential Agreement used here

Classical EA (ISO 20776-2) is defined for MIC broth microdilution: the test-system MIC must fall within one two-fold dilution of the reference MIC. BacterioScope measures zone diameters in mm, not MIC values. EA is **adapted** as the fraction of diameter measurements within **+-2 mm** of the SIRscan reference, consistent with EUCAST EDef 13.2 inter-laboratory reproducibility. This adaptation must be disclosed when comparing to ISO 20776-2 EA figures.

## Excluded images

60 image(s) were excluded from EA: disk count mismatch between pipeline and reference, or pipeline error.

- 1.1.1. original.jpg — disk count mismatch
- 1.10.1. original.jpg — disk count mismatch
- 1.3.1. original.jpg — disk count mismatch
- 1.4.1. original.jpg — disk count mismatch
- 1.5.1. original.jpg — disk count mismatch
- 1.6.1. original.jpg — disk count mismatch
- 1.8.1. original.jpg — disk count mismatch
- 2.1.1. original.jpg — disk count mismatch
- 2.10.1. original.jpg — disk count mismatch
- 2.2.1. original.jpg — disk count mismatch
- 2.3.1. original.jpg — disk count mismatch
- 2.4.1. original.jpg — disk count mismatch
- 2.5.1. original.jpg — disk count mismatch
- 2.6.1. original.jpg — disk count mismatch
- 2.7.1. original.jpg — disk count mismatch
- 2.8.1. original.jpg — disk count mismatch
- 2.9.1. original.jpg — disk count mismatch
- 3.10.1. original.jpg — disk count mismatch
- 3.11.1. original.jpg — disk count mismatch
- 3.12.1. original.jpg — disk count mismatch
- ... and 40 more (see failed_images.log)

## Phase 3 calibration experiment (disk-based vs plate-rim)

`PipelineConfig.use_disk_calibration` (see `calibrate_from_disk_radius_px()`) computes
px/mm from the median detected disk radius (6 mm physical reference) instead of the
plate rim. Run with `python scripts/validate_measurement.py --disk-calibration` to
enable it. On this 80-image subset it currently performs **worse** than plate-rim
calibration:

| Calibration | EA (±2mm) | MAE | Bias |
|---|---|---|---|
| Plate rim (default) | 32.2% | 4.27 mm | +1.41 mm |
| Disk-based (Phase 3) | 12.2% | 7.56 mm | +7.35 mm |

Reason: without YOLOv8 reading disk labels reliably yet, the Hough fallback's detected
"disks" include false positives from agar texture and lawn edges, so the median disk
radius is a noisier reference than the plate rim. Disk-based calibration is expected to
overtake plate-rim calibration once F2 (YOLOv8 label reading) is trained to a
confidence level where false-positive disk detections are rare.

## Annotated examples

Annotated plate images with detected halos (pipeline) and reference diameter labels (cyan) are saved in `docs/figures/`. Reference labels show the SIRscan measurement for each disk, paired by rank order.

## How to reproduce

```bash
python scripts/download_data.py       # follow manual download prompt
python scripts/prepare_dataset.py     # normalise CSV
python scripts/validate_measurement.py  # compute EA / MAE / Pearson r
# Quick subset (first 20 images):
python scripts/validate_measurement.py --subset 20
```

Failures are logged to `data/processed/failed_images.log`.

## Citation

> Egli A, Imkamp F, Amlang G, Brunner S, Albrich W, et al. (2023).
> *Automated reading of disk diffusion antibiograms.*
> Dataset on Dryad Digital Repository.
> https://doi.org/10.5061/dryad.5dv41nsfj
> License: CC0 1.0 Universal.

---

*This report is generated automatically by `scripts/validate_measurement.py`.*
