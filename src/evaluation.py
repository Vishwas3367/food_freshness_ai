import numpy as np

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)


# ============================================================
# 1. REGRESSION EVALUATION
# ============================================================

def regression_metrics(y_true, y_pred):
    """
    Calculate performance metrics for
    Remaining Shelf Life (RSL) prediction.

    y_true = actual remaining shelf life
    y_pred = predicted remaining shelf life
    """

    mae = mean_absolute_error(
        y_true,
        y_pred
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    r2 = r2_score(
        y_true,
        y_pred
    )

    return {
        "MAE_days": float(mae),
        "RMSE_days": float(rmse),
        "R2": float(r2)
    }


# ============================================================
# 2. FRESHNESS CLASSIFICATION
# ============================================================

def freshness_class(
    rsl,
    fresh_threshold=3.0,
    consume_threshold=1.0
):
    """
    Convert Remaining Shelf Life into a
    simple freshness category.

    IMPORTANT:
    These thresholds are temporary development
    values. They must be calibrated using our
    real experimental data.
    """

    if rsl > fresh_threshold:

        return "Fresh"

    elif rsl > consume_threshold:

        return "Consume Soon"

    else:

        return "Spoiled"


# ============================================================
# 3. CONVERT MULTIPLE RSL VALUES TO CLASSES
# ============================================================

def classify_predictions(
    rsl_values,
    fresh_threshold=3.0,
    consume_threshold=1.0
):
    """
    Convert a list/array of RSL predictions
    into freshness classes.
    """

    return [
        freshness_class(
            rsl,
            fresh_threshold,
            consume_threshold
        )
        for rsl in rsl_values
    ]


# ============================================================
# 4. CLASSIFICATION EVALUATION
# ============================================================

def classification_metrics(
    y_true,
    y_pred
):
    """
    Calculate classification performance.

    Metrics:
    Accuracy
    Precision
    Recall
    F1-score
    """

    accuracy = accuracy_score(
        y_true,
        y_pred
    )

    precision = precision_score(
        y_true,
        y_pred,
        average="weighted",
        zero_division=0
    )

    recall = recall_score(
        y_true,
        y_pred,
        average="weighted",
        zero_division=0
    )

    f1 = f1_score(
        y_true,
        y_pred,
        average="weighted",
        zero_division=0
    )

    return {
        "Accuracy": float(accuracy),
        "Precision": float(precision),
        "Recall": float(recall),
        "F1": float(f1)
    }


# ============================================================
# 5. CONFUSION MATRIX
# ============================================================

def get_confusion_matrix(
    y_true,
    y_pred,
    labels=None
):
    """
    Generate confusion matrix for
    freshness classification.
    """

    return confusion_matrix(
        y_true,
        y_pred,
        labels=labels
    )