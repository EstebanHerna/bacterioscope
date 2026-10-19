# Team Execution Plan

## Roles and ownership

| Owner | Workstream | Deliverables | Dependencies |
|---|---|---|---|
| **Esteban — Persona 1 / agent core** | Token Factory client, difficulty routing, tool calling, prompts, final report JSON schema, integration, PR review. | Agent runs end-to-end; validates the report schema; handles tool/model failure. | Persona 2 tool contracts and Persona 3 evaluation results. |
| **Luis — Persona 2 / clinical tools and sources** | CLSI intrinsic-resistance, phenotype-pattern, and cascade tools; Tavily INS/OPS alerts; UZH phenotype-label extraction; tests per tool. | Versioned deterministic rule engine, source-gated catalog, fixed-query public alert client, provenance-preserving UZH label CSV, focused tests. | Esteban confirms standard/schema boundary; authorized CLSI source and qualified review for active rules; Tavily key for live smoke check; accepted Dryad dataset download. |
| **Daniel — Persona 3 / evaluation and Nebius infrastructure** | Docker image, Nebius Serverless Jobs evaluation, agreement/error metrics, routed-vs-Ultra cost/latency comparison, CI secrets. | Reproducible batch job and honest metrics report. | Stable report contract, allowed dataset, and versioned rule/tool outputs. |
| **Sebastian — Persona 4 / product and delivery** | Streamlit agent report, public deployment with keys in secrets, image gallery, architecture diagram, 3-minute video, Devpost, platform feedback. | Public review demo and truthful submission assets. | Integrated stable flow from Personas 1–3. |

## Work packages and acceptance gates

| ID | Owner | Work | Acceptance gate |
|---|---|---|---|
| `P0` | All | Confirm team accounts, API credentials, source permissions, and qualified microbiology reviewer. | Private provider calls work; reviewer named; data rights/source edition recorded. |
| `P1` | Esteban | Freeze final report JSON schema, orchestration, and safe fallback. | Tool input/output boundary documented; old `POST /analyze` remains compatible. |
| `P2` | Luis | Implement intrinsic-resistance, phenotype-pattern, and cascade tools; Tavily search; UZH labels. | Each tool has focused tests; active clinical rules have source, edition, authorized reuse, and qualified review; public alerts link only to official INS/OPS domains; UZH labels retain EUCAST/source provenance. |
| `P3` | Daniel | Create Docker and Serverless Jobs evaluation, metrics, cost/latency comparison, and CI secrets. | Reproducible run with sample sizes and standard compatibility disclosed; credentials never committed. |
| `P4` | Sebastian | Implement report experience, public demo, gallery, diagram, video, Devpost, and feedback. | One reviewer can follow result provenance and use the demo without setup friction; all claims map to code/evaluation. |
| `P5` | All | Run expert review and user tryout. | Findings and fixes recorded; no unsupported clinical efficacy claim. |
| `P6` | All | Freeze and submit. | Demo, source, video, evaluation, and Devpost tell the same story. |

## Current work package state (2026-10-11)

- **P2 / Luis:** rule tools, Tavily adapter, and UZH extractor were merged via PR #1; the Dryad extraction/evaluation reproducibility fix was merged via PR #4. Ed33 is empty because the supplied CLSI PDF and authored candidates are Ed36, not Ed33; content cannot be relabeled across editions. The supplied Ed36 candidates remain unavailable until the named qualified review, date, and candidate scope are traceably recorded. Data work is pinned to Dryad archive `v20241013` (2024-10-13); no January 2026 dataset is used. `Tables.zip` lacks the README-advertised `measurements.csv`, but per-isolate DOCX tables supply numeric EA/MAE references; reproduced result: 32.9% identity-matched EA, 6.28 mm MAE, 316 pairs across 20 annotated images. The separate XLSX (`Overview GPT JCM.xlsx`) remains unverified and excluded as phenotype ground truth pending confirmation from Dryad/the authors.
- **Tavily live call verified (2026-10-11):** a real `TAVILY_API_KEY` (team dev key, free quota) was configured locally and `search_amr_alerts()` was run live against both sources, not mocked. Result: 1 real alert from `ins.gov.co` (an INS surveillance protocol PDF) and 5 real alerts from `paho.org` (including a September 2026 regional AMR action-plan announcement), every URL correctly restricted to its source domain. The accented characters (á/é/ó) looked garbled in the Windows terminal during this check; verified separately by writing the raw strings to a UTF-8 file and reading them back -- correct UTF-8 throughout, a terminal-display artifact only, not a client bug.
- **Standard decision (2026-10-09):** dual-edition, explicitly labeled, not a single project-wide edition. `AnalysisResult.breakpoint_table_version` (CLSI M100-Ed33 2023) stays the measurement/classification standard; Persona 2's Ed36 phenotype/ESBL rules may run and be reported, but every rule finding and the ESBL screen carry their own `standard` string, independent of the measurement standard -- never merged into one edition field. See `docs/contracts/agent-review-v1.schema.json`.
- **P1 / Esteban:** `feat/agent` branch started. Replaced the stale education-pack `docs/contracts/agent-review-v1.schema.json` with the real AST agent-review contract (dual-edition fields, fallback/`requires_human_review` states, validated against both a grounded and a fallback example). Added `src/bacterioscope/agent/contract.py::normalize_ast_observations()` mapping pipeline classifications to `ASTObservation`, skipping UNKNOWN-category and duplicate-antibiotic disks with a recorded reason instead of raising (`ASTObservation` and `evaluate_expert_rules` reject both), plus `build_measurement_section()` for the report. Added `src/bacterioscope/agent/nemotron_client.py` (OpenAI-compatible Token Factory client, lazy `openai` import matching `detector.py`'s `ultralytics` pattern, no model ID hardcoded), `src/bacterioscope/agent/routing.py` (pure Nano/Super/Ultra tier selection), and `src/bacterioscope/agent/validator.py` (schema validation; the model is only ever trusted for `model_explanation` and the `evidence_ids` it cites -- every other report field comes from the deterministic base, which structurally prevents the model from altering a measurement, finding, or citation rather than detecting it after the fact). 365 passed project-wide, ruff/mypy/bandit clean.
  - **API shape confirmed directly** (`docs.tokenfactory.nebius.com`): OpenAI-compatible, base URL `https://api.tokenfactory.nebius.com/v1/`, `Authorization: Bearer <key>`.
  - **Live catalog check (2026-10-12):** authenticated `TokenFactoryClient.list_models()` against the team's local account and confirmed 25 visible model IDs, including `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b`, and `nvidia/Nemotron-3-Ultra-550b-a55b`. These exact strings were added to the local ignored `.env`; availability can differ by account.
  - A reusable `scripts/smoke_test_integrations.py` now checks account-visible model IDs and makes fixed Tavily INS/OPS searches without logging credentials. Its optional `--check-inference` flag sends one short non-clinical Nano prompt and may incur token charges. Catalog authentication succeeded; the optional completion call has not yet been run.
  - Merged to `main` via PR #3 (`e50c591`): end-to-end `review_plate()` orchestration, rule-tool calls, evidence assembly, Token Factory request, validation, and safe fallback. This branch hardens the shared boundary by carrying an explicit `rule_standard`, rejecting flagged disks from rule inputs, and invoking the ESBL evaluator only with explicit typed inputs; PR/CI status is tracked in `docs/PROJECT_HARNESS.md`.
- **P2 / Luis, continued (2026-10-12):** merged three more PRs. `#4` made Dryad extraction/ground-truth reproducible end to end. `#5` hardened the `review_plate()` boundary: `rule_standard` is now independent of `measurement.standard` (caller-overridable), disks carrying any pipeline quality flag are excluded from rule evaluation (not just UNKNOWN/duplicate), the ESBL screen now runs when the caller supplies an explicit edition and typed disk/assay observations, and optional live INS/OPS Tavily search was added to `review_plate()` with an explicit `alert_search_status` field (`not_requested`/`provided`/`available`/`no_results`/`partial`/`unavailable`). `#7` added a derived, clearly-non-independent Ed33 category sidecar for the UZH measurements (`data/processed/uzh_derived_clsi_ed33_labels.csv`, `docs/CLSI_ED33_GROUND_TRUTH_AUDIT.md`) -- every row carries `independent_ground_truth=false` and the doc explicitly forbids using it to claim categorical validation, since it applies the project's own classifier to its own reference diameters. Full suite after all three: 425 passed, ruff/mypy/bandit clean (Esteban verified independently, not just trusted the PR).
  - **Flag for Esteban/Paula:** `#5`'s companion work (really landed in the Ed33 groundtruth change) corrected four CLSI M100-Ed33 breakpoint values in `classification/clsi.py` itself -- gentamicin (S>=15 -> S>=18), amikacin (S>=17 -> S>=20), piperacillin-tazobactam (added an SDD category, S>=21 -> S>=25), cefepime (I relabeled SDD, same numeric range). Cited with FDA/CLSI sources in `docs/CLSI_ED33_GROUND_TRUTH_AUDIT.md`, but not mentioned in the commit message or PR #5 description -- found only by reading the diff directly. Does not affect the published EA/MAE pitch numbers (those are mm-based, not category-based), but is the real clinical classifier now live; Paula should confirm the four values against the actual Ed33 table before the team relies on S/I/R output in the final demo.
- **Milestone check -- Mon 12 Oct ("end-to-end agent and deterministic tool flow works on demo plates"): met.** Luis ran `review_plate()` against a synthetic demo plate with his own configured `NEBIUS_API_KEY` and got back a real `status: "grounded_report"` with a coherent, grounded `model_explanation` and two real Tavily alerts attached (`alert_search_status: "available"`). All six disks on that particular image were correctly excluded from rule evaluation by their quality flags (small/low-circularity zones) -- working as designed, not a bug, but it means that specific image is not a good choice for demonstrating a rule finding; pick cleaner demo data for that purpose. Esteban does not yet have his own `NEBIUS_API_KEY` configured locally (checked 2026-10-12); only Luis's works today.
- **P3 / evaluation (taken over by Esteban, 2026-10-17, branch `feat/eval`, PR #10):**
  - **Deterministic synthetic benchmark** (`evaluation/synthetic_benchmark.py`). The truth comes from the generator geometry (`examples/synthetic/ground_truth.json`). Results:
    - detection: 54/54 disks, 8/8 plates with an exact disk count;
    - measurement: EA 59.3%, MAE 3.04 mm;
    - unflagged disks: EA 82.1%, with 0 VME/ME on 28 disks;
    - all 3 dangerous errors fall on flagged disks (12-disk confluence).
  - **Agent benchmark** (`evaluation/agent_benchmark.py`):
    - routed vs Ultra-only, with the same alerts fed to both modes;
    - real token counts and latency per call;
    - no hardcoded prices.
  - **Runner:** `scripts/run_evaluation.py`.
  - **Docker:** the image runs the benchmark in CI.
  - **`agent-eval.yml`:** manual dispatch, using repo secrets.
  - These are synthetic-plate numbers, not clinical validation. Never present the Ed33-derived UZH sidecar as CLSI categorical ground truth.
- **P4 / UI (taken over by Esteban, 2026-10-18):** the light-box web app is served by FastAPI at `/` (`src/bacterioscope/web/`, `api/lab.py`).
  - **Reading and correction:**
    - every zone drawn on the photograph;
    - per-antibiotic CLSI rulers;
    - drag-to-correct with live category, and traced corrections that block the agent review;
    - a 3x edge loupe with an mm scale.
  - **Report:**
    - every report state (`grounded_report`/fallback, catalog status, `alert_search_status`, ESBL off);
    - INS/OPS alerts;
    - reviewer sign-off and JSON download.
  - **Usability:** bilingual ES/EN and responsive to phone width.
  - **Design process:** built through the Impeccable workflow, passed a finish review after 3 fix rounds, and is documented in `DESIGN.md`.
  - **Still open for delivery:** public deployment with keys as secrets, the architecture diagram, the 3-minute video, and Devpost.
- The previous geometry-only education pack is retained as a separate draft artifact, not Luis's current P2 deliverable or the primary product route.

## Team workflow

- Branches: Esteban `feat/agent`, Luis `feat/rules` (current integration-hardening branch: `feat/p2-integration-hardening`), Daniel `feat/eval`, Sebastian `feat/ui`.
- One pull request per owner. Each PR lists its package, owned files, tests/evidence, acceptance gate, and remaining blockers.
- Freeze shared JSON contracts with Esteban before downstream integration. Notify dependent owners when fields change.
- Never commit API keys. Use ignored local `.env` or deployment secrets; mock provider calls in standard CI.
- Keep clinical content disabled until its source, edition, reuse permission, review, and tests are recorded. Keep external public alerts separate from AST evidence.

## Calendar and release gates

| Date (2026) | Milestone |
|---|---|
| Fri 9 Oct | Confirm accounts, standard edition, qualified reviewer, and source access. |
| Sat 10 Oct | Freeze report/tool contracts and create owner branches/PRs. |
| Mon 12 Oct | End-to-end agent and deterministic tool flow works on demo plates. |
| Sun 18 Oct | Complete the report UI and reviewed source/rule demo. |
| Fri 23 Oct | Evaluation metrics, user feedback, and public deployment go/no-go. |
| Mon 26 Oct | Feature freeze; only fixes and documentation. |
| Wed 28 Oct | Final video and Devpost review. |
| Thu 29 Oct | Submit; preserve one-day buffer before the stated close. |

## If schedule slips

Protect a coherent one-plate demo, deterministic and sourced tool outputs, a real Nebius model call, safe fallback, reproducible evaluation, and truthful submission claims. Do not invent clinical rules to fill an empty catalog. Cut cosmetic features and broad expansion before weakening source/review gates.
