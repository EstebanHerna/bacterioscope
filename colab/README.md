# Colab / Drive package

`BacterioScope_Colab.ipynb` — self-contained pipeline notebook (calibration, YOLOv8 +
Hough detection, Otsu segmentation, CLSI classification). Runs locally or in Google
Colab; auto-detects a Drive-mounted `BacterioScope/` folder wherever it ends up nested.

`BacterioScope_Drive_Package.zip` (gitignored, not committed) — the notebook bundled
with sample images and the trained YOLOv8 weights, ready to unzip and upload to Google
Drive. Regenerate it by re-running the notebook build steps described in the project
history, or ask for a fresh export if this file is missing locally.
