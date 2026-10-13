# Agent Harness

## Lab-review AST contract harness (current, implemented)

`lab_review_cases.py` is the real harness `docs/EVALUATION_HARNESS.md` section 2 asks for: it implements the seven required cases listed there against real `agent/`/`rules/` code, with only the model call itself faked. `../test_agent_harness.py` runs it in CI (`pytest tests/test_agent_harness.py -v` for the per-case breakdown). The `agent-review-v1` schema has been stable (additive-only) across every merge since PR #5, so it is frozen as of 2026-10-12 -- this harness is the fixture set that was waiting on that.

Cases REQ-5 and REQ-6 are Persona 2's own domain (Tavily domain restriction, UZH label edge cases); rather than duplicate that logic, the harness points at the exact existing tests that cover them (`tests/test_tavily.py`, `tests/test_uzh_phenotypes.py`) and reports them alongside the five it runs directly.

## Legacy Educational Agent Fixtures

The JSONL cases below (`golden-cases.jsonl`) are retained for the earlier geometry-only learning-agent workstream. They are not the lab-review AST contract, a CLSI rule benchmark, or a batch-evaluation set. Do not use these cases to score AST categories or clinical rule behavior. Numeric references come from constructed SVG geometry and are not expert-reviewed educational answer keys. Pipeline-flag fixtures are abstract states, not linked image tests; the cases are not an executable benchmark.

Run fixtures only with de-identified or synthetic educational data. Do not place real patient images or credentials here. Each case is JSONL and must state its expected deterministic grade/action and forbidden claims.

`expected_feedback_code` is the illustrative primary exercise grade or quality-only outcome. A case may also include `expected_quality_feedback_codes` so a future education harness can assert that quality cues remain separately visible when a grade is present (see `EDU-111`). `EDU-X-*` cases are structurally valid model responses with forbidden claims; JSON Schema alone cannot reject those, so any future education harness needs a semantic-policy assertion or human adjudication. `EDU-110` illustrates rejection of attempts to add or change deterministic fields. All cases are drafts and are not expert-reviewed answer keys.
