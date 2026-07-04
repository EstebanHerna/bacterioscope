"""Clinical agreement metrics for antimicrobial susceptibility testing evaluation.

Implements FDA/ISO 20776-2 agreement metrics adapted for disk diffusion
zone diameter measurements.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

CATEGORIES: tuple[str, ...] = ("S", "I", "R")
_EA_MARGIN_MM: float = 2.0


def _validate(a: NDArray[Any], b: NDArray[Any]) -> None:
    if len(a) != len(b):
        raise ValueError("predicted and reference must have the same length.")
    if len(a) == 0:
        raise ValueError("Input arrays must not be empty.")


def categorical_agreement(
    predicted: Sequence[str],
    reference: Sequence[str],
) -> float:
    """Compute Categorical Agreement (CA).

    CA is the percentage of isolates where the predicted S/I/R category
    matches the reference, expressed as a fraction in [0.0, 1.0]. It is
    the primary agreement metric in ISO 20776-2 and FDA guidance documents
    for validating automated AST systems.

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.

    Returns:
        CA as a fraction in [0.0, 1.0].

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    pred = np.asarray(predicted)
    ref = np.asarray(reference)
    _validate(pred, ref)
    return float(np.mean(pred == ref))


def error_rates(
    predicted: Sequence[str],
    reference: Sequence[str],
) -> dict[str, int | float]:
    """Compute Very Major, Major, and minor Error rates.

    Definitions per ISO 20776-2 and CLSI M23:

    Very Major Error (VME): predicted S when reference is R.
      The system labels a resistant isolate as susceptible. A patient
      receives an antibiotic that will not work. This is the most
      dangerous clinical outcome. VME rate denominator = all truly
      Resistant isolates in the reference set.

    Major Error (ME): predicted R when reference is S.
      The system labels a susceptible isolate as resistant. A patient
      is denied an effective antibiotic.
      ME rate denominator = all truly Susceptible isolates.

    minor Error (mE): any categorical discordance involving the I
      (Intermediate) category in either direction (S->I, I->S, I->R,
      R->I). Less immediately dangerous because I implies the antibiotic
      may still work at appropriately elevated doses.
      mE rate denominator = all isolates.

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.

    Returns:
        Dict with keys: vme_count, vme_rate, me_count, me_rate,
        minor_count, minor_rate, n_resistant, n_susceptible, n_total.

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    pred = np.asarray(predicted)
    ref = np.asarray(reference)
    _validate(pred, ref)

    n = len(pred)
    n_r = int(np.sum(ref == "R"))
    n_s = int(np.sum(ref == "S"))

    vme = int(np.sum((pred == "S") & (ref == "R")))
    me = int(np.sum((pred == "R") & (ref == "S")))
    minor = int(np.sum((pred != ref) & ((pred == "I") | (ref == "I"))))

    return {
        "vme_count": vme,
        "vme_rate": vme / n_r if n_r > 0 else 0.0,
        "me_count": me,
        "me_rate": me / n_s if n_s > 0 else 0.0,
        "minor_count": minor,
        "minor_rate": minor / n,
        "n_resistant": n_r,
        "n_susceptible": n_s,
        "n_total": n,
    }


def essential_agreement(
    measured_mm: Sequence[float],
    reference_mm: Sequence[float],
    margin_mm: float = _EA_MARGIN_MM,
) -> float:
    """Compute Essential Agreement (EA) for zone diameter measurements.

    Adaptation note: Classical EA per ISO 20776-2 measures whether the
    test-system MIC falls within one two-fold dilution of the reference MIC.
    BacterioScope measures inhibition zone diameters in millimetres, not MIC
    values. EA is adapted here as the percentage of diameter measurements
    within +/- margin_mm of the reference diameter. The default margin of
    2.0 mm reflects typical inter-reader reproducibility for manual disk
    diffusion measurement per EUCAST EDef 13.2. This definition must be
    disclosed when comparing results to ISO 20776-2 EA figures.

    Args:
        measured_mm: Diameters measured by the system (mm).
        reference_mm: Reference diameters from ground truth (mm).
        margin_mm: Tolerance window in mm. Default is 2.0.

    Returns:
        EA as a fraction in [0.0, 1.0].

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    meas: NDArray[np.float64] = np.asarray(measured_mm, dtype=np.float64)
    ref: NDArray[np.float64] = np.asarray(reference_mm, dtype=np.float64)
    _validate(meas, ref)
    return float(np.mean(np.abs(meas - ref) <= margin_mm))


def zone_diameter_stats(
    measured_mm: Sequence[float],
    reference_mm: Sequence[float],
) -> dict[str, float]:
    """Compute MAE and Pearson correlation for zone diameters.

    Args:
        measured_mm: Diameters measured by the system (mm).
        reference_mm: Reference diameters from ground truth (mm).

    Returns:
        Dict with keys:
        - mae_mm: Mean Absolute Error in mm.
        - pearson_r: Pearson correlation coefficient in [-1.0, 1.0].

    Raises:
        ValueError: If arrays have fewer than 2 elements or different lengths.
    """
    meas: NDArray[np.float64] = np.asarray(measured_mm, dtype=np.float64)
    ref: NDArray[np.float64] = np.asarray(reference_mm, dtype=np.float64)
    _validate(meas, ref)
    if len(meas) < 2:
        raise ValueError("At least 2 measurements are required for correlation.")
    mae = float(np.mean(np.abs(meas - ref)))
    corr: NDArray[np.float64] = np.corrcoef(meas, ref)
    r = float(corr[0, 1])
    return {"mae_mm": mae, "pearson_r": r}


def sir_confusion_matrix(
    predicted: Sequence[str],
    reference: Sequence[str],
) -> NDArray[np.intp]:
    """Compute S/I/R confusion matrix with canonical label ordering (S, I, R).

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.

    Returns:
        3x3 integer array. Rows = reference classes, columns = predicted
        classes, both in order (S, I, R). Entry cm[i, j] is the count of
        samples with reference class i predicted as class j.

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    pred = np.asarray(predicted)
    ref = np.asarray(reference)
    _validate(pred, ref)
    return confusion_matrix(ref, pred, labels=list(CATEGORIES))


def per_class_metrics(
    predicted: Sequence[str],
    reference: Sequence[str],
) -> dict[str, dict[str, float]]:
    """Compute precision, recall, and F1 per S/I/R class.

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.

    Returns:
        Dict mapping each category ('S', 'I', 'R') to a sub-dict
        with keys precision, recall, f1, support.

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    pred = np.asarray(predicted)
    ref = np.asarray(reference)
    _validate(pred, ref)
    p, r, f, s = precision_recall_fscore_support(
        reference,
        predicted,
        labels=list(CATEGORIES),
        zero_division=0,
    )
    return {
        cat: {
            "precision": float(p[i]),
            "recall": float(r[i]),
            "f1": float(f[i]),
            "support": int(s[i]),
        }
        for i, cat in enumerate(CATEGORIES)
    }


def overall_accuracy(
    predicted: Sequence[str],
    reference: Sequence[str],
) -> float:
    """Compute overall S/I/R classification accuracy.

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.

    Returns:
        Accuracy as a fraction in [0.0, 1.0].

    Raises:
        ValueError: If arrays have different lengths or are empty.
    """
    pred = np.asarray(predicted)
    ref = np.asarray(reference)
    _validate(pred, ref)
    return float(accuracy_score(reference, predicted))


def collect_metrics(
    predicted: Sequence[str],
    reference: Sequence[str],
    measured_mm: Sequence[float] | None = None,
    reference_mm: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Aggregate all evaluation metrics into a unified results dict.

    Args:
        predicted: Predicted S/I/R categories.
        reference: Reference (ground-truth) S/I/R categories.
        measured_mm: Measured zone diameters in mm (optional).
        reference_mm: Reference zone diameters in mm (optional).

    Returns:
        Dict with keys: accuracy, categorical_agreement, error_rates,
        per_class, confusion_matrix, and optionally essential_agreement
        and zone_stats when diameter arrays are provided.

    Raises:
        ValueError: If only one of measured_mm/reference_mm is given.
    """
    if (measured_mm is None) != (reference_mm is None):
        raise ValueError("Provide both measured_mm and reference_mm, or neither.")
    result: dict[str, Any] = {
        "accuracy": overall_accuracy(predicted, reference),
        "categorical_agreement": categorical_agreement(predicted, reference),
        "error_rates": error_rates(predicted, reference),
        "per_class": per_class_metrics(predicted, reference),
        "confusion_matrix": sir_confusion_matrix(predicted, reference).tolist(),
    }
    if measured_mm is not None and reference_mm is not None:
        result["essential_agreement"] = essential_agreement(measured_mm, reference_mm)
        result["zone_stats"] = zone_diameter_stats(measured_mm, reference_mm)
    return result
