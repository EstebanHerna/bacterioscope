# Platform feedback: Nebius Token Factory and NVIDIA Nemotron (Persona 4)

Structured feedback for the Nebius x NVIDIA hackathon platform-feedback prize,
written from building BacterioScope. Everything here is grounded in what we
observed while integrating the provider; it extends
`docs/SUBMISSION_KIT.md` section 6. Measured timings and token ratios trace to
`docs/EVALUATION_REPORT.md`.

## Summary

We used Nemotron (Nano, Super, Ultra) on Nebius Token Factory through its
OpenAI-compatible API as the narrative layer of a strictly grounded report
pipeline. The model summarizes deterministic evidence only; it never produces
measurements, categories, or citations that are not already in the evidence. The
integration was fast to stand up and the `usage` accounting made cost-aware
routing possible. Our notes below are the friction points worth fixing and the
pleasant surprises worth keeping.

## What worked well

- **OpenAI-compatible endpoint worked on the first try.** Our existing client
  code pointed at `https://api.tokenfactory.nebius.com/v1/` and ran without
  changes.
- **`usage` token counts come back on every call.** This is what let us build a
  cost-aware evaluation and compare routed vs Ultra-only output tokens (we
  measured 0.74x output tokens with the same grounded rate).
- **Ultra was not slower than Super on short reports.** Median 2.3 s vs 2.5 s in
  our run. That was a useful surprise for routing decisions: escalation did not
  cost latency on these workloads.
- **Nemotron tiers map cleanly onto a difficulty-routing design.** Nano for
  cheap checks, Super as the default report writer, Ultra on escalation.

## Friction worth fixing

- **Inconsistent model-ID casing across tiers.** We saw
  `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`,
  `nvidia/nemotron-3-super-120b-a12b`, and
  `nvidia/Nemotron-3-Ultra-550b-a55b`. Mixed casing makes a hardcoded ID easy to
  mistype, so we resolve all three from the live catalog at startup. A
  consistent casing convention, or documented stable aliases per tier, would
  remove that workaround.
- **Pricing needs a logged-in session.** The pricing page is gated behind
  login, so a CI job cannot report cost without a human copying prices by hand.
  A public price list or a prices endpoint would let automated evaluations
  report cost directly.
- **Empty final content on a thinking-style response.** With thinking enabled,
  Nano returned an empty final message for a concise report request; we had to
  disable thinking for those requests and treat an empty completion as an
  actionable error. Clearer guidance on when thinking suppresses the final
  answer would help.

## Suggestions

- Publish stable per-tier model aliases (e.g. a `nemotron-super` alias) with one
  documented casing.
- Expose pricing via a scriptable path (public page or API) so cost reporting
  can be automated in CI.
- Document the thinking-vs-final-content behaviour and a recommended setting for
  short structured outputs.

## How the platform shaped the product

The reliable `usage` accounting is the reason our evaluation can show that
difficulty routing pays off (Super by default, Ultra on escalation) rather than
just asserting it. Because the OpenAI-compatible API dropped in cleanly, we
spent our time on the grounding and validation layer, the part that actually
protects a clinical-adjacent workflow, instead of on client plumbing.

## Honest scope

This feedback is about the developer experience of the platform and models. It
is not a claim about clinical performance. BacterioScope remains decision
support with mandatory human sign-off; real-photo essential agreement is 32.9%,
far from the 90% clinical target.
