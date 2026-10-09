# Product Route and Business Value

## Product direction

Build **BacterioScope Lab Review Assistant**: a human-reviewed workflow that joins a plate image analysis, deterministic antimicrobial-susceptibility expert rules, and current official public-health alerts into one traceable report. The hackathon build is a research prototype. It must show which fields came from image measurement, which came from a specific standard/rule, and which came from INS/OPS search.

The first user to validate is a clinical microbiologist or laboratory quality lead who reviews disk-diffusion outputs. Adjacent users include academic AMR researchers and microbiology educators. The hackathon demo is not authorized to issue or release patient results or recommend treatment.

## User problem and value hypothesis

Lab teams repeatedly review disk-diffusion measurements, interpret organism/drug combinations under a chosen standard, apply reporting rules, and look for relevant public alerts. This work is fragmented across instrument outputs, reference documents, and websites.

The product hypothesis is: **a source-backed review workspace can make this cross-check easier to inspect and reduce time spent finding the applicable evidence, while preserving human sign-off.** Measure review time, number of findings confirmed/rejected, and usability in a small pilot before claiming time savings or clinical benefit.

## Hackathon user journey

1. Open the demo with a public/non-identifiable plate image or a synthetic fixture.
2. Review the existing pipeline's experimental measurements, S/I/R categories, version, and image-quality flags.
3. Run deterministic intrinsic-resistance, phenotype-pattern, and cascade tools against rules matching the same CLSI edition. The separate Ed36 ESBL disk screen is available only when species, exact disk identity/potency, measured zone, quality state, and MHA assay context are present; its current catalog remains draft and unavailable.
4. Search INS or OPS for a fixed broad AMR alert query; show the title, date, official source, and link.
5. Ask one Nemotron model to summarize the supplied evidence. Validate its response against Esteban's output schema and show citations beside the report.
6. A microbiologist remains responsible for interpreting and accepting any result.

If the CLSI catalog is empty, the demo must show “expert rule set unavailable” rather than implying no rule fired or faking a rule. The current pipeline's real-photo validation is low, and its S/I/R agreement against CLSI is not validated; show the demo as experimental.

## Business model hypothesis

- **Initial distribution:** free public demo and open-source research code to earn interest from microbiology labs, universities, and AMR researchers.
- **Potential buyer:** laboratory network, hospital microbiology service, or university research group that needs auditable review support.
- **Possible later revenue:** paid institutional deployment/support or a validated workflow integration, only after rights, privacy, quality-system, and regulatory work are addressed.
- **Value to test:** minutes per reviewed plate, time to locate applicable source, review corrections caught, and willingness of a lab to run a supervised pilot. Do not set a price or claim savings before those interviews.

## User acquisition

1. Ask one qualified microbiologist to review the rules and demo language before any public clinical-looking report is shown.
2. Invite 3–5 microbiologists/researchers through the team's university and lab network to complete one observed review task.
3. Use identity-matched Dryad/UZH zone measurements for offline measurement evaluation with EUCAST/source provenance intact. Exclude `Overview GPT JCM.xlsx` phenotype indicators from reference metrics until Dryad/the authors confirm whether they are model outputs or reference labels.
4. Publish a short demo video and a one-page technical note that explains sources, limitations, and how to request a supervised pilot.
5. Invite labs to contribute rule-review feedback through a specific contact/pilot form; track demo completions, source clicks, reviewer corrections, and pilot follow-ups.

Do not treat web traffic, sign-ups, or social impressions as evidence that the workflow is clinically useful.

## Hackathon win conditions

The submission should demonstrate a working pipeline from plate input through deterministic tools to a cited Nemotron report, a real Nebius Token Factory call, a live Tavily source lookup, reproducible tool tests, and a compact evaluation with honest limits. Keep the story focused on explainability and traceability. Do not claim benchmarked clinical accuracy, current CLSI coverage, or improved patient outcomes without compatible independent evidence.

## Why this scope fits current evidence

Repository documentation reports identity-matched Essential Agreement of 32.9% on a 20-image subset and documents unresolved real-photo limitations. That evidence does not support clinical result release. A constrained review prototype can still show how deterministic, versioned rules and current public sources may make an expert's review more traceable, provided the live rule catalog has appropriate authorization and human review.
