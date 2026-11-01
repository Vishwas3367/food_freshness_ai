import numpy as np
import pandas as pd


# ============================================================
# HELPER
# ============================================================

def safe_series(df, column):

    if column in df.columns:

        return pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0.0)

    return pd.Series(
        0.0,
        index=df.index
    )


# ============================================================
# NORMALIZE SIGNAL
# ============================================================

def normalize_positive(
    series,
    lower=0.0,
    upper=3.0
):
    """
    Convert a positive degradation signal into 0-1.

    This is a software scoring function, NOT a biological
    spoilage equation.
    """

    values = pd.to_numeric(
        series,
        errors="coerce"
    ).fillna(0.0)

    values = values.clip(
        lower=lower
    )

    normalized = (
        values - lower
    ) / (
        upper - lower
    )

    return normalized.clip(
        0.0,
        1.0
    )


# ============================================================
# CALCULATE STATE FEATURES
# ============================================================

def calculate_state_features(df):

    data = df.copy()

    # ========================================================
    # 1. GAS DEGRADATION EVIDENCE
    # ========================================================

    gas_relative = safe_series(
        data,
        "gas_raw_relative_change"
    )

    gas_increase = safe_series(
        data,
        "gas_increase"
    )

    gas_change_score = safe_series(
        data,
        "gas_change_score"
    )

    gas_acceleration = safe_series(
        data,
        "gas_acceleration_score"
    )

    gas_relative_signal = (
        normalize_positive(
            gas_relative.abs(),
            0.0,
            0.50
        )
    )

    gas_change_signal = (
        normalize_positive(
            gas_change_score,
            0.0,
            3.0
        )
    )

    gas_acceleration_signal = (
        normalize_positive(
            gas_acceleration,
            0.0,
            10.0
        )
    )

    gas_signal = (
        0.45 * gas_relative_signal
        +
        0.35 * gas_change_signal
        +
        0.20 * gas_acceleration_signal
    )

    # ========================================================
    # 2. WEIGHT DEGRADATION EVIDENCE
    # ========================================================

    weight_relative = safe_series(
        data,
        "weight_g_relative_change"
    )

    weight_loss_score = safe_series(
        data,
        "weight_loss_score"
    )

    weight_acceleration = safe_series(
        data,
        "weight_acceleration_score"
    )

    weight_loss_signal = (
        normalize_positive(
            weight_relative.abs(),
            0.0,
            0.10
        )
    )

    weight_change_signal = (
        normalize_positive(
            weight_loss_score,
            0.0,
            3.0
        )
    )

    weight_acceleration_signal = (
        normalize_positive(
            weight_acceleration,
            0.0,
            1.0
        )
    )

    weight_signal = (
        0.50 * weight_loss_signal
        +
        0.30 * weight_change_signal
        +
        0.20 * weight_acceleration_signal
    )

    # ========================================================
    # 3. TEMPERATURE / ENVIRONMENT SIGNAL
    # ========================================================

    temperature_change = safe_series(
        data,
        "temperature_change_score"
    )

    environment_change = safe_series(
        data,
        "environment_change_score"
    )

    thermal_stress = safe_series(
        data,
        "thermal_stress"
    )

    temperature_signal = (
        normalize_positive(
            temperature_change,
            0.0,
            3.0
        )
    )

    environment_signal = (
        normalize_positive(
            environment_change,
            0.0,
            3.0
        )
    )

    thermal_signal = (
        normalize_positive(
            thermal_stress,
            0.0,
            5.0
        )
    )

    environment_degradation_signal = (
        0.40 * temperature_signal
        +
        0.30 * environment_signal
        +
        0.30 * thermal_signal
    )

    # ========================================================
    # 4. GAS + WEIGHT AGREEMENT
    # ========================================================

    gas_weight_interaction = safe_series(
        data,
        "gas_weight_interaction"
    )

    interaction_signal = (
        normalize_positive(
            gas_weight_interaction,
            0.0,
            3.0
        )
    )

    # ========================================================
    # 5. MULTI-SENSOR DEGRADATION EVIDENCE
    # ========================================================

    data[
        "gas_degradation_signal"
    ] = gas_signal.clip(
        0.0,
        1.0
    )

    data[
        "weight_degradation_signal"
    ] = weight_signal.clip(
        0.0,
        1.0
    )

    data[
        "environment_degradation_signal"
    ] = environment_degradation_signal.clip(
        0.0,
        1.0
    )

    data[
        "sensor_interaction_signal"
    ] = interaction_signal.clip(
        0.0,
        1.0
    )

    # ========================================================
    # 6. DEGRADATION EVIDENCE
    # ========================================================

    data[
        "degradation_evidence"
    ] = (
        0.40
        * data[
            "gas_degradation_signal"
        ]
        +
        0.30
        * data[
            "weight_degradation_signal"
        ]
        +
        0.15
        * data[
            "environment_degradation_signal"
        ]
        +
        0.15
        * data[
            "sensor_interaction_signal"
        ]
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 7. DEGRADATION INDEX
    # ========================================================

    data[
        "degradation_index"
    ] = (
        data[
            "degradation_evidence"
        ]
        .rolling(
            window=10,
            min_periods=1
        )
        .mean()
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 8. DEGRADATION CHANGE
    # ========================================================

    data[
        "degradation_change"
    ] = (
        data[
            "degradation_index"
        ].diff()
        .fillna(0.0)
    )

    # ========================================================
    # 9. DEGRADATION ACCELERATION
    # ========================================================

    data[
        "degradation_acceleration"
    ] = (
        data[
            "degradation_change"
        ].diff()
        .fillna(0.0)
    )

    # ========================================================
    # 10. TRAJECTORY SCORE
    # ========================================================

    trajectory = safe_series(
        data,
        "trajectory_score"
    )

    trajectory_signal = (
        normalize_positive(
            trajectory,
            0.0,
            3.0
        )
    )

    data[
        "trajectory_degradation_signal"
    ] = trajectory_signal

    # ========================================================
    # 11. FINAL STATE SCORE
    # ========================================================

    data[
        "state_score"
    ] = (
        0.70
        * data[
            "degradation_index"
        ]
        +
        0.20
        * data[
            "trajectory_degradation_signal"
        ]
        +
        0.10
        * data[
            "sensor_interaction_signal"
        ]
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 12. STATE CLASSIFICATION
    # ========================================================

    def classify_state(score):

        if score < 0.20:

            return "Normal"

        elif score < 0.40:

            return "Early Degradation"

        elif score < 0.70:

            return "Degrading"

        else:

            return "Advanced Degradation"

    data[
        "degradation_state"
    ] = data[
        "state_score"
    ].apply(
        classify_state
    )

    # ========================================================
    # 13. STATE CHANGE
    # ========================================================

    data[
        "state_change"
    ] = (
        data[
            "degradation_state"
        ]
        !=
        data[
            "degradation_state"
        ].shift(1)
    ).astype(int)

    # First observation is not a state transition.
    if len(data) > 0:

        data.loc[
            data.index[0],
            "state_change"
        ] = 0

    return data


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("DEGRADATION STATE ENGINE TEST")
    print("=" * 65)

    np.random.seed(42)

    rows = []

    gas_values = [
        200,
        202,
        205,
        208,
        214,
        222,
        232,
        245,
        260,
        278,
        300,
        325
    ]

    weight_values = [
        150.0,
        149.9,
        149.8,
        149.7,
        149.5,
        149.3,
        149.0,
        148.7,
        148.3,
        147.9,
        147.4,
        146.8
    ]

    temperature_values = [
        24.0,
        24.1,
        24.3,
        24.5,
        24.8,
        25.2,
        25.8,
        26.5,
        27.2,
        28.0,
        28.7,
        29.5
    ]

    for i in range(12):

        rows.append({

            "temperature_c":
                temperature_values[i],

            "humidity_pct":
                70.0,

            "gas_raw":
                gas_values[i],

            "weight_g":
                weight_values[i],

            "gas_raw_delta":
                0
                if i == 0
                else
                gas_values[i]
                - gas_values[i - 1],

            "weight_g_delta":
                0
                if i == 0
                else
                weight_values[i]
                - weight_values[i - 1],

            "gas_raw_relative_change":
                (
                    gas_values[i] - 200
                ) / 200,

            "weight_g_relative_change":
                (
                    weight_values[i] - 150
                ) / 150,

            "gas_increase":
                0
                if i == 0
                else max(
                    gas_values[i]
                    - gas_values[i - 1],
                    0
                ),

            "weight_loss":
                0
                if i == 0
                else max(
                    weight_values[i - 1]
                    - weight_values[i],
                    0
                ),

            "gas_change_score":
                i * 0.25,

            "weight_loss_score":
                i * 0.10,

            "temperature_change_score":
                0
                if i == 0
                else abs(
                    temperature_values[i]
                    - temperature_values[i - 1]
                ),

            "environment_change_score":
                0
                if i == 0
                else abs(
                    temperature_values[i]
                    - temperature_values[i - 1]
                ),

            "gas_acceleration_score":
                i * 0.10,

            "weight_acceleration_score":
                i * 0.02,

            "gas_weight_interaction":
                i * 0.10,

            "thermal_stress":
                max(
                    temperature_values[i]
                    - 25.0,
                    0
                ),

            "trajectory_score":
                i * 0.20
        })

    df = pd.DataFrame(
        rows
    )

    result = calculate_state_features(
        df
    )

    print(
        "\nState progression:"
    )

    print("-" * 65)

    print(
        result[
            [
                "gas_raw",
                "weight_g",
                "temperature_c",
                "degradation_evidence",
                "degradation_index",
                "degradation_change",
                "degradation_acceleration",
                "state_score",
                "degradation_state"
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nFinal degradation state:"
    )

    print(
        result.iloc[-1][
            [
                "degradation_evidence",
                "degradation_index",
                "degradation_change",
                "degradation_acceleration",
                "state_score",
                "degradation_state"
            ]
        ]
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "DEGRADATION STATE ENGINE TEST COMPLETE"
    )

    print(
        "=" * 65
    )