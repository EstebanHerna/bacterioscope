# Project Harness — BacterioScope

Durable project state for the team and coding agents. Update this file after each substantial work session.

## North star

Build **BacterioScope Lab Review Assistant**, a hackathon research/demo workflow that combines plate analysis, deterministic source-backed AST rule checks, and official public-health alerts in an explainable report. A human microbiologist remains responsible for review. The current pipeline has not been validated for clinical result release or treatment decisions.

## Current snapshot

- Repository: `EstebanHerna/bacterioscope`; branch `feat/rules`; base commit `a10efd1`.
- Existing system: Streamlit, FastAPI `/analyze`, CLI, image pipeline, HTML/JSON reports, CLSI M100-Ed33 (2023) classifier, traceability, and CI.
- Documented limits: label OCR is not usable; identity/panel selection remains manual; real-photo identity-matched EA is 32.9% on a 20-image subset; S/I/R agreement against a CLSI-compatible reference is not validated.
- UZH/Dryad provides EUCAST-provenance data, but the deposited `Overview GPT JCM.xlsx` is an unverified summary whose role may be model output. It must not be treated as evaluation ground truth until Dryad/the authors confirm it. The repository also records EUCAST 2022 in the README and breakpoint-table v13.1 (2023) in the paper; do not silently resolve this.
- New Persona 2 code: three deterministic AST rule-tool entry points, a separate zone-based ESBL screen tool, an empty Ed33 JSON catalog, and Ed36 draft catalogs with five intrinsic-resistance checks and eight disk-screen criteria. The Ed36 rules are unavailable by default; the project owner supplied the source PDF and attested authorization. Esteban still owns the pipeline edition and integration contract. Also includes a fixed-query Tavily client for `ins.gov.co` and `paho.org`, UZH CSV/workbook label extraction with source metadata, and focused tests per tool.
- No clinical rule content is enabled. The Ed36 candidate catalog is not a usable clinical rule set until reviewed. The Tavily request has only been tested with mocked HTTP; live key is not configured.
- The full Dryad archive and nested `Tables.zip` are present under `data/raw/dryad_uzh/`. Dryad's record says the ZIP contains `measurements.csv`, but the downloaded ZIP has 450 DOCX files and one actual XLSX workbook with 225 image IDs/species/phenotype indicators. The workbook is named `Overview GPT JCM.xlsx`; its mechanism counts differ from the paper's reference counts. The extractor now preserves those values as unverified `source_reported_codes` and leaves `reference_label_codes` empty. It writes `data/processed/uzh_phenotype_labels.csv`, but workbook values are not valid evaluation targets until the source role is clarified.
- Persona owners: Esteban P1 agent/integration, Luis P2 clinical tools/sources, Daniel P3 evaluation/Nebius, Sebastian P4 product/delivery.
- Previous geometry-only education examples remain draft artifacts and are not the current P2 work package or primary product route.

## Product and technical decisions

1. Keep the hackathon story focused on a traceable lab-review prototype, not mass consumer adoption or autonomous diagnosis.
2. Deterministic code owns measurements, S/I/R calculations, approved rule conditions, cascade output, and source validation. Nemotron summarizes supplied evidence only.
3. The classifier currently uses Ed33. Esteban must coordinate any edition change; never mix rule editions or label Ed33 “current.”
4. Five Ed36 intrinsic-resistance checks and eight Ed36 ESBL disk-screen criteria are in draft catalogs based on the owner-supplied, owner-authorized source. The classifiers remain on Ed33. Never combine Ed33 classifications and Ed36 rule outputs. Carbapenemase rules are not inferred from disk AST; cascades still need local protocol input.
5. Tavily searches use fixed broad AMR queries against INS or OPS domains and contain no isolate/patient/AST data. Search pages are untrusted context, not standards evidence.
6. UZH workbook indicators are unverified source-summary values and must not be used as evaluation ground truth until their role is confirmed. Any verified measurement CSV retains EUCAST provenance and cannot validate CLSI categorical agreement.
7. Public demo data must be non-identifiable; secrets remain server-side and out of logs/repository/browser bundles.
8. Preserve `POST /analyze`; agent/report integration is additive and coordinated by Esteban.

See `PRODUCT_ROUTE.md`, `AGENT_ARCHITECTURE.md`, `PERSON_2_RULE_SPEC.md`, `TEAM_EXECUTION_PLAN.md`, and `EVALUATION_HARNESS.md`.
See `UZH_LABEL_AUDIT.md` for extracted workbook counts, provenance, limits, and reproduction steps.

## Work status

### Completed in this work session

- [x] Corrected Persona 2 ownership to match Esteban's actual team split.
- [x] Added deterministic functions for intrinsic-resistance conflicts, phenotype patterns, and cascade reporting, with source/reuse/reviewer/edition gating and no S/I/R mutation.
- [x] Added an empty CLSI M100-Ed33 catalog rather than inventing clinical data.
- [x] Added Tavily client with fixed INS/OPS alert queries, domain allowlist, HTTPS recheck, server-side key, and failure behavior.
- [x] Added UZH CSV/workbook label extraction preserving raw and non-binary statuses, source asset/author/hash, image join key, and EUCAST edition caveat.
- [x] Extracted the 225-row overview workbook and verified its image join keys against all 225 original image names; 20 rows retain non-binary source statuses for review.
- [x] Ran focused P2 tests after workbook support: **18 passed** using a writable workspace temp directory.
- [x] Added a separate M100-Ed36 (2026) candidate catalog with five Appendix B intrinsic-resistance checks; retained Ed33 as the default and verified that all Ed36 rules remain disabled before review.
- [x] Added tests for Ed36 catalog selection, draft-rule fail-closed behavior, and unknown-edition rejection.
- [x] Added the Ed36 ESBL zone-screen candidate catalog and an assay-context/measurement-gated evaluator; kept the source-backed criteria draft and fail-closed.
- [x] Ran focused Persona 2 suite after the ESBL screen work: **40 passed**.
- [x] Applied the BacterioScope biomedical-review and rule-authoring skills to audit the Ed36 candidates and integration gates; this supports continued technical work but does not constitute a professional credential or clinical validation.
- [x] Compared the UZH workbook's phenotype counts with the published paper; changed workbook extraction to preserve indicators but leave reference labels empty pending source clarification.
- [x] Wrote a standalone UZH label audit for Daniel, including row counts, non-binary statuses, provenance, and evaluation limits.
- [x] Updated the P2 spec, architecture, product route, team plan, agent instructions, and relevant biomedical/rule-authoring skills to remove the previous education-only contradiction.
- [x] Marked the old `tests/agent_harness/` fixtures as education-only and not an AST/CLSI benchmark; the lab-review contract harness remains pending Esteban's schema.
- [x] Ran repository CI-style static checks and the complete test suite locally: Ruff, Bandit, and mypy passed; 313 tests passed with 92.25% coverage. `pip-audit` did not return within the local check window, so its result remains unconfirmed until CI.
- [x] Renamed the local work branch to `feat/rules`.

### Blockers / follow-up

- [ ] Esteban replaces/extends the earlier education-only report schema, maps pipeline output to `ASTObservation`, passes quality flags and the ESBL zone/assay fields, and confirms the standard edition the agent pipeline will use.
- [ ] Keep Ed36 rule catalogs unavailable until the pipeline is explicitly on Ed36 and catalog activation is approved under the team's intended-use policy. The project owner should retain the authorization record and confirm its scope for public distribution.
- [ ] Configure Tavily API key privately and run live INS/OPS smoke checks.
- [ ] Ask Dryad/the authors to clarify whether `Overview GPT JCM.xlsx` contains model outputs, routine-diagnostic labels, or another summary, and provide the documented `measurements.csv` if omitted. Until then, exclude workbook values from evaluation; reconcile EUCAST edition from README/paper.
- [ ] Daniel builds the job and reports requested metrics only when the reference standard is compatible; otherwise mark CLSI categorical metrics unavailable.
- [ ] Sebastian integrates the visible “rule catalog unavailable” state and public alert citations after Esteban freezes the report contract.

## Next concrete action

Esteban should freeze the agent input/output fields and confirm the target CLSI edition, including how it will preserve raw antimicrobial identity, disk potency, zone diameter, assay context, and measurement quality for the ESBL screen. Luis can then map the `RuleEvaluation`, ESBL screen, and `PublicAlert` outputs into the shared contract. Keep Ed36 rules unavailable unless the pipeline explicitly uses Ed36. Daniel should exclude the workbook-derived labels from reference metrics until Dryad/the authors clarify their source role.

## Change log

| Date | Change | Evidence / next step |
|---|---|---|
| 2026-10-08 | Corrected Persona 2 scope to the team assignment. Implemented rule engine/tools, Tavily client, UZH label extraction, and tests. Added workbook fallback, extracted 225 UZH records, validated image ID joins, and documented the label audit. | Focused P2 suite: 18 passed. Need CLSI source/review, Tavily key, Dryad asset clarification, and Esteban contract. |
| 2026-10-08 | Inspected project-owner-supplied CLSI M100 Ed36 PDF; added a versioned five-rule intrinsic-resistance candidate catalog, explicit Ed33/Ed36 loading, inventory and fail-closed tests. Owner attested authorized use; all candidates remain draft. | Focused P2 suite: 21 passed. Needs qualified microbiology review and Esteban's classifier-edition decision before activation. |
| 2026-10-08 | Consulted the project biomedical-review and rule-authoring skills as requested; completed a source, edition, input-contract, and validation-gap audit. | Keep coding the hackathon prototype. Do not claim clinical validation; Ed36 integration still depends on P1's edition contract. |
| 2026-10-08 | Added a draft Ed36 ESBL screening catalog with eight zone thresholds and a typed evaluator requiring exact assay context and disk identity. Added synthetic boundary, threshold transcription, incomplete-context, quality, potency, duplicate, edition, and fail-closed tests. | Focused P2 suite: 40 passed. Await Esteban's edition and input-contract decision before integration. |
| 2026-10-08 | Rechecked UZH workbook semantics against the Dryad record and JCM paper. Filename and count discrepancies mean `Overview GPT JCM.xlsx` cannot be treated as reference labels yet; extractor now stores its labels separately and leaves reference codes empty. | Re-extracted all 225 rows; workbook provenance is unverified and reference-code fields are empty. Focused P2 suite: 40 passed. Ask Dryad/authors to clarify the workbook and missing CSV before Daniel evaluates against it. |
| 2026-10-09 | Clarified that the retained education fixtures are not the lab-review AST evaluation harness. Fixed Ruff, Bandit, and mypy findings in Persona 2 code and reran the repository checks. | Ruff, Bandit, mypy passed; 313 tests passed at 92.25% coverage. Local `pip-audit` did not return; verify its CI result. |

## Resume checklist

1. Read `AGENTS.md` and this file.
2. Check `git status`, branch, and latest commit; preserve existing uncommitted work.
3. Read the relevant spec and project skill before editing.
4. Keep P1/P3/P4 ownership clear; coordinate shared API/report changes with Esteban.
5. Update this harness and the package status after substantial work.
