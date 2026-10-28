# Submission gallery (Persona 4)

The images for the Devpost gallery and the submission page, where each one comes
from, and the caption we may use. Every image is either a bundled synthetic
fixture or an existing committed pipeline illustration. No patient or
institutional image goes in the public gallery.

## Capture rules

- Use only `examples/synthetic/*` plates or the committed `docs/plate_*.png`
  illustrations as sources. Do not upload anything from
  `data/processed/validation_figures/` or `examples/synthetic/reference_annotated/`
  back into the app; those are outputs, not inputs.
- Keep the `.env` file, terminal history, and secrets pages out of every frame.
- Label synthetic plates as synthetic in the caption.
- Captions must match the allowed claims in `docs/SUBMISSION_KIT.md`. Do not
  imply automation, clinical validation, or any real-photo accuracy above 32.9%.

## Gallery list

| # | Image | Source | Caption |
|---|---|---|---|
| 1 | Intake screen | Screenshot of `/?lang=en` | One photo in. The microbiologist stays in charge. |
| 2 | Detection and measurement | Screenshot of `/?sample=real_plate_box4&lang=en` | Every disk detected, every zone measured against the 90 mm rim. Untrusted measurements are flagged. |
| 3 | Zone correction with loupe | Screenshot of `/?sample=plate_mixed_sir&lang=en`, dragging a zone edge | Drag a zone edge; the loupe magnifies it and the category updates live. The edit is traced. |
| 4 | Grounded agent review | Screenshot of the review panel after Review with Nemotron | Nemotron writes a review that may cite only the evidence it was given. |
| 5 | Rule coverage and alerts | Screenshot of the coverage and alerts blocks | Expert rules stay disabled until a microbiologist reviews them; INS/PAHO alerts are optional. |
| 6 | Pipeline stages | `docs/pipeline_demo.gif` | Calibration, detection, zone segmentation, CLSI classification. |
| 7 | Measurement validation | `docs/plate_classified.png` | Classified output under CLSI M100-Ed33. |

## Committed illustration sources

Already in the repository, safe to reuse directly:

- `docs/pipeline_demo.gif` -- animated pipeline walkthrough.
- `docs/plate_original.png`, `docs/plate_detected.png`, `docs/plate_zones.png`,
  `docs/plate_classified.png` -- the four pipeline stages.
- `docs/lightbox_demo.jpg` -- light-box reference screenshot.
- `data/processed/validation_figures/bland_altman.png` and
  `scatter_measured_vs_reference.png` -- measurement validation plots (use only
  with the honest 32.9% EA caption; these are committed summary plots).

## Synthetic plate sources

From `examples/synthetic/` (regenerate with `scripts/generate_test_plates.py`):
pan-susceptible, MDR, mixed S/I/R, 12-disk panel, carbapenem-resistant, uneven
light, large zones, ESBL-like. Use the mixed S/I/R and 12-disk plates for the
richest screenshots.

## Export settings

- Capture the browser at 1440x900, English UI, consistent across frames.
- Export PNG for screenshots, keep the GIF as is.
- Keep file names descriptive (`gallery_01_intake.png`, ...). Store exported
  gallery files outside git unless the team decides to commit them; this
  document is the manifest, not the binary store.
