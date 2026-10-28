# Agent report view (Persona 4)

How the agent review renders in the product, what every state means, and the
exact steps Persona 4 follows to exercise it for screenshots and the video. This
documents the shipped UI; it does not change the report contract, which Esteban
owns (`docs/contracts/agent-review-v1.schema.json`).

## Where it lives

The demo UI is the light box served by FastAPI at `/`
(`src/bacterioscope/web/index.html`, `app.css`, `app.js`) and backed by
`src/bacterioscope/api/lab.py`. The agent review is requested through
`POST /api/plates/{analysis_id}/review` and rendered by `renderReview()` in
`app.js`. The older Streamlit prototype (`src/bacterioscope/app.py`) is kept for
reference only and is not the demo surface.

## What the view shows

The review panel appears below the bench after the reviewer presses
**Review with Nemotron**. It renders, top to bottom:

1. **Status line.** One of:
   - `grounded` -- "Nemotron narrative (Nebius Token Factory), validated against
     the evidence." The narrative passed the JSON schema and every citation
     exists in the deterministic evidence.
   - `fallback` -- "No model narrative: {reason}. Everything deterministic below
     is complete." The deterministic report is shown in full. Reasons the UI can
     surface: Token Factory unavailable, model reply not JSON, reply incomplete,
     citation not in evidence, schema validation failed, or a rule claim that
     conflicts with the catalog status.
2. **Report results table.** Per disk: antibiotic, zone in mm, and S/I/SDD/R
   category, with the measurements the pipeline does not trust marked and
   excluded from expert rules.
3. **Rule coverage.** Intrinsic resistance, phenotype, cascade reporting, and
   the ESBL screen. With the catalog empty by design, the panel states the
   expert rule set is unavailable rather than implying no rule fired. The ESBL
   row reads "Not run: needs disk potency and assay context" unless typed inputs
   are supplied.
4. **Public alerts.** INS and PAHO results when alerts were requested, each with
   title, date, official source, and link. Alert status can be available,
   partial (one source did not respond), or unavailable; plate review continues
   regardless.
5. **Traceability.** Analysis id, image SHA-256, CLSI measurement edition, and
   the selected rule edition.
6. **Sign and download.** The reviewer types who is reviewing, then signs and
   downloads the report JSON. A missing reviewer blocks the download.

## Rules the view enforces

- The model never receives the image. It receives structured evidence only, and
  every citation must resolve to an evidence id in the deterministic report.
- A manual zone correction blocks the review (the button disables and the panel
  explains why) until the correction is restored, because the report contract
  cannot trace a hand-edited diameter yet.
- Measurement edition (CLSI M100-Ed33) and rule edition are shown separately and
  never merged.
- A permanent disclaimer states this is decision support, not a medical device,
  and that real-photo agreement (EA 32.9%) is far from the clinical target.

## How Persona 4 exercises it

1. Start the app with keys in `.env`:
   `uvicorn bacterioscope.api.routes:app --port 8000`.
2. Open a bundled sample, English UI:
   `http://localhost:8000/?sample=plate_mixed_sir&lang=en`.
3. Confirm measurements, assign antibiotics (sample layout or manual), leave
   zones unedited.
4. Tick **Include INS and PAHO public alerts**, then press
   **Review with Nemotron**.
5. Capture the grounded status line, the citations, the rule-coverage block
   stating no expert rules are enabled, and the traceability hashes.
6. For the fallback state, run with no `NEBIUS_API_KEY` and capture the
   `fallback` status with `token_factory_unavailable`; the deterministic report
   stays complete.

Only bundled samples or non-identifiable photos may be used. Do not show the
`.env` file, terminal history with keys, or the secrets page while capturing.
