---
name: bacterioscope-evaluation
description: "Use when building or interpreting BacterioScope benchmarks, golden agent cases, user studies, or cost/latency measurements."
---

# BacterioScope Evaluation

Read `AGENTS.md`, `docs/EVALUATION_HARNESS.md`, `docs/FUENTES_DATOS.md`, `docs/LIMITACIONES.md`, and `docs/PROJECT_HARNESS.md` before selecting data or metrics.

## Evaluation rules

- State the unit of analysis, denominator, sample size, source, standard/edition, identity-matching method, split, and exclusions with each metric.
- Dryad/UZH measurement comparison may support the documented diameter analysis. Its reference categories use EUCAST 2023; do not use them as CLSI S/I/R truth or report CLSI CA/VME/ME/mE against them.
- Distinguish pipeline measurement performance from agent safety/contract performance. An agent can correctly abstain or request review without making a bad measurement accurate.
- Do not say “VME caught,” “accuracy improved,” or “clinically validated” without an independently adjudicated, compatible reference and a predeclared protocol.
- Keep education golden cases separate from held-out evaluation cases. Do not tune tolerances/prompts on held-out cases and then call them independent.
- For agent evaluation, include malformed JSON, timeout, unknown evidence IDs, attempted answer-key/measurement mutation, unsupported clinical claims, no-flag ambiguity, and a safe fallback.
- Report provider/model ID, region/endpoint if known, settings, call count, run time, p50/p95 latency, measured token cost, schema-valid rate, and fallback rate. Model cost/latency figures are tied to that run, not universal.
- For usability, report participant count, role, task, completion, timing method, and qualitative blockers. A small hackathon usability study is exploratory, not proof of learning efficacy or market demand.

Maintain the fixed cases and reporting plan in `tests/agent_harness/` and `docs/EVALUATION_HARNESS.md`. Update the project harness with what ran and what remains unverified.
