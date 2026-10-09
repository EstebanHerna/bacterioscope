# CLSI M100 Ed36 source inventory for Persona 2

- **Status:** implementation draft; no Ed36 rule is enabled.
- **Source supplied:** `1058374168-CLSI-M100-ED36-2026-Pantalla (1).pdf`.
- **Authorization:** the project owner attested on 2026-10-08 that use is authorized. The owner should retain the authorization record and check that its scope covers publication of derived rule data in the hackathon demo. The source PDF is not copied into this repository.

## Edition boundary

The project's classifier currently identifies its breakpoint table as **CLSI M100-Ed33 (2023)**. The supplied PDF is **CLSI M100-Ed36 (2026)**. The rule loader selects catalogs by an explicit standard string; its no-argument behavior continues to select the classifier's Ed33 edition. The Ed36 catalog is opt-in for inspection and currently contains draft entries only. The agent must never combine an Ed33 classification with an Ed36 finding.

M100 Ed36 describes interpretive tables for use with CLSI M02, M07, and M11 methods. A zone-based screening rule cannot safely run unless method, species, raw antimicrobial identity, disk potency, and measured zone are present and validated. The current `ASTObservation` contains only an antibiotic code and S/I/R category, so it cannot represent the inputs for the M100 ESBL screen.

## Draft rule candidates

The JSON catalog is `src/bacterioscope/rules/clsi_m100_ed36.json`. Each candidate is versioned, has an Appendix B source locator, and is marked `draft`. It flags an unexpected susceptible/intermediate category for review; it does not rewrite the AST category or tell the user what treatment to choose.

| Candidate ID | Organism scope | AST observation that would be flagged | Source locator |
|---|---|---|---|
| `CLSI-M100-ED36-APPB-KLEBSIELLA-AMPICILLIN` | *Klebsiella pneumoniae*, *K. oxytoca*, *K. variicola* | ampicillin reported S or I | Appendix B, B1 Enterobacterales, p. 318, grouped *Klebsiella* row |
| `CLSI-M100-ED36-APPB-CITROBACTER-FREUNDII-AMPICILLIN` | *Citrobacter freundii* | ampicillin reported S or I | Appendix B, B1 Enterobacterales, p. 318, *C. freundii* row |
| `CLSI-M100-ED36-APPB-CITROBACTER-FREUNDII-AMOXICILLIN-CLAVULANATE` | *C. freundii* | amoxicillin-clavulanate reported S or I | Appendix B, B1 Enterobacterales, p. 318, *C. freundii* row |
| `CLSI-M100-ED36-APPB-ENTEROBACTER-CLOACAE-COMPLEX-AMPICILLIN` | *Enterobacter cloacae* complex | ampicillin reported S or I | Appendix B, B1 Enterobacterales, p. 318, *E. cloacae* complex row |
| `CLSI-M100-ED36-APPB-ENTEROBACTER-CLOACAE-COMPLEX-AMOXICILLIN-CLAVULANATE` | *E. cloacae* complex | amoxicillin-clavulanate reported S or I | Appendix B, B1 Enterobacterales, p. 318, *E. cloacae* complex row |

These are a narrow initial sample, not a complete intrinsic-resistance table. A microbiologist must verify the precise organism scope, antimicrobial code mapping, and interpretation before any candidate is approved. Existing coarse group labels such as `Enterobacteriaceae` are insufficient to fire species-specific candidates.

## ESBL screen prototype

`src/bacterioscope/rules/esbl_screen.py` implements the deterministic mechanics for the Table 3A disk-diffusion screen. Its eight Ed36 criteria live in `src/bacterioscope/rules/clsi_m100_ed36_esbl_screen.json`; every criterion is `draft`, so the bundled tool returns `screen_rules_unavailable` and does not evaluate source values yet.

When a reviewed catalog is enabled, the tool requires exact species, drug code and disk potency, accepted zone measurement, disk-diffusion method, Mueller-Hinton agar, 33–37 °C, 16–18 h, ambient air, and confirmation that the standard disk-diffusion procedure was followed. It reports only a possible screen signal for review. It does not diagnose ESBL, exclude ESBL when no signal is observed, or modify S/I/R. A partial panel is identified in the result.

Ed36 notes that routine ESBL testing is unnecessary before reporting results when current breakpoints are used, and that screen results may support management or epidemiology/infection prevention. Phenotypic tests also have sensitivity and specificity limitations. The demo must describe this as an optional screen, never as an autonomous diagnosis.

## Other rules not yet implemented

- **Carbapenemase:** the discussion and Table 3B (printed pp. 158–162) distinguish possible test consideration and confirmatory assay results from routine AST interpretation. Do not infer carbapenemase from a plate result. Do not change carbapenem S/I/R based on a positive CarbaNP result. Any future tool must accept a separately produced assay result and its method, not guess from AST categories.
- **Cascade reporting:** the selective/cascade reporting section (printed pp. 3–6) says laboratories should develop a protocol with local antimicrobial-stewardship input and provides examples. Those examples are not a universal profile. Do not ship an executable cascade without the institution's own approved policy and review.

## Activation checklist

1. Esteban confirms the pipeline uses Ed36 and passes exact organism and antimicrobial identity. Do not activate this catalog while the classifier remains Ed33.
2. A qualified clinical microbiologist reviews every rule, the source locator, and the code-to-drug mapping; record reviewer name and date in the rule reference.
3. Project owner verifies that the authorization covers the intended derived content and public demo distribution.
4. Add tests for positive, negative, missing-organism, unknown-drug, wrong-edition, and flagged-measurement cases. Confirm the original S/I/R result is unchanged.
5. Keep catalog and UI status unavailable until all gates are complete.

## Citation

CLSI. *Performance Standards for Antimicrobial Susceptibility Testing*. 36th ed. CLSI supplement M100. Clinical and Laboratory Standards Institute; 2026. [CLSI M100 product page](https://clsi.org/shop/standards/m100/).
