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

Esteban owns the lab-review request/response contract, and it is not frozen yet. The existing `tests/agent_harness/` directory contains legacy education-only fixtures; it is not the AST integration contract or a batch-evaluation set. Keep those fixtures out of CLSI/AST evaluation. Add the executable lab-review contract fixtures only after Esteban publishes the versioned schema and confirms the mapping for AST observations, rule findings, public alerts, and catalog status.

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
- If a compatible CLSI reference is unavailable, mark those requested clinical categorical metrics unavailable and report measurement agreement plus rule-tool/agent metrics instead.
- Exclude the `Overview GPT JCM.xlsx` mechanism indicators from reference metrics until Dryad/the authors clarify whether they are model outputs, reference labels, or another summary. Its counts differ from the paper's routine-diagnostic counts. Any later mechanism-label analysis must use a verified source table and remain EUCAST-provenance analysis, not a CLSI validation.

For Nebius, report model ID, job configuration, sample count, p50/p95 latency, error/fallback rate, token/call cost, and a comparable routed-vs-Ultra baseline. Never include API keys in job output or CI artifacts.

## Go/no-go

- **Go for tool integration:** all focused unit tests pass and the result contract is frozen by Esteban.
- **Go for a clinical rule record:** exact source/edition, authorized reuse, qualified review/date, positive and negative tests, and integration standard all agree.
- **Go for public demo:** no private data or secrets, empty catalog is visibly unavailable, alert citations remain official and clickable, and every claim maps to a measured artifact.
- **No-go:** incompatible standards represented as concordance, synthetic clinical claims, hidden/unreviewed rules, or model-generated changes to deterministic output.
