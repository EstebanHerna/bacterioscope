# Legacy Educational Agent Fixtures

This folder is retained for the earlier geometry-only learning-agent workstream. It is not the lab-review AST contract, a CLSI rule benchmark, or a batch-evaluation set. Do not use these cases to score AST categories or clinical rule behavior. Numeric references come from constructed SVG geometry and are not expert-reviewed educational answer keys. Pipeline-flag fixtures are abstract states, not linked image tests; the cases are not an executable benchmark.

The planned lab-review evaluation requirements are in `../../docs/EVALUATION_HARNESS.md`. Esteban owns the versioned lab-review schema; its executable contract fixtures should be added only after that schema is frozen.

Run fixtures only with de-identified or synthetic educational data. Do not place real patient images or credentials here. Each case is JSONL and must state its expected deterministic grade/action and forbidden claims.

`expected_feedback_code` is the illustrative primary exercise grade or quality-only outcome. A case may also include `expected_quality_feedback_codes` so a future education harness can assert that quality cues remain separately visible when a grade is present (see `EDU-111`). `EDU-X-*` cases are structurally valid model responses with forbidden claims; JSON Schema alone cannot reject those, so any future education harness needs a semantic-policy assertion or human adjudication. `EDU-110` illustrates rejection of attempts to add or change deterministic fields. All cases are drafts and are not expert-reviewed answer keys.
