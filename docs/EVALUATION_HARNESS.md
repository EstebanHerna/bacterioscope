# Agent and Evaluation Harness

## Purpose

Measure tool correctness, agent grounding, runtime behavior, and AST measurement agreement without turning technical metrics into unsupported clinical claims. Persona 2 owns unit tests for its tools. Daniel (Persona 3) owns batch evaluation, Nebius Serverless Jobs, error metrics, cost, and latency.

## Evaluation layers

### 1. Persona 2 tool checks

- Intrinsic-resistance tool: exact organism, drug, standard, approved-status, and source/reuse/reviewer gates.
- Phenotype tool: all conditions present; incomplete or out-of-scope patterns do not fire.
- Cascade tool: returns only explicit source-backed suppressions and never mutates S/I/R categories.
- Tavily: fixed query, official domain filter, HTTPS result validation, malformed response/failure behavior, and no-secret leakage.
- UZH extraction: source strings preserved, documented aliases normalized, unknown values retained, and EUCAST provenance never rewritten as CLSI. The current `Overview GPT JCM.xlsx` indicators are unverified and have empty reference-label fields.

Run focused checks locally with:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m pytest -q -o addopts='' --basetemp .pytest-tmp tests/test_expert_rules.py tests/test_esbl_screen.py tests/test_tavily.py tests/test_uzh_phenotypes.py
```

These unit tests prove code behavior only. Synthetic rule fixtures are not clinical guidance; mocked Tavily responses are not proof of live service availability; synthetic UZH rows are not a downloaded dataset.

### 2. Agent/tool contract harness

**Implemented (2026-10-12).** Esteban's `agent-review-v1` schema has been stable (additive-only fields) across every merge since PR #5 and is now frozen. `tests/agent_harness/lab_review_cases.py` implements the seven required cases below against real `agent/`/`rules/` code (only the model call is faked); `tests/test_agent_harness.py` runs it in CI. Run it directly for a per-case breakdown:

```powershell
python -m pytest tests/test_agent_harness.py -v
```

The pre-existing `tests/agent_harness/golden-cases.jsonl` fixtures remain legacy education-only content; they are not this contract and stay out of CLSI/AST evaluation.

Required cases:

1. Valid rule finding with supported source ID and matching standard.
2. Draft/unlicensed/unreviewed rule is skipped and cannot be presented as a clinical finding.
3. Model attempts to alter a measurement, S/I/R, rule outcome, cascade suppression, or citation.
4. Missing rule catalog and Tavily timeout use safe deterministic fallback states.
5. Tavily result from outside the allowed official domain is rejected.
6. Empty UZH label, unknown label, and `Combination` preserve source meaning without inference; workbook rows remain `unverified_workbook_summary` and do not populate `reference_label_codes`.
7. Malformed model JSON, timeout, unknown evidence ID, and unsupported claims are rejected.

When the lab-review harness is added, its output should report total cases, pass rate, failure class, fallback rate, and evidence IDs used. Until then, Persona 2 unit tests cover deterministic tool behavior; they do not establish agent-contract correctness.

### 3. Batch evaluation (Persona 3)

Report sample counts, exact source and version, organism/drug coverage, exclusions, and confidence intervals where sample size permits.

- Measurement agreement may use identity-matched UZH/SIRscan zone diameters from the per-isolate DOCX tables with source/license provenance and an explicit note that the images were captured in a controlled SIRscan workflow.
- Do not calculate or describe CLSI CA, VME, ME, or mE using UZH categories unless the predictions and reference categories share the same compatible CLSI edition and criteria. Existing UZH labels have EUCAST provenance; current classifier code is CLSI Ed33.
- The Ed33 sidecar generator applies the configured classifier to UZH/SIRscan reference diameters; it preserves EUCAST labels and excludes incompatible disk contents and unsupported organisms. These categories derive from the same classifier and therefore are not an independent benchmark or clinical truth. Preserve `SDD`; see `docs/CLSI_ED33_GROUND_TRUTH_AUDIT.md`.
- Current categorical agreement/error metrics and 3×3 confusion matrix accept only S/I/R and now reject SDD explicitly; Daniel must define a four-category treatment before reporting metrics for SDD-bearing data.
- If a compatible CLSI reference is unavailable, mark those requested clinical categorical metrics unavailable and report measurement agreement plus rule-tool/agent metrics instead.
- Exclude the `Overview GPT JCM.xlsx` mechanism indicators from reference metrics until Dryad/the authors clarify whether they are model outputs, reference labels, or another summary. Its counts differ from the paper's routine-diagnostic counts. Any later mechanism-label analysis must use a verified source table and remain EUCAST-provenance analysis, not a CLSI validation.

For Nebius, report model ID, job configuration, sample count, p50/p95 latency, error/fallback rate, token/call cost, and a comparable routed-vs-Ultra baseline. Never include API keys in job output or CI artifacts.

## Go/no-go

- **Go for tool integration: met (2026-10-12).** All focused unit tests pass, the result contract is frozen, and `tests/test_agent_harness.py` (all 7 required cases) is green -- Daniel can build Docker/Serverless Jobs scaffolding against `review_plate()` and `agent-review-v1` now without waiting further on Esteban.
- **Go for a clinical rule record:** exact source/edition, authorized reuse, qualified review/date, positive and negative tests, and integration standard all agree.
- **Go for public demo:** no private data or secrets, empty catalog is visibly unavailable, alert citations remain official and clickable, and every claim maps to a measured artifact.
- **No-go:** incompatible standards represented as concordance, synthetic clinical claims, hidden/unreviewed rules, or model-generated changes to deterministic output.
