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
| **Antibiogo** (Fondation MSF, built on ASTimp / Pascucci et al. 2021, *Nat. Commun.*) | Free, offline, open-source Android app for Kirby-Bauer reading. **CE-IVD marked since May 2022** (in-vitro diagnostic medical device certification) -- not a research prototype. Deployed in real MSF laboratory routine use (Jordan, DR Congo, and expanding to Mali, CAR, Yemen per Fondation MSF's own project page). Winner, Google AI Impact Challenge 2019. Source library (`astimp`, Apache 2.0) at [github.com/mpascucci/AST-image-processing](https://github.com/mpascucci/AST-image-processing) includes a trained Keras/TFLite model for reading the antibiotic name printed on each disk (`pellet_labels/`) and a benchmark suite with real clinical ground truth (mm + antibiotic + organism per disk) from Amman and Creteil laboratory data (`tests/benchmark/annotations/`, 205+ images referenced, though the images themselves are hosted separately and were not accessible to us) | Built for a WHONET/EUCAST-oriented workflow, not CLSI M100 or ISO 20776-2 as reported here; the underlying `astimp` library's own repository has had no code pushes since March 2021 (the certified app itself may have continued separately); ground-truth benchmark data seen references organisms and drug panels (Amman: *S. aureus*, gram-positive) outside BacterioScope's current gram-negative Enterobacteriaceae scope, so it is not directly reusable for this project's validation without separate gram-negative data; disk-label-reading model's real-world accuracy is not published in the open repository | Apache 2.0, source public (installation requires a C++ build via a shell script, not `pip install`); Antibiogo app itself is closed-distribution CE-marked software, not simply "the open-source library" |
| **Webber et al. 2022** (*J Clin Microbiol*) | Clinical study validating early (6 h and 10 h) disk-diffusion readings against 24 h standard | Pure clinical validation, not a software tool; no automation; no open implementation | Published evidence base |

---

## The gap BacterioScope fills

**Correction to an earlier version of this document**: a previous draft claimed no
existing system combines "open source and free" with "any camera". That claim does not
survive contact with Antibiogo, which is exactly that combination, already CE-certified,
and already running in real laboratories -- a materially more mature project than
BacterioScope's current Phase 0. Overclaiming uniqueness against a system this well
documented is a credibility risk in front of evaluators who may know it, not an
advantage. The honest differentiation is narrower:

1. **CLSI M100-Ed33 2023 + ISO 20776-2 evaluation framework** — Antibiogo's public
   benchmark ground truth (Amman, Creteil) is oriented around a WHONET/EUCAST workflow;
   BacterioScope targets CLSI M100, the standard used in Colombia and most of Latin
   America. This is a real difference in target regulatory/clinical context, not a
   claim that BacterioScope's algorithm is more accurate -- it is not yet validated to
   be, and the honest F1-F3 findings in `docs/LIMITACIONES.md` should be read alongside
   this document, not instead of it.
2. **Colombian and Latin American regulatory/clinical context** — calibrated to the
   resistance landscape (Klebsiella carbapenemase, ESKAPE priority pathogens) and
   surveillance network (INS, ReLAVRA/PAHO) of low- and medium-complexity laboratories
   in the region, and a path toward INVIMA rather than CE registration.
3. **Early-reading roadmap** — Webber et al. (2022) demonstrated that readings at 6 h and
   10 h achieve ~97% categorical agreement with the 24 h standard (r > 0.98 for zone
   diameters, zero Very Major Errors at 10 h). Not yet implemented in BacterioScope, and
   not confirmed either way whether Antibiogo does this -- listed as a roadmap direction,
   not a current differentiator.
4. **A from-scratch, independently reproducible open pipeline** — Antibiogo's Apache 2.0
   library exists, but its own repository has had no code pushes since March 2021 and
   requires a C++ build script to install, not `pip install`; its real accuracy against
   the ground truth it ships is not published anywhere we found. BacterioScope publishes
   its own accuracy numbers, good and bad, as they are measured (see
   `docs/VALIDATION_REPORT.md`), which is itself worth stating plainly as a difference in
   practice, not a claim of being more accurate.

None of this makes BacterioScope more advanced than Antibiogo today. It is not. The
honest position for evaluators is: BacterioScope is an earlier-stage, CLSI/Latin-America
-oriented project in a space where a CE-certified, MSF-deployed system already exists,
and its contribution so far is a rigorously measured, openly documented validation
process rather than proven superior accuracy.

---

## What BacterioScope is not claiming

- **Not the first to measure halos automatically, and not the most mature.**
  AntibiogramJ and ADAGIO predate this project; Antibiogo is a CE-certified medical
  device already deployed in MSF laboratories, well ahead of BacterioScope's current
  Phase 0 state. The contribution here is the CLSI/Latin-America-specific framing and
  an unusually transparent validation process, not a claim of being first or best.
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
