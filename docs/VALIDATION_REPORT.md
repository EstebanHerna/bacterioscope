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

**Read this before trusting the EA/MAE numbers below**: the UZH dataset's plates are square and cropped to nearly fill the frame (a research-imaging convention), not round plates with visible background like the phone photographs BacterioScope's plate-rim calibration is designed for. Some of the error below reflects that mismatch, not necessarily real-world accuracy on the round-plate phone photographs the tool actually targets. See docs/LIMITACIONES.md section 9 for the full finding.

### Matching strategy

Two strategies are reported, clearly separated below: **identity matching** (each disk paired to its reference by the antibiotic printed on it, human-verified) where annotation exists, and **rank-order pairing** (both sets sorted ascending and paired by position) everywhere else. Rank-order pairing does not verify that the same physical disk is being compared and is reported only as an optimistic upper bound, never as the project's accuracy figure. Automatic per-antibiotic matching without manual annotation requires Phase 2 (YOLOv8 label reading) at a confidence level that is not yet reliable.

## Dataset summary

| Item | Value |
|---|---|
| Dataset | University of Zurich SIRscan (Egli et al., 2023) |
| Reference system | SIRscan automated reader (EUCAST 2023) |
| Total images evaluated | 80 |
| Images with matching disk count | 59 |
| Disk-antibiotic pairs used for EA | 944 |
| Images excluded (disk count mismatch or error) | 21 |

## Measurement accuracy

### Identity-matched — the real number

Each disk matched to its reference by antibiotic identity (human-verified from the printed disk label), not by sorted rank. This is the defensible accuracy figure for the project.

| Metric | Value | Target |
|---|---|---|
| Essential Agreement (EA, +-2 mm) | **32.9%** | >= 90% |
| Mean Absolute Error (MAE) | **6.28 mm** | — |
| Pearson r | **0.193** | — |
| Images identity-annotated | 20 |
| Disk-antibiotic pairs (identity) | 316 |

Annotate more images with `python scripts/annotate_pairs.py --batch data/raw/dryad_uzh/images_original --limit N` to grow this sample; 20-30 images gives a reasonably stable estimate.

### Rank-order pairing — optimistic upper bound, not a measurement

Both diameter lists sorted ascending and paired by position. This does not verify that the same physical disk is being compared, and inflates agreement whenever measurement error does not reorder the list — do not report this as the project's accuracy figure.

| Metric | Value | Target | Criterion |
|---|---|---|---|
| Essential Agreement (EA, +-2 mm) | **38.1%** | >= 90% | ISO 20776-2 / EUCAST EDef 13.2 |
| Mean Absolute Error (MAE) | **3.93 mm** | — | mm |
| Pearson r | **0.783** | — | — |

### Bland-Altman limits of agreement (rank-order pairs)

| Stat | Value |
|---|---|
| Bias (mean diff) | +0.95 mm |
| SD of differences | 5.40 mm |
| Upper LoA (+1.96 SD) | +11.54 mm |
| Lower LoA (−1.96 SD) | -9.63 mm |
| Pairs analysed | 944 |

### Definition of Essential Agreement used here

Classical EA (ISO 20776-2) is defined for MIC broth microdilution: the test-system MIC must fall within one two-fold dilution of the reference MIC. BacterioScope measures zone diameters in mm, not MIC values. EA is **adapted** as the fraction of diameter measurements within **+-2 mm** of the SIRscan reference, consistent with EUCAST EDef 13.2 inter-laboratory reproducibility. This adaptation must be disclosed when comparing to ISO 20776-2 EA figures.

## Diagnostic findings (this validation round)

A first identity-matched validation pass surfaced a structural problem beyond calibration or detection: on real UZH plates (16 disks packed onto one 90mm plate with confluent, overlapping inhibition zones), measured zone diameters clustered tightly regardless of which antibiotic the disk carried -- the segmenter was measuring the same shared confluent blob for every disk, not 16 different biological responses.

### What was tried on segmentation, and what actually worked

`ZoneSegmenter.segment_all()` now segments every disk in the context of its neighbours rather than in isolation. Three approaches were attempted, in order:

1. **Marker-based watershed flooding on the raw photo.** Standard textbook approach, but real-photo texture (agar surface, printed disk labels, JPEG noise) creates false local ridges everywhere, so flooding barely left each seed -- every zone collapsed to roughly the seed's own size. Discarded.
2. **Watershed on a distance-transform elevation.** Removes the texture-noise problem, but on real (noisy, irregularly-shaped) masks the saddle points between confluent zones were themselves unreliable, and an edge disk with more open unclaimed territory could inherit a physically impossible region (one measurement hit 117mm on a 90mm plate). Discarded.
3. **Voronoi partition: each pixel assigned to its geometrically nearest disk centre.** Deterministic, independent of image noise. **Verified correct on a controlled case**: two disks with deliberately different true zone sizes (80px and 40px radius, overlapping) were recovered as 40mm and 20mm respectively -- exact. This is the shipped implementation.

The Voronoi split is real and tested (see `tests/test_watershed.py::TestSegmentAllVoronoiSplit`), but it did not meaningfully move the real-photo numbers below, and the reason is itself a finding, not an implementation gap: **for several adjacent disk pairs on the densest UZH plates, the raw pixel intensity between them is completely flat**, measured directly (no rise, no dip, ~70-90 vs ~70-90 across the entire gap between two specific disks checked by hand). When two zones are that fully confluent, there is no boundary left in the photograph for *any* algorithm to recover -- a human reading the same photo by eye faces exactly the same ambiguity. Voronoi still gives each disk a geometrically fair, bounded region instead of one shared blob reaching across the whole plate, which is real progress on plates with partial (not total) overlap; it cannot manufacture information a fully confluent photograph never captured.

Two other fixes landed this round, with a measurable before/after:

| Fix | Before | After |
|---|---|---|
| Hough disk radius: fixed pixel range vs calibration-derived window (detector.py) | Median disk read as 6mm=~7.7mm (+28% bias); wild over-detection (100-217 false circles) on several images | Systematic bias much smaller (~-15 to -20% on clean detections); false-circle storms eliminated |
| Confidence threshold: 0.04 (post-hoc lowered to force a 29-class model to emit something) vs 0.25 (defensible floor) | A single ~0.05-confidence YOLO false positive could pre-empt 16 reliable Hough detections (hybrid fallback only tries Hough when YOLO returns nothing) | Images with correct disk count: 24/80 -> 70/80 |

What this meant for the headline numbers *at that point in the project's history*: rank-order EA moved from 32.8% to 26.9% across this round -- a *drop*, not an improvement, because the fixed detector now processes far more of the previously-excluded difficult images instead of silently failing on them. Fewer images being thrown out is progress even though the visible EA number went down; it is a more honest measurement over a harder, more complete sample, not a regression. Later rounds (below) moved rank-order EA further, to the figure reported in the table at the top of this document -- this 26.9% figure is a step in that history, not the current number.

### The disk itself was polluting Otsu's threshold selection

A later round found a second, structural segmentation bug, unrelated to confluence: on many real UZH photos, every disk's zone mask filled essentially 100% of its crop's bounding box, *including on sparse 4-disk plates with no neighbour anywhere near* -- ruling out confluence or crop size as the cause (growing the crop measurably made it worse, not better, jumping to 45-50mm on a ~90mm plate). Direct pixel measurement found the real cause: the paper disk itself (bright, ~150-200) is almost always a far stronger bright/dark signal than the actual zone-vs-lawn contrast, sometimes as little as 15 grey levels apart on real photos. Otsu, run over the whole crop, reliably locks onto disk-vs-everything instead of zone-vs-lawn -- confirmed directly: a between-class-variance quality score computed the same way Otsu picks its threshold was *highest* (0.91-0.92) on exactly the real photos whose masks filled 100% of their crop, because that score was measuring the disk/background split, not zone/lawn.

Fixed by excluding the disk's own area from Otsu's histogram before computing the threshold (`ZoneSegmenter._otsu_excluding_disk()`), so Otsu only ever sees the zone-vs-lawn contrast that is actually being measured. This is a real, measured improvement, not a reparameterization: on a controlled synthetic case with a 15-grey-level zone-vs-lawn gap, the old (disk-included) threshold measured a 70px true zone as 168px; the fix measured it as 70px, exact. On the real 20-image identity-matched set this round, EA moved from 24.1% to 32.9%, MAE from 7.44mm to 6.28mm, and Pearson r from 0.089 to 0.193 -- real progress, still well short of the 90% EA target.

### Disk-based calibration was never independent of plate-rim calibration

`use_disk_calibration` (Phase 3) was investigated directly rather than left as an open question. It was not measuring the disk independently at all: `pipeline.analyze()` calls `detector.detect(image, px_per_mm=px_per_mm_rim)` *before* disk calibration runs, and Hough's disk-radius search window is derived from that same plate-rim estimate. The reported disk radius was therefore plate-rim calibration scaled by whatever Hough voted for inside a window centred on that same estimate -- confirmed directly: across 20 real photos the resulting ratio was a suspiciously tight ~0.80x, far too consistent to be an independent physical measurement.

Fixed with `calibration.py::refine_disk_radius_px()`: a local, calibration-independent Otsu threshold re-measures each disk's true edge directly in a small crop around its detected centre. This closed most of the gap on the 20-image identity-matched set (EA 14.9% -> 28.8%, MAE 8.88mm -> 7.42mm) -- real progress on a real bug. But disk calibration still trails plate-rim calibration (32.9% EA, 6.28mm MAE) even once measured correctly, and this remaining gap is not a bug: it is reference size. The plate rim spans roughly 550-600px in a canonical-resized image; a disk spans roughly 50-60px. The same few pixels of edge-detection noise are a far larger *relative* error against the smaller reference. `use_disk_calibration` stays `False` by default.

## Still unresolved

- **Zone segmentation on fully confluent real plates** (above). Voronoi splitting is implemented, tested, and verified correct when some boundary signal exists; it cannot help where the photograph itself has none. The 16-disk-dense UZH panel is a worst case for this -- a clinical panel with normal CLSI disk spacing (6-12 disks, properly separated) should confluence far less often, but this has not yet been measured directly.
- **Identity-annotated sample grew from 3 to 20 images** (48 to 316 pairs), reaching the stable-estimate range this file itself called for. Going from 3 to 20 images changed Pearson r from -0.262 to +0.089 -- the earlier negative correlation was small-sample noise, not a real effect. The position-to-antibiotic mapping used to identity-annotate the 17 new images was derived from the fixed panel template shared by the first 3 (verified by direct visual reading of the printed disk labels on several images per template variant before applying it), not re-read label by label on every image -- documented here so the provenance is explicit.
- **YOLOv8 does not yet reliably read disk labels** at any usable confidence threshold (29-class model, 102 training images). A single-class 'disk' detector trained on the same images reaches mAP50=0.995 on its own held-out test split (see Phase 2 status in docs/ROADMAP.md / CLAUDE.md). An earlier round of this report claimed it was not a proven replacement for Hough, based on a comparison at an untuned conf=0.5 (60.0% exact disk-count match vs Hough's 73.8% on the 80 real UZH photos this report evaluates). That was wrong: a confidence sweep found a sharp optimum around conf=0.27-0.30 where the single-class model matches or slightly beats Hough (76-77.5% exact match), with performance collapsing outside a fairly narrow band. Hough stays the pipeline's default regardless -- not because it measures better, but because switching the default detector is a deployment decision (added torch/ultralytics dependency weight, model-load latency, and a real threshold-sensitivity risk Hough does not have) that has not been made yet. Disk *identity* still resolves through panel position, not label reading, either way.
- **EA is well below the ISO 20776-2 / EUCAST EDef 13.2 target of 90%** on both matching strategies. State plainly: BacterioScope does not yet meet the accuracy bar for real, unconstrained clinical photographs. It performs acceptably on synthetic and controlled images; real-photo accuracy is an open problem this report exists to make visible, not to paper over.

## Excluded images

21 image(s) were excluded from EA: disk count mismatch between pipeline and reference, or pipeline error.

- 1.10.1. original.jpg — disk count mismatch
- 1.5.1. original.jpg — disk count mismatch
- 2.2.1. original.jpg — disk count mismatch
- 2.8.1. original.jpg — disk count mismatch
- 3.18.1. original.jpg — disk count mismatch
- 3.3.1. original.jpg — disk count mismatch
- 3.4.1. original.jpg — disk count mismatch
- 4.22.1. original.jpg — disk count mismatch
- 4.25.1. original.jpg — disk count mismatch
- 4.26.1. original.jpg — disk count mismatch
- 4.27.1. original.jpg — disk count mismatch
- 4.29.1. original.jpg — disk count mismatch
- 4.32.1. original.jpg — disk count mismatch
- 4.33.1. original.jpg — disk count mismatch
- 4.34.1. original.jpg — disk count mismatch
- 4.38.1. original.jpg — disk count mismatch
- 4.4.1. original.jpg — disk count mismatch
- 4.40.1. original.jpg — disk count mismatch
- 4.41.1. original.jpg — disk count mismatch
- 4.42.1. original.jpg — disk count mismatch
- ... and 1 more (see failed_images.log)

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
