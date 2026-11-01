import numpy as np
import pandas as pd


def calculate_prediction_confidence(df):
    """
    Calculate a confidence score for the freshness/RSL prediction.

    Confidence is based on:
        1. Overall sensor reliability
        2. Agreement between gas and weight
        3. Environmental disturbance
        4. Consistency of the degradation trajectory

    Output:
        0.0 -> very low confidence
        1.0 -> very high confidence

    This is a research prototype.
    The final formulation will be validated using
    real experimental data.
    """

    out = df.copy()

    # ---------------------------------------------------------
    # 1. SENSOR RELIABILITY
    # ---------------------------------------------------------

    sensor_reliability = (
        out["overall_sensor_reliability"]
        .clip(0.0, 1.0)
    )

    # ---------------------------------------------------------
    # 2. SENSOR AGREEMENT
    # ---------------------------------------------------------

    sensor_agreement = (
        out["sensor_agreement"]
        .clip(0.0, 1.0)
    )

    # ---------------------------------------------------------
    # 3. ENVIRONMENTAL DISTURBANCE
    # ---------------------------------------------------------

    disturbance = (
        out["environment_disturbance_score"]
        .clip(0.0, 1.0)
    )

    # A strong disturbance increases uncertainty.
    disturbance_confidence = (
        1.0 - disturbance
    )

    # ---------------------------------------------------------
    # 4. DEGRADATION TRAJECTORY CONSISTENCY
    # ---------------------------------------------------------

    # A stable trajectory gives higher confidence.
    # A rapidly changing trajectory gives lower confidence.

    acceleration = (
        out["degradation_acceleration"]
        .abs()
    )

    max_acceleration = acceleration.max()

    if max_acceleration < 1e-9:

        acceleration_norm = pd.Series(
            0.0,
            index=out.index
        )

    else:

        acceleration_norm = (
            acceleration
            / max_acceleration
        )

    trajectory_consistency = (
        1.0 - acceleration_norm
    )

    trajectory_consistency = (
        trajectory_consistency
        .clip(0.0, 1.0)
    )

    out["trajectory_consistency"] = (
        trajectory_consistency
    )

    # ---------------------------------------------------------
    # 5. COMBINED CONFIDENCE
    # ---------------------------------------------------------

    out["prediction_confidence"] = (

        0.40 * sensor_reliability

        + 0.25 * sensor_agreement

        + 0.20 * disturbance_confidence

        + 0.15 * trajectory_consistency
    )

    out["prediction_confidence"] = (
        out["prediction_confidence"]
        .clip(0.0, 1.0)
    )

    # ---------------------------------------------------------
    # 6. CONFIDENCE PERCENTAGE
    # ---------------------------------------------------------

    out["confidence_percent"] = (
        out["prediction_confidence"]
        * 100.0
    )

    # ---------------------------------------------------------
    # 7. CONFIDENCE CATEGORY
    # ---------------------------------------------------------

    out["confidence_level"] = np.select(

        [
            out["prediction_confidence"] >= 0.75,

            out["prediction_confidence"] >= 0.50
        ],

        [
            "High",

            "Medium"
        ],

        default="Low"
    )

    # ---------------------------------------------------------
    # 8. ADAPTIVE SAMPLING DECISION
    # ---------------------------------------------------------

    # If confidence is low, the system should consider
    # taking additional measurements.

    out["adaptive_sampling_required"] = (
        out["prediction_confidence"] < 0.50
    ).astype(int)

    # ---------------------------------------------------------
    # 9. SAMPLING ACTION
    # ---------------------------------------------------------

    out["sampling_action"] = np.select(

        [
            out["prediction_confidence"] < 0.50,

            out["prediction_confidence"] < 0.75
        ],

        [
            "Increase Measurement Frequency",

            "Continue Monitoring Carefully"
        ],

        default="Normal Measurement Frequency"
    )

    return out