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
one "disk" label, letting panel position resolve identity instead) reaches
much higher mAP50 on the same 102 images and is the current best replacement
for Hough-based localisation; it does not, by itself, remove the manual
assignment step.

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

A related, distinct problem was found and confirmed directly: at the
default ROI crop size, most real UZH photos have Otsu marking essentially
the entire search crop as "zone" for most disks, not the real zone-vs-lawn
boundary -- even on sparse, widely-spaced 4-disk plates with no neighbour
nearby, ruling out confluence as the cause. Growing the crop was tried and
tested directly: it does not fix this. Otsu keeps marking the whole (larger)
crop as zone regardless of its size on these images, and the resulting
measurement gets worse, not better (some real photos jumped to 45-50mm on a
physically ~90mm plate). `ZoneSegmenter._search_radius()` now applies two
geometric safety caps (nearest-neighbour distance, and an absolute
plausible-zone-size ceiling) so this cannot happen unboundedly, but the
underlying cause -- Otsu failing to find a true boundary on many real
photographs -- remains unresolved.

The identity-matched validation sample grew from 3 to 20 images (48 to 316
disk-antibiotic pairs) this round, reaching the range this document
previously said was needed for a stable estimate. The larger sample
resolved an artifact of the earlier tiny sample (Pearson r moved from
-0.262 to +0.089 -- a real near-zero correlation, not the earlier
small-sample noise) while confirming EA and MAE as real, not noise
(22.9%->24.1%, 7.11mm->7.44mm across the two sample sizes).

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
