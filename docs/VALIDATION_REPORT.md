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

### Matching strategy

Two strategies are reported, clearly separated below: **identity matching** (each disk paired to its reference by the antibiotic printed on it, human-verified) where annotation exists, and **rank-order pairing** (both sets sorted ascending and paired by position) everywhere else. Rank-order pairing does not verify that the same physical disk is being compared and is reported only as an optimistic upper bound, never as the project's accuracy figure. Automatic per-antibiotic matching without manual annotation requires Phase 2 (YOLOv8 label reading) at a confidence level that is not yet reliable.

## Dataset summary

| Item | Value |
|---|---|
| Dataset | University of Zurich SIRscan (Egli et al., 2023) |
| Reference system | SIRscan automated reader (EUCAST 2023) |
| Total images evaluated | 80 |
| Images with matching disk count | 70 |
| Disk-antibiotic pairs used for EA | 1120 |
| Images excluded (disk count mismatch or error) | 10 |

## Measurement accuracy

### Identity-matched — the real number

Each disk matched to its reference by antibiotic identity (human-verified from the printed disk label), not by sorted rank. This is the defensible accuracy figure for the project.

| Metric | Value | Target |
|---|---|---|
| Essential Agreement (EA, +-2 mm) | **22.9%** | >= 90% |
| Mean Absolute Error (MAE) | **7.18 mm** | — |
| Pearson r | **-0.354** | — |
| Images identity-annotated | 3 |
| Disk-antibiotic pairs (identity) | 48 |

Annotate more images with `python scripts/annotate_pairs.py --batch data/raw/dryad_uzh/images_original --limit N` to grow this sample; 20-30 images gives a reasonably stable estimate.

### Rank-order pairing — optimistic upper bound, not a measurement

Both diameter lists sorted ascending and paired by position. This does not verify that the same physical disk is being compared, and inflates agreement whenever measurement error does not reorder the list — do not report this as the project's accuracy figure.

| Metric | Value | Target | Criterion |
|---|---|---|---|
| Essential Agreement (EA, +-2 mm) | **26.9%** | >= 90% | ISO 20776-2 / EUCAST EDef 13.2 |
| Mean Absolute Error (MAE) | **5.31 mm** | — | mm |
| Pearson r | **0.579** | — | — |

### Bland-Altman limits of agreement (rank-order pairs)

| Stat | Value |
|---|---|
| Bias (mean diff) | +3.16 mm |
| SD of differences | 6.67 mm |
| Upper LoA (+1.96 SD) | +16.22 mm |
| Lower LoA (−1.96 SD) | -9.91 mm |
| Pairs analysed | 1120 |

### Definition of Essential Agreement used here

Classical EA (ISO 20776-2) is defined for MIC broth microdilution: the test-system MIC must fall within one two-fold dilution of the reference MIC. BacterioScope measures zone diameters in mm, not MIC values. EA is **adapted** as the fraction of diameter measurements within **+-2 mm** of the SIRscan reference, consistent with EUCAST EDef 13.2 inter-laboratory reproducibility. This adaptation must be disclosed when comparing to ISO 20776-2 EA figures.

## Diagnostic findings (this validation round)

A first identity-matched validation pass surfaced a structural problem beyond calibration or detection: on real UZH plates (16 disks packed onto one 90mm plate with confluent, overlapping inhibition zones), measured zone diameters cluster tightly (stdev ~1.4-1.6mm) around ~27mm regardless of which antibiotic the disk carries. Real Kirby-Bauer results for 16 different drugs against one organism should vary far more (roughly 10-35mm) than that. The Otsu + watershed segmenter, tuned on isolated synthetic halos, is converging on a shared confluent boundary rather than each disk's own zone edge -- it measures the same thing 16 times, not 16 different biological responses. This is the leading suspect for why identity-matched Pearson r is near zero or negative even after the detection-radius and confidence-threshold fixes below: there is little real signal in the measurements to correlate against. Fixing this requires segmentation aware of neighbouring disks (e.g. a distance-transform watershed seeded from all detected disks at once, not an independent Otsu threshold per isolated ROI) -- not yet implemented.

Two other fixes landed this round, with a measurable before/after:

| Fix | Before | After |
|---|---|---|
| Hough disk radius: fixed pixel range vs calibration-derived window (detector.py) | Median disk read as 6mm=~7.7mm (+28% bias); wild over-detection (100-217 false circles) on several images | Systematic bias much smaller (~-15 to -20% on clean detections); false-circle storms eliminated |
| Confidence threshold: 0.04 (post-hoc lowered to force a 29-class model to emit something) vs 0.25 (defensible floor) | A single ~0.05-confidence YOLO false positive could pre-empt 16 reliable Hough detections (hybrid fallback only tries Hough when YOLO returns nothing) | Images with correct disk count: 24/80 -> 70/80 |

What this means for the headline numbers: rank-order EA moved from 32.8% to 26.9% across this round -- a *drop*, not an improvement, because the fixed detector now processes far more of the previously-excluded difficult images instead of silently failing on them. Fewer images being thrown out is progress even though the visible EA number went down; it is a more honest measurement over a harder, more complete sample, not a regression.

## Still unresolved

- **Zone segmentation on confluent real plates** (above) -- the single largest suspected contributor to remaining error, not yet fixed.
- **Identity-annotated sample is small** (3 images, 48 pairs). Needs 20-30 images (`scripts/annotate_pairs.py`) for a stable estimate; the current identity EA/MAE/r should be read as directional, not final.
- **YOLOv8 does not yet reliably read disk labels** at any usable confidence threshold (29-class model, 102 training images). A single-class 'disk' detector trained on the same images reaches much higher mAP50 in early epochs (see Phase 2 status in docs/ROADMAP.md / CLAUDE.md) and can replace Hough for localisation, but disk *identity* still resolves through panel position, not label reading, until far more labelled data exists.
- **EA is well below the ISO 20776-2 / EUCAST EDef 13.2 target of 90%** on both matching strategies. State plainly: BacterioScope does not yet meet the accuracy bar for real, unconstrained clinical photographs. It performs acceptably on synthetic and controlled images; real-photo accuracy is an open problem this report exists to make visible, not to paper over.

## Excluded images

10 image(s) were excluded from EA: disk count mismatch between pipeline and reference, or pipeline error.

- 2.8.1. original.jpg — disk count mismatch
- 3.4.1. original.jpg — disk count mismatch
- 4.25.1. original.jpg — disk count mismatch
- 4.26.1. original.jpg — disk count mismatch
- 4.27.1. original.jpg — disk count mismatch
- 4.29.1. original.jpg — disk count mismatch
- 4.32.1. original.jpg — disk count mismatch
- 4.33.1. original.jpg — disk count mismatch
- 4.38.1. original.jpg — disk count mismatch
- 4.42.1. original.jpg — disk count mismatch

## Annotated examples

Annotated plate images with detected halos (pipeline) and reference diameter labels (cyan) are saved in `data/processed/validation_figures/`. Reference labels show the SIRscan measurement for each disk, paired by rank order.

## How to reproduce

```bash
python scripts/download_data.py       # follow manual download prompt
python scripts/prepare_dataset.py     # normalise CSV
# Optional but recommended: identity-annotate a sample so EA/MAE/r
# are a real measurement, not a rank-order upper bound.
python scripts/annotate_pairs.py --batch data/raw/dryad_uzh/images_original --limit 20
# ... fill in the generated *_pairs.csv files, then:
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
