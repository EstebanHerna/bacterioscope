# BacterioScope evaluation report

Generated 2026-10-19 15:15 UTC from commit `11d8f1a` by `scripts/run_evaluation.py`.

## Key findings

- **Errors concentrate on one plate:** 11 of 16 category disagreements, and 3 of 3 very major/major ones, are on `plate_12disk_panel.png`, where neighbouring zones merge.
- **Detection:** 54/54 drawn disks found; exact disk count on 8/8 plates.
- **Measurement:** 59.3% of zones within ±2 mm (MAE 3.04 mm); the pipeline underestimates by 1.59 mm on average.
- **Flags work as a safety signal:** 0 very major/major errors on 28 unflagged disks, 3 on 26 flagged ones. Flagged disks are excluded from expert rules by design.
- **Grounded reports:** 8/8 `routed`; 8/8 `ultra_only`. Each narrative passed schema validation and cites only evidence that exists in the deterministic report.
- **Routed vs Ultra:** routed calls by tier: super 8. It produced 0.74x the completion tokens of Ultra at 1.12x its median latency, with the same grounded rate.
- **Why routing never escalated:** the report call runs on Super and escalates to Ultra only on expert-rule findings or a positive ESBL screen. No expert rules are enabled yet and the screen needs disk potency, so no plate qualified.

## Stage 1 -- vision pipeline vs drawn geometry (8 synthetic plates)

No network. Categories on both sides come from the same CLSI M100-Ed33 classifier, so every disagreement is a measurement error. SDD is treated like I.

| Metric | Value | ISO 20776-2 target |
|---|---|---|
| Disk recall (matched / drawn) | 100.0% (54/54) | - |
| Disk precision (matched / detections) | 100.0% | - |
| Essential agreement (±2 mm) | 59.3% | >= 90% |
| MAE / bias | 3.04 mm / -1.59 mm | - |
| EA unflagged vs flagged | 82.1% vs 34.6% (48.1% flagged) | - |
| Categorical agreement | 70.4% (n=54) | >= 90% |
| Very major errors (R read as S) | 1 (4.3% of R) | <= 1.5% |
| Major errors (S read as R) | 2 (11.1% of S) | <= 3% |
| Minor errors (involving I/SDD) | 13 (24.1%) | <= 10% |

Reference frame: the generator draws the rim at 252 px, which the pipeline calibrates as 90 mm. Against the scenario table's nominal values instead, EA is 57.4%: those values assume a scale ~6% larger.

### Per plate

| Plate | Disks found | Flagged | EA ±2 mm | MAE | Bias | CA |
|---|---|---|---|---|---|---|
| plate_pan_susceptible.png | 6/6 | 4 | 83.3% | 0.94 mm | -0.94 mm | 83.3% |
| plate_mdr_organism.png | 6/6 | 0 | 66.7% | 1.44 mm | 1.44 mm | 100.0% |
| plate_mixed_sir.png | 6/6 | 2 | 100.0% | 0.53 mm | 0.19 mm | 83.3% |
| plate_12disk_panel.png | 12/12 | 10 | 16.7% | 8.13 mm | -6.15 mm | 8.3% |
| plate_carbapenem_resistant.png | 6/6 | 0 | 66.7% | 1.68 mm | 1.68 mm | 100.0% |
| plate_uneven_light.png | 6/6 | 2 | 83.3% | 0.83 mm | -0.28 mm | 50.0% |
| plate_large_zones.png | 6/6 | 6 | 16.7% | 4.52 mm | -4.52 mm | 100.0% |
| plate_esbl_like.png | 6/6 | 2 | 83.3% | 1.15 mm | 0.39 mm | 100.0% |

### Every category disagreement

| Error | Plate | Antibiotic | Reference | Measured | Flags |
|---|---|---|---|---|---|
| very major | plate_12disk_panel.png | ampicillin | 9.3 mm R | 17.9 mm S | low_circularity |
| major | plate_12disk_panel.png | meropenem | 23.2 mm S | 12.8 mm R | low_circularity |
| major | plate_12disk_panel.png | cefepime | 25.4 mm S | 10.6 mm R | low_circularity |
| minor | plate_12disk_panel.png | ciprofloxacin | 22.5 mm I | 12.9 mm R | low_circularity |
| minor | plate_12disk_panel.png | ceftriaxone | 21.4 mm I | 11.0 mm R | low_circularity |
| minor | plate_12disk_panel.png | imipenem | 20.4 mm I | 11.5 mm R | low_circularity |
| minor | plate_12disk_panel.png | gentamicin | 16.8 mm I | 12.5 mm R | low_circularity |
| minor | plate_12disk_panel.png | ertapenem | 21.4 mm I | 8.2 mm R | low_circularity |
| minor | plate_12disk_panel.png | amikacin | 17.9 mm I | 9.9 mm R | low_circularity |
| minor | plate_12disk_panel.png | levofloxacin | 12.9 mm R | 14.8 mm I | none |
| minor | plate_12disk_panel.png | trimethoprim-sulfamethoxazole | 15.0 mm I | 16.4 mm S | none |
| minor | plate_mixed_sir.png | meropenem | 22.5 mm S | 21.8 mm I | crop_boundary |
| minor | plate_pan_susceptible.png | ciprofloxacin | 26.1 mm S | 23.6 mm I | crop_boundary |
| minor | plate_uneven_light.png | meropenem | 24.3 mm S | 21.3 mm I | low_circularity |
| minor | plate_uneven_light.png | ampicillin | 12.9 mm R | 13.6 mm I | none |
| minor | plate_uneven_light.png | ceftriaxone | 22.5 mm S | 22.2 mm I | crop_boundary |

## Stage 2 -- live agent on Nebius Token Factory

Run 2026-10-19 15:07 UTC at commit `11d8f1a` ([workflow run](https://github.com/EstebanHerna/bacterioscope/actions/runs/39275126717)). Each synthetic plate reviewed once per mode with organism *Escherichia coli*; both modes receive the same pre-fetched public alerts (ins 1 alerts, ops 5 alerts).

Models resolved from the live catalog: nano `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, super `nvidia/nemotron-3-super-120b-a12b`, ultra `nvidia/Nemotron-3-Ultra-550b-a55b`.

| Mode | Grounded | Latency p50 / p95 | Prompt / completion tokens | Calls by tier | Cost per plate |
|---|---|---|---|---|---|
| routed | 8/8 | 2.55 s / 2.70 s | 34565 / 2770 | super 8 | not priced |
| ultra_only | 8/8 | 2.27 s / 3.08 s | 34565 / 3733 | ultra 8 | not priced |

Fallbacks: none. Cost is reported only with `--prices` taken from your own Token Factory console.

### Every live review

| Plate | Mode | Status | Latency | Tokens in / out | Tier | Cited evidence |
|---|---|---|---|---|---|---|
| plate_pan_susceptible.png | routed | grounded_report | 2.53 s | 4272 / 319 | super | 6 |
| plate_mdr_organism.png | routed | grounded_report | 2.11 s | 4216 / 288 | super | 6 |
| plate_mixed_sir.png | routed | grounded_report | 2.57 s | 4248 / 427 | super | 6 |
| plate_12disk_panel.png | routed | grounded_report | 2.70 s | 4810 / 333 | super | 6 |
| plate_carbapenem_resistant.png | routed | grounded_report | 2.57 s | 4220 / 422 | super | 6 |
| plate_uneven_light.png | routed | grounded_report | 2.27 s | 4240 / 336 | super | 6 |
| plate_large_zones.png | routed | grounded_report | 2.71 s | 4314 / 327 | super | 6 |
| plate_esbl_like.png | routed | grounded_report | 2.33 s | 4245 / 318 | super | 6 |
| plate_pan_susceptible.png | ultra_only | grounded_report | 2.31 s | 4272 / 432 | ultra | 6 |
| plate_mdr_organism.png | ultra_only | grounded_report | 2.54 s | 4216 / 418 | ultra | 6 |
| plate_mixed_sir.png | ultra_only | grounded_report | 2.84 s | 4248 / 479 | ultra | 6 |
| plate_12disk_panel.png | ultra_only | grounded_report | 2.23 s | 4810 / 612 | ultra | 6 |
| plate_carbapenem_resistant.png | ultra_only | grounded_report | 2.17 s | 4220 / 459 | ultra | 6 |
| plate_uneven_light.png | ultra_only | grounded_report | 1.97 s | 4240 / 471 | ultra | 6 |
| plate_large_zones.png | ultra_only | grounded_report | 1.68 s | 4314 / 389 | ultra | 6 |
| plate_esbl_like.png | ultra_only | grounded_report | 3.21 s | 4245 / 473 | ultra | 6 |

## How to read this

- **EA** (essential agreement): share of zones measured within ±2 mm of the reference.
- **CA** (categorical agreement): share of disks whose S/I/R category matches.
- **Very major**: a resistant isolate reported susceptible, the most dangerous error. **Major**: susceptible reported resistant. **Minor**: any disagreement involving I/SDD.
- **Grounded report**: the model's narrative passed schema validation and cites only evidence IDs that exist in the deterministic report; otherwise the agent falls back to the deterministic report, which is always complete.
- Targets are the ISO 20776-2 / FDA performance criteria for AST devices. These are synthetic plates: real-photo measurement is far weaker (EA 32.9%, see `docs/VALIDATION_REPORT.md`). Nothing here is clinical validation.

## Reproduce

```bash
python scripts/run_evaluation.py                     # stage 1 only, no network
python scripts/run_evaluation.py --live --alerts ins ops   # billable
gh workflow run "Agent evaluation"                  # live run with repo secrets
```
