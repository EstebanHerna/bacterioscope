"""Image I/O helper utilities.

Status: placeholder — to be implemented as the dataset pipeline grows.

What this module will contain
------------------------------
As BacterioScope is extended to process batches of images from the Dryad/UZH
dataset, this module will centralise image loading, validation, and format
conversion so that the same safe I/O logic is reused across:

  - ``pipeline.py`` (single-image analysis)
  - ``scripts/evaluate.py`` (batch evaluation)
  - ``scripts/generate_demo.py`` (demo generation)

Planned functions
-----------------
``load_image(path)``
    Load an image file with OpenCV, validate format and size, and return a
    BGR NumPy array. Raise clear errors if the file is missing, unreadable,
    or exceeds the size cap.

``save_image(image, path)``
    Write a BGR NumPy array to disk. Create parent directories if needed.

``resize_for_inference(image, target_size)``
    Resize an image to the standard input size expected by the YOLOv8 model
    while preserving the aspect ratio via letterboxing.
"""
