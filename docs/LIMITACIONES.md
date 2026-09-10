# Limitations

This document states the known limitations of BacterioScope Phase 0 explicitly.
Understanding what the system does not do is as important as knowing what it does.

---

## 1. Measurement validation only — not S/I/R validation

The current validation (Phase 0) measures zone diameters in millimetres and
computes Essential Agreement (EA), Mean Absolute Error (MAE), and Pearson r
against a reference dataset. It does **not** validate S/I/R categorical accuracy.

**Why:** The reference dataset (Dryad/UZH) uses EUCAST 2023 breakpoints from the
SIRscan automated reader. BacterioScope classifies using CLSI M100-Ed33 2023
breakpoints. EUCAST and CLSI breakpoints differ for several antibiotic-organism
combinations. Comparing S/I/R categories across these two standards produces
misleading error rates that reflect the standard difference, not system performance.

**Consequence:** The system's categorical accuracy (CA), Very Major Error (VME),
and Major Error (ME) rates have not been validated against a CLSI-annotated
clinical reference. Full S/I/R validation is planned for Phase 3 using a
CLSI-annotated dataset.

---

## 2. Manual antibiotic assignment in Phase 0

The Hough-based disk detector used in Phase 0 cannot read the antibiotic
abbreviation printed on each disk. Users must manually assign the antibiotic to
each detected disk in the Streamlit interface. The phase 0 S/I/R output is
therefore only as accurate as the user's assignment.

**Consequence:** The system is not fully automated in Phase 0. Full automation
requires the YOLOv8 model trained in Phase 2. The current 29-class label-reading
model (102 training images, ~3.5 examples per class) does not reach a usable
confidence level -- `confidence_threshold` is deliberately kept at a defensible
0.25 floor rather than lowered to force detections out of an undertrained
model. A single-class "disk" detector (collapsing all 29 antibiotic classes to
one "disk" label, letting panel position resolve identity instead) finished
training and reaches mAP50=0.995 on its own held-out Roboflow test split.
It does not, by itself, remove the manual assignment step (identity still
resolves through panel position, not label reading).

An earlier round of this document claimed it "is not a proven replacement
for Hough" based on a head-to-head at `conf=0.5` (60.0% exact disk-count
match vs Hough's 73.8% on the 80 real UZH photos this project validates
against). That comparison used an untuned threshold and was wrong. A
confidence sweep found a sharp optimum around `conf=0.27-0.30`:
**76-77.5% exact-count match, matching or slightly beating Hough** --
the earlier conclusion is corrected here rather than left standing. The
model is real and usable
(`PipelineConfig(detector_weights=Path("data/models/single_class/
yolov8_disks.pt"), confidence_threshold=0.28)`), with a real labelling bug
also fixed this round (every detection previously shared the literal
class name `'disk'`, now numbered `disk_0`, `disk_1`, ... to match Hough).
The pipeline's default still stays on Hough for now -- not because the
single-class model measured worse, but because switching the default
detector is a broader deployment decision (adds a torch/ultralytics
dependency and model-load latency, and the model's sharp sensitivity to
the confidence threshold, near-zero exact matches just outside the
0.27-0.30 band, is a real operational risk Hough does not carry) that
has not yet been made, not a closed question.

---

## 3. Image quality dependency, and confirmed failure on confluent zones

Zone segmentation accuracy depends on image quality. Factors that degrade
performance include:

- Uneven bench lighting or strong directional shadows on the agar surface.
- Flash reflections creating bright spots inside the inhibition zone.
- Camera motion blur or out-of-focus disk labels.
- Non-standard agar colour (e.g. blood agar vs Mueller-Hinton).
- Overlapping zones from closely spaced disks.

The system includes a CLAHE (Contrast Limited Adaptive Histogram Equalization)
option for real-plate images, but there is no guarantee of accurate segmentation
under extreme or unusual lighting conditions.

**Confirmed, not theoretical, and partially addressed:** an identity-matched
validation pass (see [VALIDATION_REPORT.md](VALIDATION_REPORT.md)) found that
on real UZH plates (16 disks on one 90mm plate, confluent overlapping zones),
measured diameters for all 16 different antibiotics clustered within ~1.5mm of
each other -- the segmenter was measuring one shared confluent blob for every
disk, not 16 different biological responses. `ZoneSegmenter.segment_all()` now
splits confluent zones with a Voronoi partition (each pixel assigned to its
geometrically nearest disk), verified correct on a controlled case with two
disks of deliberately different true zone sizes (recovered exactly: 40mm and
20mm). This is real, tested progress for plates with *partial* overlap.

It is not a complete fix. Checked directly on the real UZH images: for several
adjacent disk pairs on the densest plates, the raw pixel intensity between the
two disks is completely flat across the entire gap -- no rise, no dip. When
two zones are that fully confluent, there is no boundary left in the
photograph for any algorithm, geometric or intensity-based, to recover; a
human reading the same photo by eye faces the identical ambiguity. This
16-disk-dense research protocol is not representative of routine clinical
practice (6-12 disks with normal CLSI spacing); whether ordinary clinical
panels confluence this severely has not yet been measured directly.

A related, distinct problem was found, root-caused, and fixed: at the
default ROI crop size, most real UZH photos had Otsu marking essentially
the entire search crop as "zone" for most disks, not the real zone-vs-lawn
boundary -- even on sparse, widely-spaced 4-disk plates with no neighbour
nearby, ruling out confluence as the cause. Growing the crop was tried
first and tested directly: it did not fix this -- Otsu kept marking the
whole (larger) crop as zone regardless of size, and the resulting
measurement got worse, not better (some real photos jumped to 45-50mm on a
physically ~90mm plate). `ZoneSegmenter._search_radius()` applies two
geometric safety caps (nearest-neighbour distance, and an absolute
plausible-zone-size ceiling) so this cannot happen unboundedly, but a crop
size change alone never addressed the underlying cause.

Direct pixel measurement found the real cause: the paper disk itself
(bright, ~150-200) is almost always a far stronger bright/dark signal than
the actual zone-vs-lawn contrast, sometimes as little as 15 grey levels
apart on real photos. Otsu, run over the whole crop including the disk,
reliably locks onto disk-vs-everything instead of zone-vs-lawn --
confirmed directly: a between-class-variance quality score computed the
same way Otsu picks its threshold was *highest* (0.91-0.92) on exactly the
real photos whose masks filled 100% of their crop, because that score was
measuring the disk/background split, not zone/lawn. Fixed by excluding the
disk's own area from Otsu's histogram before computing the threshold
(`ZoneSegmenter._otsu_excluding_disk()`). Measured, not assumed: on the
20-image identity-matched real-photo set, EA moved from 24.1% to 32.9%,
MAE from 7.44mm to 6.28mm, Pearson r from 0.089 to 0.193 -- real progress,
still well short of the 90% EA target and still limited by the fully
confluent, zero-signal case described above.

The identity-matched validation sample grew from 3 to 20 images (48 to 316
disk-antibiotic pairs) this round, reaching the range this document
previously said was needed for a stable estimate. The larger sample
resolved an artifact of the earlier tiny sample (Pearson r moved from
-0.262 to +0.089 -- a real near-zero correlation, not the earlier
small-sample noise) while confirming EA and MAE as real, not noise
(22.9%->24.1%, 7.11mm->7.44mm across the two sample sizes).

**Disk-based calibration (`use_disk_calibration`, Phase 3) was investigated
and found to have been non-independent by construction.** Disk detection
runs with `px_per_mm=px_per_mm_rim` already set, and Hough's disk-radius
search window is derived from that same plate-rim estimate -- so the
"disk-calibrated" ratio was plate-rim calibration scaled by whatever Hough
voted for inside a window centred on it, not an independent measurement
(confirmed: a suspiciously tight ~0.80x ratio across 20 real photos).
Fixed with a local, calibration-independent Otsu re-measurement of each
disk's true edge (`calibration.py::refine_disk_radius_px()`), which closed
most of the gap (identity-matched EA 14.9%->28.8%, MAE 8.88mm->7.42mm).
Even measured correctly, though, disk calibration still trails plate-rim
calibration (32.9% EA, 6.28mm MAE) -- not a remaining bug, a consequence
of calibrating against a ~50-60px reference (the disk) instead of a
~550-600px one (the plate): the same few pixels of edge noise are a much
larger relative error against the smaller reference. `use_disk_calibration`
stays `False` by default.

---

## 4. Tool for support — confirmation by a qualified professional is required

BacterioScope is a decision-support tool. It is not a validated medical device and
must not be used as the sole basis for clinical treatment decisions. Any result
produced by the system must be reviewed and confirmed by a qualified microbiology
professional before being used to guide antibiotic therapy.

This applies to Phase 0 and will apply to all future phases until the system
has been validated through a formal clinical evaluation study and, where required,
approved by the relevant national health authority (INVIMA in Colombia, or
equivalent).

---

## 5. Organism scope

The CLSI M100-Ed33 2023 breakpoint table currently implemented covers 15
antibiotics for Gram-negative Enterobacteriaceae. Other organism groups
(Staphylococcus, Pseudomonas, Acinetobacter, anaerobes) and other antibiotics
are not supported and will return UNKNOWN.

---

## 6. Disk overlap detection is approximated

The quality flag system detects potential zone overlaps by comparing the
distance between disk centres with the sum of zone radii. This is a circular
approximation — real zones are not perfect circles. The flag indicates that
overlap is possible; the actual degree of interference requires visual inspection.

---

## 7. Early reading is planned, not implemented

The Webber et al. 2022 evidence base supports reading disk diffusion at 6–10 hours
with acceptable categorical agreement. This capability is on the Phase 3–4 roadmap
and has not been implemented or validated in BacterioScope. No current version of
the system is designed for or validated with early-reading protocols.

---

## 8. Cefotaxime disks are reported as "ceftriaxone" — flagged, not fixed

Found by direct code audit, not measurement: `label_map.py::ROBOFLOW_TO_CLSI` maps
the YOLO class `"CTX 30"` to `"ceftriaxone"`. CTX is the standard disk-diffusion
abbreviation for **cefotaxime**, a distinct drug from ceftriaxone (CRO) — same
cephalosporin class, but not the same antibiotic. `CLSI_2023_ENTEROBACTERIACEAE`
(`clsi.py`) has no separate `"cefotaxime"` entry, so a cefotaxime disk is classified
using ceftriaxone's breakpoints and reported to the user as ceftriaxone.

This is unlike the `"GM 10"` / `"GEN 10"` merge a few lines below it in the same
map, which is correct: those are two abbreviation conventions for the *same* drug,
gentamicin. CTX and CRO are two different drugs.

**Why this is flagged instead of fixed directly:** CLSI M100 does, in most recent
editions, publish identical Enterobacterales zone-diameter breakpoints for
ceftriaxone and cefotaxime, which would mean the S/I/R *call* is unaffected even
though the *reported drug name* is wrong -- but this is recalled from general
clinical-microbiology knowledge, not verified against the actual M100-Ed33 document
this project cites everywhere else, and the earlier segmentation and calibration
fixes in this document were only made after measuring them directly. A wrong
breakpoint value asserted with unearned confidence is worse than an open question
for a clinical decision-support tool. This needs sign-off from the project's
microbiology team (Paula Becerra Lara, Farid) against the actual CLSI M100-Ed33
table before either adding a separate `"cefotaxime"` entry or documenting the
merge as an intentional, confirmed equivalence.
