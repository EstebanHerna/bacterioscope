# CLSI Ed33 UZH derived-category reference

**Owner:** Luis (Persona 2)
**Updated:** 2026-10-12
**Status:** deterministic derivation implemented; source-zone CSV generated locally.

## Decision and interpretation

Esteban's edition split is adopted: **zone measurement/category output uses the
project's CLSI M100-Ed33 (2023) classifier; phenotype-rule candidates stay
separately scoped to Ed36 (2026)**. The project owner explicitly authorized
the Ed33 work and directed that the classifier's Ed33 categories be used as
the reference labels.

The new UZH sidecar is therefore a **derived analytical reference**: it applies
the configured project classifier to SIRscan reference diameters. It is not an
independent categorical ground truth, because the same breakpoint table is
used by the pipeline; it does not validate that table or establish clinical
performance. Original EUCAST labels stay in a separate column and are never
converted or overwritten. Do not report the sidecar as patient-outcome truth
or use it to claim CLSI categorical validation.

## Ed33 criteria checked and corrected

The Ed33 breakpoint changes that had official, publicly accessible row-level
support were corrected in `src/bacterioscope/classification/clsi.py`:

| Drug / Enterobacterales disk | CLSI Ed33 criteria | Evidence |
|---|---|---|
| Gentamicin 10 µg | S ≥18; I 15–17; R ≤14 mm | [FDA Ed33 rationale](https://www.fda.gov/drugs/development-resources/fda-rationale-recognition-decision-gentamicin-tobramycin-and-amikacin-enterobacterales-and-p) |
| Amikacin 30 µg | S ≥20; I 17–19; R ≤16 mm | [FDA Ed33 rationale](https://www.fda.gov/drugs/development-resources/fda-rationale-recognition-decision-gentamicin-tobramycin-and-amikacin-enterobacterales-and-p) |
| Cefepime 30 µg | S ≥25; SDD 19–24; R ≤18 mm | [CLSI AST meeting minutes, 2023](https://clsi.org/media/epube0cq/2024_january_ast_meeting_agenda_summary_minutes.pdf); [CLSI education table](https://clsi.org/media/3503/education-beyond-sir.pdf) |
| Piperacillin-tazobactam 100/10 µg | S ≥25; SDD 21–24; R ≤20 mm | [FDA rationale for Ed33 Enterobacterales breakpoints](https://www.fda.gov/drugs/development-resources/fda-rationale-piperacillin-tazobactam-breakpoints-enterobacterales) |

The official [CLSI Ed33 release](https://clsi.org/about/press-releases/clsi-publishes-m100-performance-standards-for-antimicrobial-susceptibility-testing-33rd-edition/)
establishes the edition and publication date. The remaining classifier rows
were not independently re-transcribed from the full licensed Ed33 table in
this task; the generated sidecar uses the values already configured in the
project classifier. Their exact organism-specific scope should be audited
before presenting results as an independently sourced benchmark.

## UZH transformation

Input is the locally extracted Dryad v20241013 `ground_truth.csv` (3,597
SIRscan zone rows) plus `uzh_phenotype_labels.csv` (225 isolate/species
records). Run:

```powershell
python scripts/derive_uzh_clsi_ed33_labels.py `
  --measurements data/processed/ground_truth.csv `
  --phenotypes data/processed/uzh_phenotype_labels.csv `
  --output data/processed/uzh_derived_clsi_ed33_labels.csv
```

The generated output file preserves each source row and includes the source EUCAST
category, exact organism join, source and CLSI disk potency, derived Ed33
category, inclusion/exclusion reason, and an explicit
`independent_ground_truth=false` field. Only Enterobacterales records,
classifier-supported antibiotic codes, numeric zones, and matching disk
contents receive a derived category. UZH CAZ is 10 µg while the mapped CLSI
ceftazidime disk is 30 µg; UZH TPZ is 30/6 µg while mapped CLSI
piperacillin-tazobactam is 100/10 µg. Those rows remain present but excluded.
The UZH EUCAST edition discrepancy (README 2022 vs paper/repository notes
v13.1, 2023) remains recorded as unresolved and does not change this Ed33
derivation.

## Evidence and use limits

- Boundary tests cover the corrected aminoglycoside thresholds and the SDD
  breakpoints; transformation tests cover source-label preservation, potencies,
  organism scope, joins, and invalid measurements.
- `tests/test_derived_clsi_reference.py` and `scripts/derive_uzh_clsi_ed33_labels.py`
  are the reproducible harness and generator.
- `tests/test_metrics.py` S/I/R metrics are not run over this sidecar. Do not
  compare the pipeline's image-measured categories against labels derived from
  reference diameters and claim independent categorical/clinical validation.
- Ed36 phenotype rules remain a different edition and a separate output.
