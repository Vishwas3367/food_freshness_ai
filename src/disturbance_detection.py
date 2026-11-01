import numpy as np
import pandas as pd


def calculate_disturbance_features(df):
    """
    Detect short-term environmental disturbances.

    The purpose is to distinguish:
    
        Environmental change
                from
        Possible food degradation

    This is a research prototype.
    Thresholds will be calibrated using real
    experimental data.
    """

    out = df.copy()

    # ---------------------------------------------------------
    # 1. TEMPERATURE CHANGE
    # ---------------------------------------------------------

    temperature_change = (
        out["temperature_c_delta"].abs()
    )

    # ---------------------------------------------------------
    # 2. HUMIDITY CHANGE
    # ---------------------------------------------------------

    humidity_change = (
        out["humidity_pct_delta"].abs()
    )

    # ---------------------------------------------------------
    # 3. GAS CHANGE
    # ---------------------------------------------------------

    gas_change = (
        out["gas_raw_delta"].abs()
    )

    # ---------------------------------------------------------
    # 4. WEIGHT CHANGE
    # ---------------------------------------------------------

    weight_change = (
        out["weight_g_delta"].abs()
    )

    # ---------------------------------------------------------
    # 5. NORMALIZATION FUNCTION
    # ---------------------------------------------------------

    def normalize(series):

        minimum = series.min()
        maximum = series.max()

        if maximum - minimum < 1e-9:
            return pd.Series(
                0.0,
                index=series.index
            )

        return (
            (series - minimum)
            / (maximum - minimum)
        )

    temp_score = normalize(
        temperature_change
    )

    humidity_score = normalize(
        humidity_change
    )

    gas_score = normalize(
        gas_change
    )

    weight_score = normalize(
        weight_change
    )

    # ---------------------------------------------------------
    # 6. ENVIRONMENTAL DISTURBANCE SCORE
    # ---------------------------------------------------------

    # Temperature and humidity changes are treated as
    # the main environmental indicators.

    out["environment_disturbance_score"] = (
        0.50 * temp_score
        + 0.50 * humidity_score
    )

    # ---------------------------------------------------------
    # 7. FOOD RESPONSE SCORE
    # ---------------------------------------------------------

    # Gas increase and weight loss are treated as
    # food-response indicators.

    gas_increase = (
        out["gas_raw_delta"]
        .clip(lower=0)
    )

    weight_loss = (
        -out["weight_g_delta"]
    ).clip(lower=0)

    gas_increase_score = normalize(
        gas_increase
    )

    weight_loss_score = normalize(
        weight_loss
    )

    out["food_response_score"] = (
        0.55 * gas_increase_score
        + 0.45 * weight_loss_score
    )

    # ---------------------------------------------------------
    # 8. DISTURBANCE-TO-DEGRADATION RATIO
    # ---------------------------------------------------------

    out["environment_food_ratio"] = (
        out["environment_disturbance_score"]
        /
        (
            out["food_response_score"]
            + 0.001
        )
    )

    # ---------------------------------------------------------
    # 9. DISTURBANCE DETECTION
    # ---------------------------------------------------------

    environment = (
        out["environment_disturbance_score"]
    )

    food_response = (
        out["food_response_score"]
    )

    # Strong environmental change but weak
    # food response = likely environmental disturbance.

    out["environmental_disturbance"] = (
        (environment > 0.60)
        &
        (food_response < 0.35)
    ).astype(int)

    # ---------------------------------------------------------
    # 10. POSSIBLE DEGRADATION RESPONSE
    # ---------------------------------------------------------

    # Strong food response while environmental
    # conditions remain relatively stable.

    out["possible_food_degradation"] = (
        (food_response > 0.55)
        &
        (environment < 0.50)
    ).astype(int)

    # ---------------------------------------------------------
    # 11. MIXED CONDITION
    # ---------------------------------------------------------

    # Both environmental and food signals are changing.

    out["mixed_condition"] = (
        (environment >= 0.50)
        &
        (food_response >= 0.50)
    ).astype(int)

    # ---------------------------------------------------------
    # 12. FINAL CONDITION
    # ---------------------------------------------------------

    out["detected_condition"] = np.select(

        [
            out["environmental_disturbance"] == 1,

            out["possible_food_degradation"] == 1,

            out["mixed_condition"] == 1
        ],

        [
            "Environmental Disturbance",

            "Possible Food Degradation",

            "Mixed Condition"
        ],

        default="Stable Condition"
    )

    return out