import numpy as np
import pandas as pd


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

SENSORS = {
    "temperature": "temperature_c",
    "humidity": "humidity_pct",
    "gas": "gas_raw",
    "weight": "weight_g"
}


# ============================================================
# SAFE NUMERIC SERIES
# ============================================================

def safe_numeric(df, column):

    if column not in df.columns:

        return pd.Series(
            np.nan,
            index=df.index,
            dtype=float
        )

    return pd.to_numeric(
        df[column],
        errors="coerce"
    )


# ============================================================
# CREATE MISSING TEMPORAL SIGNALS
# ============================================================

def ensure_temporal_signals(df):

    out = df.copy()

    for sensor_name, column in SENSORS.items():

        values = safe_numeric(
            out,
            column
        )

        # ----------------------------------------------------
        # Delta
        # ----------------------------------------------------

        delta_column = (
            f"{column}_delta"
        )

        if delta_column not in out.columns:

            out[
                delta_column
            ] = (
                values
                .diff()
                .fillna(0.0)
            )

        # ----------------------------------------------------
        # Rolling standard deviation
        # ----------------------------------------------------

        std_column = (
            f"{column}_rolling_std"
        )

        if std_column not in out.columns:

            out[
                std_column
            ] = (
                values
                .rolling(
                    window=10,
                    min_periods=1
                )
                .std()
                .fillna(0.0)
            )

    return out


# ============================================================
# CALCULATE SENSOR RELIABILITY
# ============================================================

def calculate_sensor_reliability(df):

    out = ensure_temporal_signals(
        df
    )

    reliability_columns = []

    # ========================================================
    # INDIVIDUAL SENSOR RELIABILITY
    # ========================================================

    for sensor_name, column in SENSORS.items():

        values = safe_numeric(
            out,
            column
        )

        delta = pd.to_numeric(
            out[
                f"{column}_delta"
            ],
            errors="coerce"
        ).fillna(0.0)

        rolling_std = pd.to_numeric(
            out[
                f"{column}_rolling_std"
            ],
            errors="coerce"
        ).fillna(0.0)

        # ----------------------------------------------------
        # Missing-value reliability
        # ----------------------------------------------------

        valid_signal = (
            values.notna()
            .astype(float)
        )

        # ----------------------------------------------------
        # Sudden-change instability
        # ----------------------------------------------------

        change_scale = (
            delta.abs()
            .rolling(
                window=10,
                min_periods=1
            )
            .mean()
        )

        change_scale = (
            change_scale
            .replace(0, np.nan)
        )

        normalized_change = (
            delta.abs()
            / change_scale
        )

        normalized_change = (
            normalized_change
            .replace(
                [np.inf, -np.inf],
                np.nan
            )
            .fillna(0.0)
        )

        instability_penalty = (
            normalized_change
            /
            (
                1.0
                + normalized_change
            )
        )

        # ----------------------------------------------------
        # Variability penalty
        # ----------------------------------------------------

        variability_scale = (
            rolling_std
            /
            (
                values.abs()
                .rolling(
                    window=10,
                    min_periods=1
                )
                .mean()
                .replace(
                    0,
                    np.nan
                )
            )
        )

        variability_scale = (
            variability_scale
            .replace(
                [np.inf, -np.inf],
                np.nan
            )
            .fillna(0.0)
        )

        variability_penalty = (
            variability_scale
            /
            (
                1.0
                + variability_scale
            )
        )

        # ----------------------------------------------------
        # Reliability
        # ----------------------------------------------------

        reliability = (
            valid_signal
            *
            (
                1.0
                - 0.60
                * instability_penalty
                - 0.40
                * variability_penalty
            )
        )

        reliability = reliability.clip(
            0.05,
            1.0
        )

        reliability_column = (
            f"{sensor_name}_reliability"
        )

        out[
            reliability_column
        ] = reliability

        reliability_columns.append(
            reliability_column
        )

    # ========================================================
    # OVERALL SENSOR RELIABILITY
    # ========================================================

    reliability_matrix = out[
        reliability_columns
    ]

    out[
        "overall_sensor_reliability"
    ] = reliability_matrix.mean(
        axis=1
    ).clip(
        0.05,
        1.0
    )

    # ========================================================
    # SENSOR AGREEMENT
    # ========================================================

    signal_columns = []

    for sensor_name, column in SENSORS.items():

        if column not in out.columns:
            continue

        values = safe_numeric(
            out,
            column
        )

        delta = (
            values
            .diff()
            .fillna(0.0)
        )

        # Direction of change
        signal_columns.append(
            np.sign(delta)
        )

    if signal_columns:

        signal_matrix = pd.concat(
            signal_columns,
            axis=1
        )

        # Agreement is based on how consistently
        # sensors move in the same direction.
        out[
            "sensor_agreement"
        ] = (
            signal_matrix
            .abs()
            .mean(axis=1)
        )

    else:

        out[
            "sensor_agreement"
        ] = 0.0

    # ========================================================
    # RELIABILITY-WEIGHTED SENSOR EVIDENCE
    # ========================================================

    weighted_evidence = []

    for sensor_name, column in SENSORS.items():

        reliability_column = (
            f"{sensor_name}_reliability"
        )

        delta_column = (
            f"{column}_delta"
        )

        if (
            reliability_column not in out.columns
            or delta_column not in out.columns
        ):
            continue

        delta = pd.to_numeric(
            out[
                delta_column
            ],
            errors="coerce"
        ).fillna(0.0)

        reliability = out[
            reliability_column
        ]

        weighted_evidence.append(
            delta.abs()
            * reliability
        )

    if weighted_evidence:

        evidence_matrix = pd.concat(
            weighted_evidence,
            axis=1
        )

        out[
            "reliability_weighted_change"
        ] = evidence_matrix.mean(
            axis=1
        )

    else:

        out[
            "reliability_weighted_change"
        ] = 0.0

    return out


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("SENSOR RELIABILITY ENGINE TEST")
    print("=" * 65)

    np.random.seed(42)

    timestamps = pd.date_range(
        "2026-09-01 09:00:00",
        periods=12,
        freq="10min"
    )

    df = pd.DataFrame({

        "timestamp": timestamps,

        "temperature_c": [
            24.0,
            24.1,
            24.2,
            24.3,
            24.4,
            24.5,
            24.6,
            24.7,
            24.8,
            24.9,
            25.0,
            25.1
        ],

        "humidity_pct": [
            70.0,
            70.2,
            70.1,
            70.3,
            70.2,
            70.4,
            70.5,
            70.3,
            70.4,
            70.5,
            70.6,
            70.5
        ],

        "gas_raw": [
            200,
            202,
            205,
            208,
            214,
            220,
            228,
            238,
            250,
            265,
            282,
            300
        ],

        "weight_g": [
            150.0,
            149.95,
            149.90,
            149.85,
            149.80,
            149.75,
            149.70,
            149.65,
            149.60,
            149.55,
            149.50,
            149.45
        ]
    })

    result = calculate_sensor_reliability(
        df
    )

    print(
        "\nReliability features:"
    )

    print("-" * 65)

    reliability_features = [

        "temperature_reliability",
        "humidity_reliability",
        "gas_reliability",
        "weight_reliability",
        "overall_sensor_reliability",
        "sensor_agreement",
        "reliability_weighted_change"

    ]

    for feature in reliability_features:

        if feature in result.columns:

            print(
                f"✓ {feature}"
            )

    print(
        "\nFinal observation:"
    )

    print(
        result.iloc[-1][
            reliability_features
        ]
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "SENSOR RELIABILITY ENGINE TEST COMPLETE"
    )

    print(
        "=" * 65
    )