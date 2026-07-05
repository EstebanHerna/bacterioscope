"""YOLOv8 training script for antibiotic disk detection.

Status: planned for Phase 1. This file is currently a placeholder.

What this module will do
------------------------
Once the Dryad/UZH dataset (225 Gram-negative isolates, 862 disk images) is
downloaded and converted to YOLO annotation format, this script will fine-tune
a YOLOv8 object-detection model to locate antibiotic paper disks in
Kirby-Bauer plate photographs and classify them by antibiotic name.

Background — what is YOLOv8?
------------------------------
YOLO (You Only Look Once) is a family of real-time object detection neural
networks. Version 8, developed by Ultralytics, accepts an image and produces
bounding boxes with class labels in a single forward pass through the network.

For BacterioScope, each class corresponds to one antibiotic label printed on
the paper disk (e.g. ``ciprofloxacin``, ``meropenem``). After training on
annotated plate photographs, the model will be able to:

  1. Locate every disk in a new plate image.
  2. Read its label and return the antibiotic name as the detection class.

This removes the need for manual assignment in the Streamlit demo and
enables fully automated S/I/R classification without human intervention.

Planned interface
-----------------
::

    python -m bacterioscope.detection.train \\
        --data  data/processed/dataset.yaml \\
        --model yolov8n.pt \\
        --epochs 100 \\
        --output data/models/

References
----------
Jocher, G. et al. (2023). Ultralytics YOLOv8.
https://github.com/ultralytics/ultralytics
"""
