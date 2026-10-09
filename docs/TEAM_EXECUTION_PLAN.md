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

## Current work package state (2026-10-09)

- **P2 / Luis:** `feat/rules` merged to `main` via PR #1 (now 331 project-wide tests). The built-in CLSI Ed33 catalog remains empty because licensed rule content and qualified review have not been provided. Tavily's live call is not verified because no API key is configured. Confirmed directly: the supplied `Tables.zip` has no `measurements.csv` despite the Dryad README (SHA-256 recorded in `docs/UZH_LABEL_AUDIT.md`), and the one XLSX in the archive (`Overview GPT JCM.xlsx`) has mechanism counts that do not match the paper's reference counts -- stored as `source_reported_codes`, not used as ground truth, pending confirmation from Dryad/the authors.
- **Standard decision (2026-10-09):** dual-edition, explicitly labeled, not a single project-wide edition. `AnalysisResult.breakpoint_table_version` (CLSI M100-Ed33 2023) stays the measurement/classification standard; Persona 2's Ed36 phenotype/ESBL rules may run and be reported, but every rule finding and the ESBL screen carry their own `standard` string, independent of the measurement standard -- never merged into one edition field. See `docs/contracts/agent-review-v1.schema.json`.
- **P1 / Esteban:** `feat/agent` branch started. Replaced the stale education-pack `docs/contracts/agent-review-v1.schema.json` with the real AST agent-review contract (dual-edition fields, fallback/`requires_human_review` states, validated against both a grounded and a fallback example). Added `src/bacterioscope/agent/contract.py::normalize_ast_observations()` mapping pipeline classifications to `ASTObservation`, skipping UNKNOWN-category and duplicate-antibiotic disks with a recorded reason instead of raising (`ASTObservation` and `evaluate_expert_rules` reject both), plus `build_measurement_section()` for the report. 10 new tests, 331 passed project-wide. Still open: the Token Factory client itself (no Nebius credentials available in this environment to build or test against), difficulty routing, prompts, and wiring rule-tool outputs into the report end to end.
- **P3 / Daniel:** can start Docker/job scaffolding against a frozen input/output contract. Must not treat UZH/EUCAST labels as CLSI categorical truth.
- **P4 / Sebastian:** can build report states for “rules unavailable,” source-linked public alerts, and human review. Do not display draft or synthetic test rules as clinical content.
- The previous geometry-only education pack is retained as a separate draft artifact, not Luis's current P2 deliverable or the primary product route.

## Team workflow

- Branches: Esteban `feat/agent`, Luis `feat/rules`, Daniel `feat/eval`, Sebastian `feat/ui`.
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
