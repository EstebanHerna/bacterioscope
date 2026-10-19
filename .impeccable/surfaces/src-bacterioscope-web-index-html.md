---
version: 1
slug: "src-bacterioscope-web-index-html"
primary_target: "src/bacterioscope/web/index.html"
related_targets: ["src/bacterioscope/web/app.js","src/bacterioscope/web/app.css"]
---

# Lab review surface

Scope: the BacterioScope plate-review web app (single page) served by FastAPI at `/`. Mode: Operate.

Audience and job: a clinical microbiologist reads one incubated Kirby-Bauer plate photo, checks each measured zone, corrects what is wrong, assigns or confirms antibiotics, requests the Nemotron review, and downloads a signed-off JSON report. Secondary: hackathon judges watching a 3-minute demo.

Proof/content: real pipeline output (disk centres, zone contours, mm, flags), CLSI Ed33 breakpoints, the agent's grounded explanation with checked citations, INS/OPS alerts, traceability. Synthetic sample plates are labelled synthetic.

Constraints: bilingual ES/EN toggle; category never by colour alone; S/I/R colours only for categories; flags never in resistant red; empty or disabled rule catalogs read as "unavailable", never as a negative finding; manual corrections are traced and block agent submission; `POST /analyze` stays compatible.

## Direction contract

THESIS: The screen is the matte black, non-reflective background a microbiologist already reads plates against (CLSI M02). The photo leads, every measurement is drawn on it to true scale. Refuses the clinical SaaS dashboard (sidebar, white cards, blue accent) and the neon "AI lab".

OWN-WORLD: Matte felt black ground, porcelain disk-paper ink, hairline graticule rules, no cards and no shadows, panels divided by one-pixel rules. Colour appears only as S/SDD/I/R category fills and an olive quality-flag hatch. Atkinson Hyperlegible Next for UI, Atkinson Hyperlegible Mono for every millimetre and code, read as an instrument.

STORY: The visitor sees their plate measured disk by disk, sees which zones the system itself distrusts, corrects one by dragging its ring, and leaves with a report whose every sentence traces to evidence.

FIRST VIEWPORT: Full-bleed light box. Left about 60%: the plate at reading size, a 90 mm dial graticule around the rim, zone contours drawn in porcelain hairline, flagged zones hatched, a code + mm tag per disk. Right about 40%: one millimetre ruler per antibiotic with R / I-SDD / S breakpoint segments, the measured value as a caliper jaw, the category letter large at the end. A thin instrument strip on top: name, sample picker, ES/EN, calibration readout. Primary action "Revisar con Nemotron" sits under the rulers. Empty state: dashed 90 mm ring, drop target, synthetic sample plates laid on the felt.

FORM: Light box (caja de luz), position 4 of my ordered list, seed key dc7b8a6a. Raises: live tabular readout while dragging (from the variable-font specimen); the disk under examination ringed in one fixed focus treatment at true scale (from the star atlas); a loupe magnifies the selected disk while the whole plate stays visible (from the transit diagram); a millimetre graticule calibrated from the 90 mm rim toggles as a real state (from Crouwel). Signature interaction: drag a zone ring to correct its diameter, digits tick, ruler jaw follows, category recomputes live. Motion: rings draw in clockwise from 12 o'clock once on load; reduced motion draws instantly.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
