# Devpost submission text (Persona 4)

Copy-ready text for the Devpost page. Numbers trace to
`docs/EVALUATION_REPORT.md` and `docs/VALIDATION_REPORT.md`; the allowed and
forbidden claims are in `docs/SUBMISSION_KIT.md` section 4. If those numbers
change, update this file before submitting.

## Name

BacterioScope

## Tagline

Read an antibiogram plate from a photo, with an AI review that can only cite the
evidence it was given.

## Elevator pitch (one line for the Devpost summary field)

A human-reviewed workflow that measures a Kirby-Bauer plate from one photo,
classifies S/I/SDD/R under CLSI M100-Ed33, and lets Nemotron write a review
grounded strictly in the deterministic evidence and official INS/PAHO alerts.

## Inspiration

Antimicrobial resistance is a public-health priority in Latin America, yet many
mid- and low-complexity labs have no automated AST reader. Disk-diffusion plates
are measured by hand and checked against CLSI tables, and alerts from INS
(Colombia) and PAHO live on separate websites. We wanted one traceable place for
that review.

## What it does

From one photo of a Kirby-Bauer plate, BacterioScope:

- detects every disk and measures each inhibition zone in millimetres;
- classifies S/I/SDD/R with CLSI M100-Ed33 and flags the measurements it does
  not trust.

The microbiologist reviews everything on a black light-box screen and can
correct any zone by dragging it. Nemotron then writes a review grounded in the
deterministic results, the expert-rule tools, and official INS/PAHO alerts found
through Tavily. The review is validated against a schema, may cite only evidence
that exists, and falls back to a complete deterministic report when validation
fails. The same workflow is exposed as an MCP server.

## How we built it

- **Vision:** OpenCV for Hough disk detection, Otsu zone segmentation that
  excludes the disk itself, and Voronoi splitting for confluent zones.
- **Rules and alerts:** a deterministic CLSI classifier and rule tools, and
  Tavily restricted to the official INS and PAHO domains.
- **Models:** Nemotron Nano, Super, and Ultra on Nebius Token Factory through
  its OpenAI-compatible API. Difficulty routing sends the report to Super and
  escalates to Ultra on complex phenotypes.
- **Apps:** a FastAPI back end with a hand-built front end (no framework, strict
  CSP, bilingual) and a FastMCP server.
- **Quality:** 500+ tests, mypy strict, CodeQL, Docker, and a GitHub Actions
  workflow that runs the live evaluation with repository secrets.

## Challenges we ran into

- On real photos, the paper disk is a much stronger signal than the faint zone
  edge, so we had to exclude it from thresholding.
- On dense 16-disk plates, neighbouring zones merge with no visible boundary.
- Keeping the language model honest: it never sees the image, it may cite only
  evidence ids from the deterministic report, and a manual correction blocks the
  review until it can be traced.

## Accomplishments we're proud of

- On the first live evaluation, 16 of 16 reviews were grounded and validated, at
  about 2.5 s median per plate.
- Routing used Super for every report and 0.74x the output tokens of an
  Ultra-only setup, with the same grounded rate.
- On synthetic plates, 54 of 54 disks were detected, with zero dangerous
  category errors on unflagged disks.

## What we learned

Measuring honestly matters more than a good-looking number. Our real-photo
essential agreement is 32.9%, far from the 90% clinical target, so the product
is decision support with mandatory human sign-off, not an automated reader.

## What's next

- A microbiologist-reviewed expert-rule catalog.
- Reading the printed disk codes automatically.
- A supervised pilot with a Colombian lab, measuring review time and corrections
  caught.

## Built with

Python, OpenCV, scikit-image, FastAPI, Nebius Token Factory, NVIDIA Nemotron,
Tavily, MCP, Docker, GitHub Actions.

## Links to fill at submission

- GitHub repository: https://github.com/EstebanHerna/bacterioscope
- Public demo URL: (from `deploy/DEPLOYMENT.md` once deployed)
- Video (3 min): (from `docs/delivery/VIDEO_SCRIPT.md` once recorded)

## Gallery

Use the manifest in `docs/delivery/GALLERY.md`. Lead with the grounded review
screenshot and the architecture diagram.

## Claims guard (do not submit violations)

Allowed: 16/16 grounded live reviews; 54/54 disks on 8 synthetic plates with 0
very major/major errors on 28 unflagged disks; real-photo EA 32.9% on 20
identity-matched images; mandatory human sign-off; the model never sees the
image.

Not allowed: "automated", "replaces the microbiologist", "clinically
validated", any real-photo accuracy above 32.9%, reading disk names today, cost
or time savings, claiming expert rules fired, or presenting synthetic numbers as
clinical performance.
