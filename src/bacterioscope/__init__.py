"""BacterioScope — automated antimicrobial susceptibility testing from plate images.

This is the top-level Python package. Installing it with ``pip install -e .``
makes the name ``bacterioscope`` importable from anywhere on your machine.

What the project does
---------------------
A Kirby-Bauer antibiogram is a circular agar plate with paper disks soaked in
antibiotics. After 16-18 hours of incubation, bacteria cannot grow near a disk
if they are susceptible to that antibiotic — a clear halo called the
"inhibition zone" forms. Clinicians measure the halo diameter with a ruler and
compare it against standardised tables (CLSI M100) to decide treatment.

BacterioScope automates that measurement:

  photograph  →  detect disks  →  measure halos  →  S/I/R report

Sub-modules
-----------
pipeline
    End-to-end orchestrator. The single entry point for analysis.
cli
    Command-line interface. Run ``python -m bacterioscope analyze <image>``.
detection
    Disk detection — YOLOv8 deep-learning model with a Hough-circles fallback.
segmentation
    Inhibition zone measurement via Otsu thresholding and contour fitting.
classification
    CLSI M100-Ed33 (2023) breakpoint lookup returning S, I, or R.
api
    FastAPI REST endpoints for programmatic access.
utils
    Calibration, visualization, and image I/O helpers.
evaluation
    ISO 20776-2 clinical agreement metrics (CA, EA, VME, ME, mE).
"""
