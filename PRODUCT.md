# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Custom web front-end (HTML/CSS/JS, no framework) served by the existing FastAPI app (`src/bacterioscope/api/`). Chosen by the team lead on 2026-10-17 over Streamlit, specifically so the interface is not a template look. Ships as the project's Docker image. The Streamlit app (`src/bacterioscope/app.py`) stays as an internal tool, not the demo surface.

## Users

- **Primary:** clinical microbiologists and lab technicians in mid- and low-complexity labs in Latin America that read Kirby-Bauer disk-diffusion plates by hand (ruler + printed CLSI table) and cannot afford automated readers (VITEK 2 / BD Phoenix class). Job: turn one photo of an incubated plate into zone diameters, S/I/R categories, and a report they review and sign.
- **Secondary:** Nebius x NVIDIA Global AI Hackathon judges (submission due 2026-10-29/30), who evaluate technological implementation, design, potential impact, and quality of the idea, mostly from a 3-minute video, screenshots, and possibly a live demo.

## Product Purpose

BacterioScope reads a single photograph of a Kirby-Bauer plate: detects each antibiotic disk, measures each inhibition zone in millimetres, classifies it against CLSI M100-Ed33 (2023), and then a Nemotron agent (via Nebius Token Factory) writes a grounded review that can only cite deterministic evidence. Success is a report a microbiologist can trust or correct quickly, that says plainly which measurements not to trust.

## Positioning

A decision-support reader that is honest about its own uncertainty: every measurement carries quality flags, and on the synthetic benchmark none of the 28 unflagged disks produced a very major or major category error, while all three that did were on disks the system had flagged. The language model cannot change a measurement, category, finding, or citation; it can only explain them, and every citation is checked. CLSI (not EUCAST) for Colombia's standard, open source, validation process published including unfavourable numbers.

## Operating Context

- Input: one photo of an incubated Mueller-Hinton plate (any camera), plate rim visible; antibiotic identity assigned by a fixed panel layout or manually (automatic label reading is not usable yet).
- Output: per-disk mm, S/SDD/I/R, quality flags, expert-rule coverage (catalog currently empty or draft, shown as unavailable, never as "no resistance"), optional INS/OPS public-health alerts (Tavily), the agent's explanation, traceability (analysis ID, image SHA-256, commit, CLSI edition), JSON download.
- Every report requires human review; nothing is released automatically.

## Capabilities and Constraints

- Measurement is CLSI M100-Ed33 (2023); expert-rule candidates are Ed36 and stay draft/disabled. The two editions are always labelled separately, never merged.
- Real-photo measurement agreement is far from the clinical target (identity-matched EA 32.9% vs ≥90%). Synthetic plates: EA 59.3%, 82.1% on unflagged disks. Must never be presented as clinically validated.
- Disks with any quality flag are excluded from expert-rule evaluation. Manual zone overrides must be traceable before they can reach the agent.
- Interface language: bilingual, Spanish and English, user-selectable (decided 2026-10-17). Hackathon materials must be available in English.
- Not a medical device; no treatment recommendations; no INVIMA/CE certification.

## Brand Commitments

- Name: BacterioScope. Motto: "La tecnología al servicio de la salud pública."
- Existing token set "Clinical Slate" (`src/bacterioscope/design/tokens.py`): S/I/R category colours are reserved for categories only, quality warnings never use the resistant red, and every category is shown with its letter, never colour alone.
- Team: Universidad de los Andes (Bogotá). No logo asset exists.

## Evidence on Hand

- `examples/synthetic/` (8 generated plates + `ground_truth.json`), `examples/real/` (real plate photos), `docs/VALIDATION_REPORT.md` (real-photo EA/MAE), `scripts/run_evaluation.py` output (synthetic benchmark; live agent stage via `.github/workflows/agent-eval.yml`).
- No customers, pilots, testimonials, or clinical studies exist. Do not imply any.

## Product Principles

1. Show uncertainty before confidence: flagged measurements are visibly distinct and explained, never hidden.
2. Deterministic evidence first, model narrative second, and the narrative always traces to evidence.
3. The microbiologist decides; the tool proposes, measures, and documents.
4. Never let an empty or disabled rule catalog read as a negative clinical finding.

## Accessibility & Inclusion

Category must never be encoded by colour alone (existing token rule). Bilingual ES/EN. Lab environments: often a shared desktop or laptop, sometimes a phone used to take the photo.
