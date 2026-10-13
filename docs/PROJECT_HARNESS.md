# Project Harness — BacterioScope

Durable project state for the team and coding agents. Update this file after each substantial work session.

## North star

Build **BacterioScope Lab Review Assistant**, a hackathon research/demo workflow that combines plate analysis, deterministic source-backed AST rule checks, and official public-health alerts in an explainable report. A human microbiologist remains responsible for review. The current pipeline has not been validated for clinical result release or treatment decisions.

## Current snapshot

- Repository: `EstebanHerna/bacterioscope`; current integration base `main` at `1414305`. This work session is on `feat/p2-ed33-groundtruth`.
- Existing system: Streamlit, FastAPI `/analyze`, CLI, image pipeline, HTML/JSON reports, CLSI M100-Ed33 (2023) classifier, traceability, and CI.
- Documented limits: label OCR is not usable; identity/panel selection remains manual; real-photo identity-matched EA is 32.9% on a 20-image subset; S/I/R agreement against a CLSI-compatible reference is not validated.
- UZH/Dryad provides EUCAST-provenance data, but the deposited `Overview GPT JCM.xlsx` is an unverified summary whose role may be model output. It must not be treated as evaluation ground truth until Dryad/the authors confirm it. The repository also records EUCAST 2022 in the README and breakpoint-table v13.1 (2023) in the paper; do not silently resolve this.
- Ed33 reference derivation: the owner authorized deriving categories from the project's Ed33 classifier; the branch corrects sourced gentamicin, amikacin, cefepime, and piperacillin-tazobactam criteria and now preserves SDD. The reproducible UZH sidecar generator is `scripts/derive_uzh_clsi_ed33_labels.py`. Its labels are derived from the same classifier, not independent ground truth or clinical validation; EUCAST source categories remain unchanged. See `docs/CLSI_ED33_GROUND_TRUTH_AUDIT.md`.
- Persona 2 code: three deterministic AST rule-tool entry points, a separate zone-based ESBL screen tool, an empty Ed33 JSON catalog, and Ed36 draft catalogs with five intrinsic-resistance checks and eight disk-screen criteria. The Ed36 rules are unavailable by default; the project owner supplied the source PDF and attested authorization. Esteban owns the pipeline edition and agent schema; the merged `review_plate()` integration is being hardened on this branch. Also includes a fixed-query Tavily client for `ins.gov.co` and `paho.org`, UZH CSV/workbook label extraction with source metadata, and focused tests per tool.
- Demo edition split: `scripts/demo_agent_review.py` now defaults its expert-rule catalog selection to Ed36 explicitly while leaving image measurements/classifications on Ed33. The Ed36 intrinsic candidates remain draft and fail-closed; the phenotype-pattern and cascade catalogs remain empty, and ESBL screening still needs typed assay inputs. The general `review_plate()` API continues to default to the measurement edition unless the caller explicitly supplies `rule_standard`.
- No clinical rule content is enabled. The owner reports that clinical review is complete, but traceable reviewer identity/qualification, review date, and exact candidate scope were not supplied; the Ed36 catalog therefore remains fail-closed. The Ed33 catalog is empty because the only supplied CLSI source/candidates are Ed36 and cannot be relabeled as Ed33. A live Tavily smoke check against INS and OPS is recorded below and in `docs/TEAM_EXECUTION_PLAN.md`; provider keys remain outside the repo.
- `crop_boundary` means the segmented mask fills an unusually large share of its bounding box, a measured warning sign that the contour may follow the segmenter's search-window edge rather than the halo edge. It does not mean the uploaded photo was cropped. Keep it as a quality warning and exclude flagged disks from expert-rule inputs; the Streamlit screen explains the warning and supports manual diameter correction. Increasing the search margin globally is not a safe fix: prior real-photo checks found it could enlarge implausible contours and worsen measurements.
- This work is pinned to Dryad archive version `v20241013` (2024-10-13); no January 2026 dataset is used. The local raw archive is fully extracted. Its `Tables.zip` has 225 per-isolate DOCX measurement tables plus 225 macOS metadata sidecars and the `Overview GPT JCM.xlsx` workbook, but no `measurements.csv`. `prepare_dataset.py` parses the DOCX tables and has regenerated the ignored `data/processed/ground_truth.csv` with 3,597 numeric rows for EA/MAE. The workbook's phenotype indicators differ from the paper's reference counts, so the extractor preserves them as unverified `source_reported_codes` and leaves `reference_label_codes` empty. `scripts/download_data.py` now detects incomplete outer and nested extraction rather than treating an existing ZIP as proof of completion.
- Persona owners: Esteban P1 agent/integration, Luis P2 clinical tools/sources, Daniel P3 evaluation/Nebius, Sebastian P4 product/delivery.
- Previous geometry-only education examples remain draft artifacts and are not the current P2 work package or primary product route.

## Product and technical decisions

1. Keep the hackathon story focused on a traceable lab-review prototype, not mass consumer adoption or autonomous diagnosis.
2. Deterministic code owns measurements, S/I/R calculations, approved rule conditions, cascade output, and source validation. Nemotron summarizes supplied evidence only. `grounded_report` means the response passed JSON/schema checks and its listed evidence IDs are allowed; it does not prove that free-text claims are entailed or that image measurements are accurate.
3. The classifier currently uses Ed33. Esteban must coordinate any edition change; never mix rule editions or label Ed33 “current.”
4. Five Ed36 intrinsic-resistance checks and eight Ed36 ESBL disk-screen criteria are in draft catalogs based on the owner-supplied source. The classifiers remain on Ed33. The Ed33 rule catalog is empty because Ed36 content cannot be relabeled as Ed33. Never combine Ed33 classifications and Ed36 rule outputs. Carbapenemase rules are not inferred from disk AST; cascades still need local protocol input.
5. Tavily searches use fixed broad AMR queries against INS or OPS domains and contain no isolate/patient/AST data. Search pages are untrusted context, not standards evidence.
6. UZH workbook indicators are unverified source-summary values and must not be used as evaluation ground truth until their role is confirmed. Any verified measurement CSV retains EUCAST provenance and cannot validate CLSI categorical agreement.
7. The Ed33 UZH sidecar is an analytical derivation from reference diameters and the configured classifier. Preserve SDD, exclude wrong disk potencies and unsupported organisms, and never present the sidecar as independent clinical or categorical validation.
8. Public demo data must be non-identifiable; secrets remain server-side and out of logs/repository/browser bundles.
9. Preserve `POST /analyze`; agent/report integration is additive and coordinated by Esteban.

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
- [x] Fast-forwarded the P2 branch to current `main` and fixed resumable Dryad ZIP extraction, with focused coverage for partial outer/nested archives.
- [x] Reproduced measurement ground truth and EA/MAE from only the Oct 2024 archive's per-isolate DOCX tables; the identity-matched result is 32.9% EA, 6.28 mm MAE, 316 pairs across 20 annotated images. The missing advertised CSV is not required for these metrics; the phenotype workbook remains excluded as reference truth.
- [x] Filtered AppleDouble image sidecars and fixed punctuation-tolerant isolate/image matching so the pinned archive yields all 3,597 plausible reference rows across 225 images.
- [x] Reviewed Esteban's merged agent orchestration (`e50c591`): it calls the three expert-rule tools and accepts optional alert results, but had not wired ESBL evaluation or a rule-edition field separate from measurement edition.
- [x] Corrected sourced Ed33 gentamicin, amikacin, cefepime, and piperacillin-tazobactam criteria; added SDD support through classification/report display, plus tests and a provenance-preserving UZH derivation harness. Committed sidecar: 3,597 rows; 2,083 derived analytical labels. Focused test set: 143 passed. Labels are explicitly marked derived, not independent ground truth.

### Integration hardening in PR #5 (`feat/p2-integration-hardening`)

- Separate `rule_standard` from `measurement.standard` in the report and allow the caller to opt into a distinct rule edition.
- Invoke the ESBL evaluator only when the caller supplies an explicit ESBL edition and typed assay/disk inputs; the draft Ed36 catalog still returns unavailable.
- Exclude any disk with a pipeline quality flag from the expert-rule observations, and preserve the exclusion reason in the report.
- Let the report caller opt into fixed INS/OPS Tavily queries; report `available`, `no_results`, `partial`, or `unavailable` without stopping plate review.
- Focused integration suite passed: **94 passed**; Ruff, compilation, schema parsing, and whitespace checks passed. CI and CodeQL passed on merged commit `c8d5475`.

### Provider and full-flow verification (2026-10-12)

- [x] Read the live Token Factory catalog with the configured local credential. The account exposed 25 model IDs, including Nemotron Nano (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`), Super (`nvidia/nemotron-3-super-120b-a12b`), and Ultra (`nvidia/Nemotron-3-Ultra-550b-a55b`). These IDs are stored only in the ignored local `.env`; account availability may differ.
- [x] Added `scripts/smoke_test_integrations.py` to load `.env`, verify model catalog/tier IDs, and query only the fixed public INS/OPS alert searches. One short Nano inference is opt-in (`--check-inference`).
- [x] Fixed Nano's empty-final-text response by disabling Nemotron thinking for concise report requests; empty completions now raise an actionable request error instead of reaching the report validator as `""`.
- [x] Fixed `reclassify_with_labels()` to preserve all `AnalysisResult` traceability/edition metadata and reject mismatched disk/zone/panel lengths. Added focused regression tests.
- [x] Added `scripts/demo_agent_review.py` for pipeline → manual synthetic-panel labels → rule tools → optional INS/OPS search → Nemotron → schema-validated report. No patient or institutional image data is used in the default path.
- [x] Live provider smoke passed: 25 model IDs visible, all three configured tier IDs matched, Nano/Super/Ultra each returned final text on a minimal non-clinical request, and the full demo returned `grounded_report`; Tavily returned one eligible official INS and one OPS result.
- [x] The default synthetic demo detected 6/6 disks, but every measured disk had at least one quality flag and was excluded from rule evaluation. A separate pass over all eight generated synthetic fixtures found every detected disk flagged (the uneven-light fixture detected only 2/6). The report correctly keeps human review required; these images are not suitable evidence of measurement performance.
- [x] Full local test suite passed: **428 passed**, **92.35% coverage**; focused agent/pipeline tests: **37 passed**; Ruff passed.
- [x] Added a local Streamlit agent-review panel on this branch. It calls `review_plate()` only after explicit opt-in, keeps Ed33 measurement and selected rule edition separate, renders validated report sections and JSON download, and clears stale reports when the image changes. Streamlit UI code remains Persona 4-owned; no shared report schema changed.
- [x] The UI requires an exact user-selected species and confirmation that the sample is synthetic/non-identifiable before calling Nebius. It states that the image file is not sent but the structured context, including the image hash, is. Tavily remains an optional fixed INS/OPS query.
- [x] `crop_boundary` is shown as `window edge`, with an explanation that the algorithm's search region may have truncated the measured contour; it does not mean the source photograph is cropped. Any edited zone blocks report generation because report v1 cannot trace manual corrections.
- [x] Manually compared the `plate_mixed_sir.png` pipeline output with its generated geometry annotation: meropenem measured 21.8 mm (I) versus generated 23.9 mm (S); ciprofloxacin 21.1 mm (R) versus generated 22.8 mm (I). Pixel rounding accounts for the slight difference from the nominal 24/23 mm generator inputs. Both carry `crop_boundary` and remain excluded. The outer halo edges are diffuse in the raw synthetic image; its labels come from the same generator and are not independent ground truth.

### Synthetic demo corrections (2026-10-12)

- [x] Fixed the synthetic plate generators' intensity polarity to match the current segmenter's `THRESH_BINARY_INV` dark-zone expectation; regenerated the eight scenario plates, their annotated references, and the pipeline demo frames/GIF. This makes these fixtures exercise the implementation and does not validate the polarity against clinical photos.
- [x] Fixed the clockwise panel sort around 12 o'clock for disk centers slightly left of the inferred center (a one-pixel Hough offset had moved that disk to the end). Strengthened the wrap regression test and changed `demo_agent_review.py` to use `PanelManager.assign()` instead of its own duplicate angle sort.
- [x] Re-ran the full local pipeline on the eight generated fixtures: detected and assigned 54/54 disks. Twenty-six measurements retained quality flags (10 on the crowded 12-disk plate, six on the deliberately large-zone plate, and 10 across other scenarios); those records must remain excluded from expert-rule evaluation.
- [x] Synthetic geometry-only MAE after these corrections is 3.69 mm across 54 generated pairs, but it is a generator-specific smoke metric, not a performance claim. The existing identity-matched real-photo result remains 32.9% EA / 6.28 mm MAE; do not tune thresholds against synthetic fixtures or weaken quality gates to improve this demo score.
- [x] The Codex execution environment could not connect to Token Factory, but the owner supplied PowerShell output confirming 25 models visible, all three configured Nemotron IDs present, Nano inference successful, and full agent reports successful with and without Tavily. The first pasted report used image SHA-256 `172bb690…`; the second used `e09e91c6…`, matching the regenerated fixture currently in this workspace. Thus the different measurements came from different image bytes despite the same basename; the corrected report retains two `crop_boundary` exclusions.
- [x] Made the demo CLI print the resolved image path and SHA-256, so stale/copied fixtures with the same basename are distinguishable. Tightened the Nemotron instructions to separate deterministic S/I/R classifications from expert-rule matches and to describe empty rule catalogs as unavailable. Added a deterministic validator guard that rejects “no rules matched” claims when every rule catalog is empty; such a response falls back to the deterministic report. `grounded_report` still is not full semantic or clinical validation.
- [x] Repeated the live Nemotron demo after adding a required exact sentence for empty rule catalogs. The model then returned a consistent explanation and `grounded_report`; the CLI exited 0 with the same image SHA and measurements. `--skip-alerts` was used, so this call did not search Tavily. Agent/validator tests: 27 passed; Ruff and `git diff --check` passed.
- [ ] Daniel should rerun the official real-photo evaluation after integrating these changes. Sebastian should exercise the Streamlit report panel, then refresh screenshots/demo using the regenerated fixtures and preserve their quality warnings.

### Blockers / follow-up

- [x] Focused integration-hardening suite passed: **94 passed**; Ruff, Python compilation, JSON schema parsing, and `git diff --check` passed. CI and CodeQL passed on commit `33c2d3b`. The caller/UI must provide the chosen rule edition and, for ESBL, exact disk identity/potency, zone, quality acceptance, and assay context.
- [ ] Keep Ed36 rules unavailable until a named qualified reviewer, review date, and exact candidate scope are recorded. Owner permission to use a source is separate from clinical review and does not fill those fields.
- [ ] Put `TAVILY_API_KEY` in the hosted server-side secret store and have the UI opt into INS/OPS search. The real INS/OPS smoke check already passed on 2026-10-11.
- [ ] Ask Dryad/the authors to clarify whether `Overview GPT JCM.xlsx` contains model outputs, routine-diagnostic labels, or another summary. Request the advertised `measurements.csv` only to reconcile package contents; zone EA/MAE uses the v20241013 DOCX tables. Continue excluding workbook phenotype values from evaluation and reconcile EUCAST edition from README/paper.
- [ ] Daniel builds the job and reports requested metrics only when the reference standard is compatible; otherwise mark CLSI categorical metrics unavailable.
- [ ] Independently verify every remaining classifier drug/organism breakpoint row against the full authorized Ed33 source before presenting the sidecar as a separately sourced categorical benchmark. Ed33 CA/VME/ME/mE remain unavailable as claims of independent or clinical validation.
- [ ] Sebastian reviews the local report panel against the current report contract, then continues public deployment, gallery, architecture diagram, video, and Devpost deliverables.

## Next concrete action

Install the optional UI and agent dependencies with `pip install -e ".[ui,agent]"`, then run `streamlit run src/bacterioscope/app.py` and use only a synthetic or non-identifiable image to review the new report panel. Select the exact species, keep measurements unedited, choose the rule edition separately, and opt into Nebius; select INS/OPS search only if desired. Inspect the per-disk exclusion reasons, rule-catalog state, and alert status. For a no-Tavily CLI repeat, use `python scripts/demo_agent_review.py --skip-alerts`. Synthetic fixtures still carry quality flags; preserve exclusions and never present synthetic scores as clinical validation. Daniel should rerun real-photo metrics; Sebastian should continue public deployment and submission work.

## Change log

| Date | Change | Evidence / next step |
|---|---|---|
| 2026-10-08 | Corrected Persona 2 scope to the team assignment. Implemented rule engine/tools, Tavily client, UZH label extraction, and tests. Added workbook fallback, extracted 225 UZH records, validated image ID joins, and documented the label audit. | Focused P2 suite: 18 passed. Need CLSI source/review, Tavily key, Dryad asset clarification, and Esteban contract. |
| 2026-10-08 | Inspected project-owner-supplied CLSI M100 Ed36 PDF; added a versioned five-rule intrinsic-resistance candidate catalog, explicit Ed33/Ed36 loading, inventory and fail-closed tests. Owner attested authorized use; all candidates remain draft. | Focused P2 suite: 21 passed. Needs qualified microbiology review and Esteban's classifier-edition decision before activation. |
| 2026-10-08 | Consulted the project biomedical-review and rule-authoring skills as requested; completed a source, edition, input-contract, and validation-gap audit. | Keep coding the hackathon prototype. Do not claim clinical validation; Ed36 integration still depends on P1's edition contract. |
| 2026-10-08 | Added a draft Ed36 ESBL screening catalog with eight zone thresholds and a typed evaluator requiring exact assay context and disk identity. Added synthetic boundary, threshold transcription, incomplete-context, quality, potency, duplicate, edition, and fail-closed tests. | Focused P2 suite: 40 passed. Await Esteban's edition and input-contract decision before integration. |
| 2026-10-08 | Rechecked UZH workbook semantics against the Dryad record and JCM paper. Filename and count discrepancies mean `Overview GPT JCM.xlsx` cannot be treated as reference labels yet; extractor now stores its labels separately and leaves reference codes empty. | Re-extracted all 225 rows; workbook provenance is unverified and reference-code fields are empty. Focused P2 suite: 40 passed. Ask Dryad/authors to clarify the workbook and missing CSV before Daniel evaluates against it. |
| 2026-10-09 | Clarified that the retained education fixtures are not the lab-review AST evaluation harness. Fixed Ruff, Bandit, and mypy findings in Persona 2 code and reran the repository checks. | Ruff, Bandit, mypy passed; 313 tests passed at 92.25% coverage. Local `pip-audit` did not return; verify its CI result. |
| 2026-10-11 | Fixed recursive Dryad archive discovery and resumable extraction; excluded the outer archive from nested extraction; ignored macOS sidecars and normalized isolate/image punctuation. Rebuilt ground truth and reran the documented 80-image measurement evaluation using only archive `v20241013`. | 3,597 numeric references across 225 images; 46 focused P2/data-prep tests passed; Ruff passed. Reproduced 32.9% identity-matched EA, 6.28 mm MAE, r=0.193 (316 pairs), and 38.1% rank-order EA / 3.93 mm MAE (944 pairs). |
| 2026-10-12 | Applied Esteban's edition split: Ed33 for classifier-derived categories and Ed36 for phenotype-rule candidates. Corrected sourced Ed33 rows, added SDD support, tests, and committed the provenance-preserving UZH sidecar (3,597 rows; 2,083 derived). | Focused tests: 143 passed; Ruff and compileall passed. Labels are derived from reference zones using the project's classifier, not independent validation. EUCAST categories and disk mismatches are preserved/explicitly excluded. |
| 2026-10-12 | Hardened live Nemotron requests against empty final content; preserved analysis metadata during panel reclassification; added a local complete agent-review CLI harness and exercised the provider path with synthetic data and public INS/OPS alerts. | Nano, model catalog, Tavily and report-schema path passed; report correctly excluded all six synthetic measurements due to quality flags. All eight generated fixtures currently flag every detected disk. Full suite: 428 passed, 92.35% coverage; Ruff passed. Next: fix or replace the synthetic demo inputs and add the report panel through P4. |
| 2026-10-12 | Corrected synthetic zone polarity and the panel-angle wrap; removed duplicate label-ordering code from the CLI harness; regenerated committed synthetic plates and pipeline GIF/frames. | Full pipeline found 54/54 disks and assigned labels; 26/54 still carry quality flags, concentrated in the crowded 12-disk and deliberately large-zone fixtures. Synthetic geometry MAE 3.69 mm is only a smoke metric. Preserve quality exclusions; rerun the official real-photo evaluation after integration. |
| 2026-10-12 | Made the demo select Ed36 expert-rule candidates explicitly while keeping Ed33 measurements; improved catalog-status narration and guarded against model claims that disabled catalogs are empty. Explained `crop_boundary` in the console and Streamlit without weakening the quality gate. | 28 validator/orchestrator tests passed; Ruff and diff checks passed. Full synthetic Nemotron demo returned `grounded_report`; intrinsic candidates correctly remained disabled, and two flagged measurements stayed excluded. |
| 2026-10-13 | Added the local Streamlit report flow to make `grounded_report` visible, render measurement/rule editions separately, show catalog and alert coverage, and download JSON. Added explicit non-identifiable-data consent; the agent receives structured context (including image hash), never the image file. Manual zone edits block agent submission until the report contract can trace them. | Scoped Ruff and compileall passed. Focused suite: 65 passed; 415 tests passed excluding `test_api.py`, and the 4 tempfile tests passed separately after redirecting temp files inside the workspace. Full suite stalled at `test_api.py`; the Streamlit extra is absent in this venv, so UI runtime review remains. Manual fixture review found fuzzy, uncertain outer edges for the two flagged disks; generated annotations are not independent truth. Meropenem annotation is 23.9 mm and ciprofloxacin 22.8 mm after pixel rounding. |

## Resume checklist

1. Read `AGENTS.md` and this file.
2. Check `git status`, branch, and latest commit; preserve existing uncommitted work.
3. Read the relevant spec and project skill before editing.
4. Keep P1/P3/P4 ownership clear; coordinate shared API/report changes with Esteban.
5. Update this harness and the package status after substantial work.
