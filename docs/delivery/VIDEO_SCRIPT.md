# Submission video: script and edit plan (Persona 4)

Production script for the 3-minute demo video. The narration and claims come
from `docs/SUBMISSION_KIT.md` section 2; numbers trace to
`docs/EVALUATION_REPORT.md` and `docs/VALIDATION_REPORT.md`. Do not add any
claim not listed in the submission kit "Claims" section.

## Setup before recording

- Start the app with keys in `.env`:
  `uvicorn bacterioscope.api.routes:app --port 8000`.
- Record at 1440x900. Pick one UI language and keep it consistent; English
  narration reaches more judges, English UI is cleanest.
- Hide the `.env` file, any terminal with keys, and the secrets pages.
- Pre-open the three sample URLs in tabs so transitions are instant:
  - `/?lang=en`
  - `/?sample=real_plate_box4&lang=en`
  - `/?sample=plate_mixed_sir&lang=en`

## Shot list and narration

| # | Time | Screen / action | Narration |
|---|---|---|---|
| 1 | 0:00-0:20 | Intake screen `/?lang=en` | Kirby-Bauer disk diffusion is still read by hand in most mid- and low-complexity labs in Latin America. A tech measures every zone with a ruler and looks up breakpoints. BacterioScope reads the plate photo and keeps the microbiologist in charge. |
| 2 | 0:20-0:50 | Click the real 16-disk sample | Every disk is detected and every zone measured on the photo, calibrated against the 90 mm rim. Olive hatching marks measurements the system does not trust, and those never feed expert rules. |
| 3 | 0:50-1:25 | Open mixed S/I/R sample; click ciprofloxacin; drag its handle; restore it | One ruler per antibiotic shows the CLSI bands. Drag a zone edge and the loupe magnifies it three times with its own millimetre scale; the category changes live. The correction is traced, and it blocks the AI review, because the report cannot yet trace a hand-edited diameter. Restore it. |
| 4 | 1:25-2:15 | Click Review with Nemotron, alerts on | Nemotron on Nebius Token Factory writes the review. It only sees structured evidence, never the image. The narrative is validated against a JSON schema and may cite only evidence that exists. Point at the citations, the INS and PAHO alerts, the coverage saying no expert rules are enabled yet, and the traceability hashes. Type a reviewer name, then sign and download. |
| 5 | 2:15-2:35 | Claude Desktop or Claude Code calling `bacterioscope_analyze_plate` | The same workflow is an MCP server, so any agent can read a plate, correct it, and request the review. |
| 6 | 2:35-3:00 | `docs/EVALUATION_REPORT.md` key findings | 16 of 16 live reviews were grounded. On synthetic plates the pipeline found 54 of 54 disks and made no dangerous errors on unflagged disks. On real photos measurement agreement is still 32.9%, which is why a human signs every result. Next: a supervised pilot with a lab. |

## Edit plan

- **Structure:** cold open on shot 1 (no title card longer than 2 s), then
  straight into the demo. End card at 2:55 with the project name, the tagline,
  and "decision support, human sign-off required".
- **Pacing:** keep each cursor action on screen long enough to read (about 1 s
  settle before narration moves on). The drag in shot 3 is the hero moment; let
  the loupe breathe.
- **Captions:** burn in short captions for the key terms (90 mm rim, grounded,
  fallback, MCP). Judges may watch muted.
- **Zoom-ins:** punch in on the citations and the traceability hashes in shot 4;
  punch in on the three headline numbers in shot 6.
- **Audio:** single voice track, light bed music under -20 dB. No stock
  "corporate" stingers.
- **Lower third once:** presenter/team name at shot 1 only.
- **Export:** 1080p, H.264, under the platform size limit; keep a 1440p master.

## Hard "do not" list

- No `.env`, no terminal with keys, no GitHub secrets page in any frame.
- Do not say "automated", "replaces the microbiologist", or "clinically
  validated".
- Do not claim the system reads antibiotic names off the disks today (identity
  is manual or panel-based).
- Do not present synthetic numbers as clinical performance.
- Do not claim cost or time savings; they were not measured.

## Pre-publish checklist

- [ ] Runtime under 3:00.
- [ ] Every spoken number matches the submission kit.
- [ ] No secrets visible in any frame (scrub frame by frame).
- [ ] Captions spell-checked.
- [ ] End card shows the human-sign-off line.
