# Submission kit -- Nebius x NVIDIA hackathon

Everything the team needs to ship the submission: what is done, the video script, the Devpost
text, the claims we may and may not make, and the remaining tasks. Numbers here come from
`docs/EVALUATION_REPORT.md` and `docs/VALIDATION_REPORT.md`; if those change, update this file.

## 1. Status (2026-10-19, `main` at the merge of PR #10)

| Area | State | Where |
|---|---|---|
| Vision pipeline (disks, zones, CLSI M100-Ed33) | Done | `src/bacterioscope/pipeline.py` |
| Rule tools (intrinsic, phenotype, cascade, ESBL screen) | Done; catalog empty by design until reviewed | `src/bacterioscope/rules/` |
| Agent: Nemotron via Token Factory, routing, validated report, fallback | Done | `src/bacterioscope/agent/` |
| INS / OPS public alerts via Tavily | Done | `src/bacterioscope/integrations/tavily.py` |
| Evaluation: synthetic benchmark + live agent run | Done, first live run 16/16 grounded | `docs/EVALUATION_REPORT.md` |
| Review UI ("light box"), ES/EN, phone width | Done | `http://localhost:8000/` |
| MCP server (7 tools) | Done | `bacterioscope-mcp`, README "MCP server" |
| Docker image, CI (3 Python versions, CodeQL, secret scan) | Green | `.github/workflows/` |
| Public deployment | **Open** | section 5 |
| Architecture diagram, video, Devpost, platform feedback | **Open** | sections 2-4, 6 |

## 2. Video script (3 minutes)

Record at 1440x900, Spanish UI or English UI consistently; English narration reaches more judges.
Start the app with `uvicorn bacterioscope.api.routes:app --port 8000` and a `.env` holding the keys.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:20 | Intake screen (`/?lang=en`) | Kirby-Bauer disk diffusion is still read by hand in most mid- and low-complexity labs in Latin America. A tech measures every zone with a ruler and looks up breakpoints. BacterioScope reads the plate photo and keeps the microbiologist in charge. |
| 0:20-0:50 | Click the real 16-disk sample (`/?sample=real_plate_box4&lang=en`) | Every disk is detected and every zone is measured on the photo, calibrated against the 90 mm rim. Olive hatching marks measurements the system does not trust, and those never feed expert rules. |
| 0:50-1:25 | Open `/?sample=plate_mixed_sir&lang=en`; click ciprofloxacin; drag its handle | One ruler per antibiotic shows the CLSI bands. Drag a zone edge: the loupe magnifies the edge three times with its own millimetre scale, and the category changes live. The correction is traced, and it blocks the AI review, because the report cannot yet trace a hand-edited diameter. Restore it. |
| 1:25-2:15 | Click "Review with Nemotron" (alerts on) | Nemotron on Nebius Token Factory writes the review. It only sees structured evidence, never the image. The narrative is validated against a JSON schema and may cite only evidence that exists. Point at the citations, the INS and PAHO alerts, the rule coverage stating that no expert rules are enabled yet, and the traceability hashes. Type a reviewer name, then sign and download. |
| 2:15-2:35 | Claude Desktop or Claude Code calling `bacterioscope_analyze_plate` | The same workflow is an MCP server, so any agent can read a plate, correct it and request the review. |
| 2:35-3:00 | `docs/EVALUATION_REPORT.md` key findings | 16 of 16 live reviews were grounded. On synthetic plates the pipeline found 54 of 54 disks, and it made no dangerous errors on unflagged disks. On real photos measurement agreement is still 32.9%, which is why a human signs every result. Next: a supervised pilot with a lab. |

Do not show the `.env` file, the terminal history with keys, or the GitHub secrets page.

## 3. Devpost text

**Name:** BacterioScope

**Tagline:** Read an antibiogram plate from a photo, with an AI review that can only cite the evidence it was given.

**Inspiration.** Antimicrobial resistance is a public-health priority in Latin America, yet many
mid- and low-complexity labs have no automated AST reader. Disk diffusion plates are measured by
hand and checked against CLSI tables, and alerts from INS (Colombia) and PAHO live on separate
websites. We wanted one traceable place for that review.

**What it does.** From one photo of a Kirby-Bauer plate, BacterioScope:
- detects every disk and measures each inhibition zone in millimetres;
- classifies S/I/SDD/R with CLSI M100-Ed33 and flags measurements it does not trust.

The microbiologist reviews everything on a black "light box" screen and can correct any zone by
dragging it. Nemotron then writes a review grounded in the deterministic results, the
expert-rule tools and official INS/PAHO alerts found through Tavily. The review is validated
against a schema, may cite only evidence that exists, and falls back to a complete
deterministic report when validation fails. The same workflow is exposed as an MCP server.

**How we built it.**
- **Vision:** OpenCV for Hough disk detection, Otsu zone segmentation that excludes the disk itself, and Voronoi splitting for confluent zones.
- **Rules and alerts:** a deterministic CLSI classifier and rule tools, and Tavily restricted to official INS and PAHO domains.
- **Models:** Nemotron Nano, Super and Ultra on Nebius Token Factory, through its OpenAI-compatible API. Difficulty routing sends the report to Super and escalates to Ultra on complex phenotypes.
- **Apps:** a FastAPI back end with a hand-built front end (no framework, strict CSP, bilingual) and a FastMCP server.
- **Quality:** 500+ tests, mypy strict, CodeQL, Docker, and a GitHub Actions workflow that runs the live evaluation with repository secrets.

**Challenges.**
- On real photos, the paper disk is a much stronger signal than the faint zone edge, so we had to exclude it from thresholding.
- On dense 16-disk plates, neighbouring zones merge with no visible boundary.
- Keeping the language model honest: it never sees the image, it may cite only evidence IDs from the deterministic report, and a manual correction blocks the review until it can be traced.

**Accomplishments.**
- On the first live evaluation, 16 of 16 reviews were grounded and validated, at about 2.5 s median per plate.
- Routing used Super for every report and 0.74x the output tokens of an Ultra-only setup, with the same grounded rate.
- On synthetic plates, 54 of 54 disks were detected, with zero dangerous category errors on unflagged disks.

**What we learned.** Measuring honestly matters more than a good-looking number. Our real-photo
essential agreement is 32.9%, far from the 90% clinical target, so the product is decision
support with mandatory human sign-off, not an automated reader.

**What's next.**
- A microbiologist-reviewed expert-rule catalog.
- Reading the printed disk codes automatically.
- A supervised pilot with a Colombian lab, measuring review time and corrections caught.

**Built with:** Python, OpenCV, scikit-image, FastAPI, Nebius Token Factory, NVIDIA Nemotron,
Tavily, MCP, Docker, GitHub Actions.

## 4. Claims

Allowed, with the source:
- 16/16 grounded live reviews, routed and Ultra-only (`EVALUATION_REPORT.md`, Stage 2).
- 54/54 disks detected on 8 synthetic plates; 0 very major/major errors on 28 unflagged disks (Stage 1).
- Real-photo essential agreement 32.9% on 20 identity-matched images (`VALIDATION_REPORT.md`).
- Every report requires human sign-off; the model never sees the image.

Not allowed:
- "Automated", "replaces the microbiologist", "clinically validated", or any accuracy claim on real plates above 32.9%.
- That the system reads antibiotic names from the disks today. Identity comes from manual or panel assignment.
- Cost savings or time savings. They were not measured, and we have no prices.
- That expert rules fired. The catalog is empty until a microbiologist reviews it.
- Presenting synthetic-plate numbers as clinical performance.

## 5. Remaining tasks

| Task | Owner | Due |
|---|---|---|
| Public deployment of the Docker image with `NEBIUS_API_KEY` / `TAVILY_API_KEY` as platform secrets | Sebastian, with Esteban | Fri 23 Oct (go/no-go) |
| Architecture diagram: photo -> pipeline -> rule tools + Tavily -> Nemotron -> validator -> UI/MCP | Sebastian | Sat 24 Oct |
| Paula reviews the CLSI breakpoints and the demo wording | Paula | Sat 24 Oct |
| Feature freeze; fixes and docs only | All | Mon 26 Oct |
| Record and edit the 3-minute video (section 2) | Sebastian | Wed 28 Oct |
| Devpost page (section 3), screenshots from `docs/lightbox_demo.jpg` | Sebastian | Wed 28 Oct |
| Submit, with one day of buffer | Esteban | Thu 29 Oct |

**Deployment notes:**
- Any host that runs a Docker image on one port works, for example Hugging Face Spaces (Docker), Render or Fly.io.
- The image listens on 8000 and starts uvicorn by default.
- Keep `use-alerts` optional. Every review on a public demo spends Token Factory credit, so watch usage, or add a per-IP limit if the link circulates widely.
- Only the bundled samples and non-identifiable photos may be used on a public instance.

## 6. Platform feedback for Nebius (from building this)

- The OpenAI-compatible endpoint worked on the first try, and `usage` token counts come back on every call, which made the cost-aware evaluation possible.
- Model ID casing is inconsistent across tiers: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b` and `nvidia/Nemotron-3-Ultra-550b-a55b`. That makes it easy to mistype one, and we had to resolve them from the live catalog.
- The pricing page needs a logged-in session, so a CI job cannot report cost without someone copying prices by hand.
- Ultra was not slower than Super for these short reports (median 2.3 s vs 2.5 s). That was a useful surprise when deciding how to route.
