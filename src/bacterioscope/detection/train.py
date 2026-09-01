"""YOLOv8 training script for antibiotic disk detection.

Fine-tunes a YOLOv8 object-detection model on a YOLO-format dataset of
Kirby-Bauer plate photographs.  After training, the model can locate each
antibiotic disk and classify it by the antibiotic label printed on the disk.

Usage::

    python -m bacterioscope.detection.train \\
        --data  data/processed/dataset.yaml \\
        --model yolov8n.pt \\
        --epochs 100 \\
        --output data/models/

The dataset YAML must follow the Ultralytics format with at minimum:
``train``, ``val``, ``nc`` (number of classes), and ``names`` (class list).

References
----------
Jocher, G. et al. (2023). Ultralytics YOLOv8.
https://github.com/ultralytics/ultralytics
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the training script."""
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 for antibiotic disk detection.",
    )
    parser.add_argument(
        "--data", type=Path, required=True,
        help="Path to the YOLO dataset YAML file.",
    )
    parser.add_argument(
        "--model", default="yolov8n.pt",
        help="YOLOv8 base model name or path to existing weights (default: yolov8n.pt).",
    )
    parser.add_argument(
        "--epochs", type=int, default=100,
        help="Number of training epochs (default: 100).",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/models"),
        help="Directory for trained weights (default: data/models/).",
    )
    parser.add_argument(
        "--device", default="cpu",
        help="Training device: 'cpu', '0', '0,1' (default: cpu).",
    )
    parser.add_argument(
        "--imgsz", type=int, default=640,
        help="Input image size in pixels (default: 640).",
    )
    return parser.parse_args()


def _validate_dataset(data_yaml: Path) -> None:
    """Validate that a YOLO dataset YAML has all required keys.

    Args:
        data_yaml: Path to the dataset YAML file.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If required keys are missing from the file.
    """
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {data_yaml}")
    with data_yaml.open("r", encoding="utf-8") as fh:
        cfg: dict[str, object] = yaml.safe_load(fh) or {}
    missing = {"train", "val", "nc", "names"} - cfg.keys()
    if missing:
        raise ValueError(
            f"Dataset YAML is missing required keys: {sorted(missing)}"
        )


def train(
    data_yaml: Path,
    base_model: str,
    epochs: int,
    output_dir: Path,
    device: str,
    imgsz: int,
) -> Path:
    """Fine-tune a YOLOv8 model and copy the best weights to output_dir.

    Args:
        data_yaml: Path to the YOLO-format dataset YAML.
        base_model: YOLOv8 model name (e.g. 'yolov8n.pt') or path to weights.
        epochs: Number of training epochs.
        output_dir: Directory to save the final weights file.
        device: Compute device string ('cpu', '0', '0,1').
        imgsz: Training image size in pixels.

    Returns:
        Path to the saved ``yolov8_disks.pt`` inside ``output_dir``.

    Raises:
        ImportError: If the ``ultralytics`` package is not installed.
    """
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ImportError(
            "ultralytics is required for training. "
            "Install it with: pip install 'bacterioscope[ml]'"
        ) from exc

    model = YOLO(base_model)
    abs_output = output_dir.resolve()
    model.train(
        data=str(data_yaml.resolve()),
        epochs=epochs,
        imgsz=imgsz,
        device=device,
        project=str(abs_output),
        name="disk_detector",
        exist_ok=True,
    )

    best_pt = abs_output / "disk_detector" / "weights" / "best.pt"
    dest = abs_output / "yolov8_disks.pt"
    if best_pt.is_file():
        shutil.copy2(best_pt, dest)
    return dest


def main() -> None:
    """CLI entry point for YOLOv8 disk-detection training."""
    args = _parse_args()
    try:
        _validate_dataset(args.data)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Training YOLOv8 ({args.model}) for {args.epochs} epochs on {args.data}")
    try:
        dest = train(
            data_yaml=args.data,
            base_model=args.model,
            epochs=args.epochs,
            output_dir=args.output,
            device=args.device,
            imgsz=args.imgsz,
        )
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Training complete. Weights saved to: {dest}")


if __name__ == "__main__":
    main()
