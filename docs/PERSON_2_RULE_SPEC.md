# Persona 2: clinical rules, Tavily, and UZH labels

**Owner:** Luis. **Integration owner:** Esteban. **Current status:** deterministic rule tools and focused tests are implemented; 225 workbook-derived UZH records have been extracted, but their phenotype role is unverified and they are blocked from use as evaluation ground truth. M100-Ed36 candidate data includes five draft intrinsic-resistance checks and eight draft ESBL disk-screen criteria from the PDF the project owner supplied and said is authorized. The Ed36 catalog remains unavailable unless its exact edition and input contract are selected. A live Tavily request still needs runtime credentials. Dryad's README still disagrees with the actual table archive contents.

## Scope assigned by the team

Luis owns these four deliverables:

1. CLSI expert-rule tools for intrinsic resistance, phenotype patterns, and cascade reporting.
2. Tavily search for current public alerts from Colombia's Instituto Nacional de Salud (INS) and the Pan American Health Organization (OPS/PAHO).
3. Source-reported phenotype labels from the UZH/Dryad SIRscan dataset.
4. Focused tests for every tool and data transformation.

Esteban owns the Token Factory client, difficulty routing, agent tool calling, prompts, final report schema, and integration/review of PRs. Daniel owns Nebius evaluation infrastructure and metrics. Sebastian owns product UI, deployment, demo assets, Devpost, and feedback. Persona 2 must hand Esteban stable Python signatures and result fields; it does not edit the shared agent response schema without his coordination.

## P2-1: deterministic CLSI rule tools

Implemented in `src/bacterioscope/rules/`:

| Agent tool | Python entry point | Input | Output |
|---|---|---|---|
| Intrinsic-resistance check | `check_intrinsic_resistance` | Organism, standard edition, and `{antibiotic_code, category}` observations | Sourced findings for matching approved rules; never rewrites an S/I/R value. |
| Phenotype-pattern check | `evaluate_phenotype_rules` | Same AST input | Finding code, phenotype label, matched drug codes, and source citation for complete approved patterns. |
| Cascade reporting | `apply_cascade_reporting` | Same AST input | Sourced findings plus a list of report codes to suppress; never changes AST categories. |
| ESBL disk-screen check | `evaluate_esbl_screen` | Exact organism, standard, assay context, and `{antibiotic_code, disk_potency_ug, zone_mm, quality_accepted}` observations | Screen signal for review with exact threshold and citation; never diagnoses ESBL or changes S/I/R. |

```python
context = ESBLScreenContext(
    method="disk diffusion",
    medium="MHA",
    temperature_c=35,
    incubation_hours=17,
    atmosphere="ambient air",
    standard_disk_diffusion_procedure=True,
)
evaluate_esbl_screen(
    organism="Klebsiella pneumoniae",
    standard="CLSI M100-Ed36 2026",
    context=context,
    observations=[ZoneObservation("ceftazidime", 30, 21.0, quality_accepted=True)],
)
```

The current Ed36 catalog returns `screen_rules_unavailable`; this example documents the handoff contract, not a live positive clinical result.

The tools load the catalog matching the requested standard. The no-argument/default standard remains the pipeline classifier's CLSI M100-Ed33 (2023), whose catalog is empty. A separate CLSI M100-Ed36 (2026) catalog contains five intrinsic-resistance discordance candidates, each marked `draft`; the project owner supplied the PDF and attested authorization on 2026-10-08. The current execution gate still requires a stable ID/version, source locator and HTTPS citation, matching edition, reuse evidence, and a named qualified reviewer with review date. Exact organism and AST conditions must match. Unknown editions and draft or mismatched rules fail closed. Never send Ed36 rules outputs for an Ed33 result.

The Ed36 inventory and locators are in `docs/CLSI_ED36_RULE_INVENTORY.md`. Eight Ed36 ESBL disk-screen candidates and their deterministic evaluator now exist in `rules/clsi_m100_ed36_esbl_screen.json` and `rules/esbl_screen.py`; all candidates remain draft and unavailable. The evaluator requires exact organism, raw drug identity and potency, measured zone in millimeters, MHA disk-diffusion context, incubation conditions, ambient air, standard inoculum procedure, and an accepted measurement-quality flag. Esteban must decide how those fields enter the agent contract; Luis did not change P1 schemas. Carbapenemase status must not be inferred from disk results. Cascade profiles are institution-specific and need local stewardship input. Tests use synthetic fixtures and prove software behavior, not clinical correctness.

## P2-2: public-health alert search

Implemented in `src/bacterioscope/integrations/tavily.py` as `TavilyAlertSearch.search_amr_alerts(source)`.

- `source` is allowlisted to `ins` (`ins.gov.co`) or `ops` (`paho.org`).
- Queries are fixed public AMR-alert queries. No isolate, patient, or AST result is sent to Tavily.
- The request asks for news search, disables Tavily-generated answers/raw page content, and restricts domains server-side.
- Returned URLs are checked again against the selected HTTPS domain. Results contain title, URL, snippet, source, and publication date; returned page text is untrusted context, not AST or rule evidence.
- The key comes only from server-side `TAVILY_API_KEY`. Missing keys and request failures raise typed errors without logging or returning the key.

Esteban can call the class through his tool-calling layer and serialize `PublicAlert` fields. The module uses Python's standard library; no new runtime dependency is required. The live request still needs an API key and a smoke test in a private environment.

## P2-3: UZH/Dryad phenotype indicators and provenance

Implemented in `src/bacterioscope/phenotypes/uzh.py` and `scripts/extract_uzh_phenotypes.py`.

The extractor accepts Dryad's documented `SampleID`/`ResistanceMechanism` CSV or the overview workbook found in the uploaded archive. It preserves raw labels, normalizes only declared labels, records unknown statuses, and keeps EUCAST provenance. `Combination` remains unspecified when it appears in the CSV. The workbook is named `Overview GPT JCM.xlsx` and contains yes/no indicators for `None`, `ESBL`, `AMPC`, and `CARBAPENEMASE`; only explicit `yes` values are retained as `source_reported_codes`. Its role is not documented. The paper reports routine-diagnostic reference counts of None=75, ESBL=111, AmpC=32, carbapenemase=23, while workbook counts are None=76, ESBL=113, AmpC=33, carbapenemase=23. This, together with “GPT” in the filename, suggests a possible model-output summary but does not prove it. Therefore workbook rows have `label_provenance_status=unverified_workbook_summary` and an empty `reference_label_codes`; Daniel must not score them as ground truth until Dryad or the authors confirm their meaning. Documented CSV rows are separately marked `documented_measurement_table`. For workbook rows, `sample_id` preserves the source `Image` identifier, `source_identifier_type` says it is an image ID, and `image_join_key` trims only the final period for joining to the image archive. Output is `data/processed/uzh_phenotype_labels.csv` and records source DOI, license declaration, source asset/author, SHA-256, organism, and EUCAST provenance.

Dryad lists 225 Gram-negative isolates, 862 valid phenotypic categories, and a `Tables.zip` containing `Tables/measurements.csv`. The uploaded full archive is at `data/raw/dryad_uzh/doi_10_5061_dryad_5dv41nsfj__v20241013.zip`; its nested `Tables.zip` is `data/raw/dryad_uzh/Tables.zip`, SHA-256 `ffeb440d482be894d582efaf5b3417b6f003ce3119a43c3bb1a1bedec2b532d7`. The archive has 450 DOCX files and one actual XLSX workbook (plus an AppleDouble metadata stub), but no CSV. The workbook has 225 unique image IDs, species, and mechanism indicators. Its image IDs join one-to-one to the 225 original image names after trimming a trailing period (223 matched exactly before this punctuation normalization). Paper reference counts differ from the workbook counts, so these rows remain unverified source summaries. Dryad's README says EUCAST 2022 while the paper cites breakpoint-table version 13.1 (2023); preserve this discrepancy until reconciled.

```powershell
python scripts/extract_uzh_phenotypes.py --input data/raw/dryad_uzh/Tables.zip
```

The workbook fallback requires the project dev dependencies (`pip install -e ".[dev]"`).

## Tool-level tests and handoff

`tests/test_expert_rules.py`, `tests/test_esbl_screen.py`, `tests/test_tavily.py`, and `tests/test_uzh_phenotypes.py` cover all rule tools, Tavily request filtering and failures, UZH label mapping/provenance, Ed36 catalog selection, assay context and measurement gates, source-threshold transcription, and disabled-rule behavior. The latest focused suite passed: **40 passed**. The workbook test uses a synthetic workbook; the full source archive was processed separately as a local data run (225 records, 205 complete indicator rows, 20 partial rows). Rule fixtures are synthetic; Tavily HTTP is mocked. These checks establish transformation behavior, not clinical validity.

### Contract for Esteban

```python
ASTObservation(antibiotic_code="CRO", category="R")
```

Each rule tool takes keyword arguments `organism: str`, `standard: str`, `observations: Iterable[ASTObservation]`, and optional `rules`. Its `RuleEvaluation` has:

- `findings`: rule ID/version/type/code, optional phenotype label, matched antibiotic codes, source ID/citation/URL;
- `suppressed_antibiotics`: cascade-only report codes;
- `skipped_rule_ids`: rules disabled by status, provenance, reuse review, or standard mismatch.
- `catalog_status`: `no_rules_configured`, `rules_not_enabled_for_standard_or_review`, or `rules_available`; an empty catalog is reported as unavailable, never as a negative AST result.

Tavily returns `PublicAlert(source, title, url, snippet, published_date)`. UZH output fields are documented in the generated CSV header within the extractor.

## Execution plan and integration gates

Work in this order so rule outputs cannot be attached to the wrong organism,
drug, or standard:

1. **Freeze the shared contract with Esteban.** P1 normalizes pipeline results
   into explicit organism identity, standard edition, antibiotic codes, S/I/R
   categories, and per-disk quality flags. The current `AnalysisResult` does
   not retain the configured organism group, and the REST disk schema does not
   expose quality flags. P1 should carry these fields through the agent input
   contract. Unknown drug labels must remain unmapped; do not use fuzzy matching
   or infer an organism from the image.
2. **Gate before calling rules.** P1 calls the deterministic rule tools only
   when organism, standard, and antibiotic identities are explicit and all
   required measurements pass the agreed quality checks. Missing or flagged
   input yields a review-required state, not a rule match. Persona 2 tools never
   modify a measured zone or its S/I/R category.
3. **Resolve the CLSI edition and rule evidence.** The pipeline currently uses
   M100-Ed33 (2023); the owner supplied M100-Ed36 (2026) and attested that its
   use is authorized. The Ed36 candidate rules remain draft until a qualified
   microbiologist reviews each organism/drug mapping and P1 confirms the
   pipeline edition. The default remains Ed33 and its catalog stays empty.
   Never mix Ed33 classifications with Ed36 rule findings.
4. **Resolve UZH label provenance.** The current workbook is an unverified
   summary: its title and counts do not match the paper's routine-diagnostic
   reference counts. Ask Dryad/the authors what it represents and obtain
   `measurements.csv` if it was omitted. Until then, use the workbook only for
   source-ingestion/image-join demos, not as an evaluation target.
5. **Smoke-test Tavily privately.** Once `TAVILY_API_KEY` is configured in the
   runtime secrets, test the fixed INS and OPS queries. The report shows source,
   URL, and retrieval/publication date; search failure or no eligible result is
   an explicit unavailable state. No plate image, isolate identifier, or AST
   vector goes to Tavily.
6. **Integrate and render.** Esteban assembles pipeline results, the AST/zone
   rule outputs, and optional alerts into his final validated JSON report.
   Daniel evaluates deterministic behavior and latency/cost; workbook-derived
   values are excluded from reference metrics until their role is confirmed.
   Sebastian renders rule coverage/status and alert links in Streamlit,
   including unavailable states and provenance. The agent may explain this
   evidence bundle but cannot alter it.

### Integration edges

```text
plate image + explicit organism/panel
  -> existing CV/classifier output + standard + quality flags
  -> P1 normalization and quality gate
  -> P2 intrinsic-resistance / phenotype-pattern / cascade / ESBL screen tools
  -> P1 evidence assembly and validated agent JSON
  -> P4 Streamlit report with source and availability status

fixed INS or OPS query -> P2 Tavily adapter -> dated public alert links -> P1/P4
Dryad Tables.zip -> P2 UZH extractor -> provenance-rich phenotype CSV -> P3 evaluation
```

### Definition of done for Persona 2

- P1 accepts the input/output contract and demonstrates a round trip on a
  sample plate without losing organism, standard, quality flags, or provenance.
- Each enabled rule has exact applicability, a stable ID/version, a source
  locator, reuse evidence, and a named qualified reviewer/date. Otherwise the
  catalog remains disabled and the UI says rules are unavailable.
- The UZH extractor preserves raw workbook indicators and unknown values,
  marks the workbook provenance unverified, and leaves its reference-label
  field empty. A documented CSV or author confirmation is required before
  evaluation use; source DOI, asset, author, hash, image key, and EUCAST
  version discrepancy remain traceable.
- Tavily has a private live smoke check for both allowlisted sources, while
  unit tests continue to mock HTTP and verify failure handling.
- P1, P3, and P4 consume the same documented fields; no team member duplicates
  clinical rule logic in prompts, evaluation scripts, or UI code.

## Open gates

- Confirm with Esteban whether the integrated pipeline remains on Ed33 or will move to a licensed, reviewed edition. Do not mix editions.
- Obtain qualified microbiology review for each Ed36 candidate rule; have the project owner retain the authorization record and confirm its scope for public distribution.
- Configure `TAVILY_API_KEY` privately and run a live smoke check for INS and OPS.
- Resolve with Dryad whether `Overview GPT JCM.xlsx` contains model outputs or routine-diagnostic labels, and obtain `measurements.csv` if it was omitted. Until then, workbook values are not an evaluation reference. Reconcile the EUCAST edition note against the README and paper.
- Esteban integrates the three rule entry points and Tavily result fields into the agent tool-call schema; no response-schema changes are made by Luis in this task.
