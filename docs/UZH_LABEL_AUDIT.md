# UZH phenotype-label audit

- **Audit date:** 2026-10-08
- **Owner:** Persona 2 (Luis)
- **Purpose:** document what the supplied Dryad archive can support for exploratory evaluation.

## Source and reproducibility

- Dryad DOI: `10.5061/dryad.5dv41nsfj`.
- Outer archive: `data/raw/dryad_uzh/doi_10_5061_dryad_5dv41nsfj__v20241013.zip`.
- Extracted asset: `data/raw/dryad_uzh/Tables.zip`.
- SHA-256 of `Tables.zip`: `ffeb440d482be894d582efaf5b3417b6f003ce3119a43c3bb1a1bedec2b532d7`.
- Phenotype-indicator workbook in that ZIP: `Overview GPT JCM.xlsx`, attributed in workbook metadata to Adrian Egli; the role of its yes/no values is unverified.
- Extractor: `scripts/extract_uzh_phenotypes.py`.
- Generated artifact: `data/processed/uzh_phenotype_labels.csv` (ignored/generated data; regenerate locally).

The current Dryad record describes `Tables/measurements.csv`, but the supplied
2.97 MB `Tables.zip` has no CSV. It contains 450 DOCX files, one actual XLSX
workbook, and an AppleDouble metadata stub for that workbook. The XLSX is named
`Overview GPT JCM.xlsx` and has 225 image IDs, species, and binary/unknown
indicator cells. The package/README mismatch remains open.

**Critical provenance update:** the workbook is not safe to call ground truth.
Its filename includes “GPT”, and its extracted mechanism counts are None=76,
ESBL=113, AmpC=33, carbapenemase=23. The paper reports routine-diagnostic
reference counts of None=75, ESBL=111, AmpC=32, and carbapenemase=23. The
discrepancy and filename suggest the workbook may summarize model outputs, but
do not prove its origin. Until Dryad or the authors confirm its semantics, the
extractor stores its values as `source_reported_codes`, leaves
`reference_label_codes` empty, and sets `label_provenance_status` to
`unverified_workbook_summary`. Daniel must not use it as evaluation ground
truth. The documented measurements CSV, if obtained and verified, follows a
different path and is labeled `documented_measurement_table`.

Primary sources: [Dryad dataset record](https://datadryad.org/dataset/doi:10.5061/dryad.5dv41nsfj)
and the [J Clin Microbiol article](https://doi.org/10.1128/jcm.00689-24).

## Extracted rows

- 225 records; 225 unique source IDs; organism is present for all rows.
- 205 records have all phenotype indicator fields in recognized states; 20
  records are partial because at least one source field is blank, unknown, or
  marked not assessed/not applicable/not tested.
- All 225 normalized image join keys matched original image filenames in the
  archive. The normalization trims a trailing period only; the extractor
  rejects collisions after normalization.
- Workbook author metadata is `Adrian Egli`; original indicator strings,
  source asset, source hash, isolate/image ID, and normalized join key are kept
  in the generated CSV.
- Provisional workbook counts (overlap allowed): ESBL 113, AMPC 33,
  carbapenemase 23. `NO_MECHANISM_REPORTED` occurs in 76 rows. These are
  unverified workbook values, not evaluation reference counts or population
  prevalence estimates.

The workbook also contains non-binary source values, including `not
applicable`, `not assessable`, `not tested`, `?`, and blanks. The extractor
preserves these values and marks such records partial; it does not coerce them
to negative labels.

## Permitted interpretation for this project

- Use the workbook only to demonstrate source ingestion and image-ID joins.
  Do not use it as the target for accuracy, sensitivity, specificity, or model
  selection unless its role is confirmed by Dryad/the authors.
- Preserve the dataset's EUCAST provenance. These labels do not validate CLSI
  S/I/R categories, CLSI rule behavior, or clinical decisions.
- Do not train or claim a clinical classifier from these labels without a
  documented label definition, source clarification, and appropriate review.
- Ask Dryad/the authors to confirm whether the workbook represents GPT output,
  reference annotations, or a different summary, and request the documented
  `measurements.csv` if it is missing from the deposited archive.

## Reproduction

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')
python scripts/extract_uzh_phenotypes.py --input data/raw/dryad_uzh/Tables.zip
```

The focused Persona 2 test command used for this extractor and its sibling
tools was:

```powershell
python -m pytest --basetemp .pytest-run-uzh -o addopts= tests/test_expert_rules.py tests/test_tavily.py tests/test_uzh_phenotypes.py -q
```

Result on 2026-10-08 before the ESBL screen and provenance correction: 18 passed. A live Tavily request was not part of this
test; HTTP behavior is mocked until a private runtime key is configured.
