# State of the Art: Automated Kirby-Bauer Disk Diffusion Reading

This document positions BacterioScope relative to existing automated antimicrobial
susceptibility testing (AST) systems and published research.  It is intended for
evaluators, potential collaborators, and as background for the BDIC 2026 submission.

---

## Existing systems and their limitations

| System | What it does | Key limitation | Access |
|---|---|---|---|
| **AntibiogramJ** (Putze & Bosshard, 2017) | Semi-automatic inhibition zone reader for scanned images; Java desktop | Semi-manual (user draws each zone); no antibiotic label reading; no early-reading support; no active maintenance since 2020 | Open source, unmaintained |
| **ADAGIO** (i2a) | Automated plate reader with camera, image processing, EUCAST/CLSI integration | Hardware cost ~EUR 40 000+; requires service contracts; dependent on proprietary reagent supply chain | Commercial, proprietary |
| **SIRscan** (i2a) | Same family as ADAGIO; used in the UZH Dryad validation dataset | Same hardware and cost constraints | Commercial, proprietary |
| **VITEK 2** (bioMérieux) | Fluorescence-based AST, not disk diffusion; fastest turnaround in high-complexity labs | USD 80 000+ capital cost; not disk diffusion; requires continuous reagent supply | Commercial, proprietary |
| **BD Phoenix** (Becton Dickinson) | Automated broth microdilution | USD 60 000+; same supply-chain dependency | Commercial, proprietary |
| **Pascucci et al. 2021** (ASTimp, *Nat. Commun.*) | Smartphone app and C++/Python library for Kirby-Bauer reading; validated on clinical plates; source available at [github.com/mpascucci/AST-image-processing](https://github.com/mpascucci/AST-image-processing) | Halo measured as circle, not real contour; no per-antibiotic label reading in open implementation; no CLSI breakpoint integration; not maintained since 2022; Android-only app, no web/API interface | Apache 2.0, source public |
| **Webber et al. 2022** (*J Clin Microbiol*) | Clinical study validating early (6 h and 10 h) disk-diffusion readings against 24 h standard | Pure clinical validation, not a software tool; no automation; no open implementation | Published evidence base |

---

## The gap BacterioScope fills

None of the systems above occupy the following combination simultaneously:

1. **Open source and free** — no capital cost, no reagent lock-in, reproducible by any lab.
2. **Any camera** — a smartphone or basic USB webcam is sufficient; no proprietary hardware.
3. **CLSI M100-Ed33 2023 + ISO 20776-2 evaluation framework** — clinically validated
   breakpoints and quality metrics, not a proprietary algorithm.
4. **Early-reading roadmap** — Webber et al. (2022) demonstrated that readings at 6 h and
   10 h achieve ~97% categorical agreement with the 24 h standard (r > 0.98 for zone
   diameters, zero Very Major Errors at 10 h).  BacterioScope is designed to automate
   that reading window, reducing turnaround from overnight to same-shift.
5. **Colombian and Latin American context** — calibrated to the resistance landscape
   (Klebsiella carbapenemase, ESKAPE priority pathogens) and surveillance network (INS,
   ReLAVRA/PAHO) of low- and medium-complexity laboratories that cannot sustain VITEK or
   Phoenix infrastructure.

---

## What BacterioScope is not claiming

- **Not the first to measure halos automatically.** AntibiogramJ and ADAGIO predate this
  project.  The contribution is the combination above, not the measurement idea.
- **Not a replacement for VITEK in high-complexity settings.** Those labs have the budget
  and supply chain for gold-standard systems.  BacterioScope targets the labs that do not.
- **Early reading is planned, not yet implemented.** The Webber 2022 evidence base makes
  it technically feasible; the Phase 2 YOLOv8 detector (which reads the printed antibiotic
  label) is the prerequisite before a timed reading protocol can be automated.

---

## Scientific support for the early-reading hypothesis

> Webber DM, Wallace MA, Burnham CA (2022).
> Stop Waiting for Tomorrow: Disk Diffusion Performed on Early Growth Is an Accurate
> Method for Antimicrobial Susceptibility Testing with Reduced Turnaround Time.
> *Journal of Clinical Microbiology* 60(5): e03007-20.
> doi:10.1128/JCM.03007-20

Key findings relevant to BacterioScope:

- **6-hour reading**: categorical agreement (CA) with 24 h reference ~90%; zone
  diameters strongly correlated (r > 0.95).
- **10-hour reading**: CA ~97%; Pearson r > 0.98 for zone diameters; **zero Very Major
  Errors** (no resistant isolate misclassified as susceptible).
- **Clinical implication**: a 10 h read gives a same-shift result in most working
  schedules, cutting antibiotic-prescribing delay from the next morning to the same day.

This study validates that the disk-diffusion signal at early timepoints contains enough
information for reliable classification.  BacterioScope will automate the image capture
and zone measurement step; the classification threshold adjustments for early reading
(if needed) would follow from this and similar studies.

---

## References

- Webber DM, Wallace MA, Burnham CA (2022). Stop Waiting for Tomorrow: Disk Diffusion
  Performed on Early Growth Is an Accurate Method for Antimicrobial Susceptibility Testing
  with Reduced Turnaround Time. *J Clin Microbiol* 60(5): e03007-20.
  doi:10.1128/JCM.03007-20

- Pascucci M, Royer G, Adamek J, et al. (2021). AI-based mobile application to fight
  antibiotic resistance. *Nat Commun* 12: 1173. doi:10.1038/s41467-021-21187-3

- Egli A, Imkamp F, Amlang G, Brunner S, Albrich W, et al. (2023). Automated reading of
  disk diffusion antibiograms. Dryad Digital Repository.
  doi:10.5061/dryad.5dv41nsfj

- Putze J, Bosshard PP (2017). AntibiogramJ: A tool for the analysis of disk diffusion
  antibiograms. *J Microbiol Methods* 142: 101-104.

- CLSI (2023). M100 Performance Standards for Antimicrobial Susceptibility Testing.
  33rd ed. Clinical and Laboratory Standards Institute, Wayne, PA.

- EUCAST (2023). EUCAST Definitive Document EDef 13.2: Method for the determination of
  broth microdilution MICs of antifungal agents. European Committee on Antimicrobial
  Susceptibility Testing.
