---
name: bacterioscope-project-context
description: "Use when planning, implementing, or handing off work in the BacterioScope repository; reloads the product route, current project state, ownership, and scope boundaries."
---

# Bacterioscope Project Context

Before changing the repository:

1. Read root `AGENTS.md` and `docs/PROJECT_HARNESS.md`.
2. Read the task-specific source of truth: `docs/PRODUCT_ROUTE.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/TEAM_EXECUTION_PLAN.md`, or `docs/PERSON_2_RULE_SPEC.md` as applicable.
3. Inspect `git status`, the latest commit, and the actual code/doc for the claim being changed. `CLAUDE.md`, README marketing copy, and older plans may lag one another.

Keep the hackathon product to one education workflow for microbiology learners. The deterministic grader owns correct answers; Nemotron gives constrained, evidence-backed coaching. Treat the vision pipeline as experimental, and don't widen to hospital deployment, clinical decision support, accounts, extra organisms, or three-model routing unless the user records a scope change.

At the end of a meaningful work session, update `docs/PROJECT_HARNESS.md` with completed work, current state, blockers, and one next concrete action. Update the task owner/status in `docs/TEAM_EXECUTION_PLAN.md` in the same change. Do not mark a feature built based on a plan or an unverified screenshot.
