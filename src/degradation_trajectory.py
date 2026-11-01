import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_WINDOW = 10


# ============================================================
# SAFE COLUMN ACCESS
# ============================================================

def safe_series(df, column, default=0.0):

    if column in df.columns:

        return pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(default)

    return pd.Series(
        default,
        index=df.index,
        dtype=float
    )


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_signal(
    series,
    lower=0.0,
    upper=1.0
):
    """
    Convert a signal to the range 0-1.
    """

    values = pd.to_numeric(
        series,
        errors="coerce"
    ).fillna(0.0)

    if upper <= lower:

        return pd.Series(
            0.0,
            index=values.index
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
# ENSURE COMPATIBILITY WITH TEMPORAL FEATURES
# ============================================================

def ensure_trajectory_inputs(df):

    out = df.copy()

    # --------------------------------------------------------
    # Gas change
    # --------------------------------------------------------

    if "gas_raw_delta" in out.columns:

        out["gas_change"] = out[
            "gas_raw_delta"
        ]

    elif "gas_change" not in out.columns:

        if "gas_raw" in out.columns:

            out["gas_change"] = (
                pd.to_numeric(
                    out["gas_raw"],
                    errors="coerce"
                )
                .diff()
                .fillna(0.0)
            )

        else:

            out["gas_change"] = 0.0

    # --------------------------------------------------------
    # Gas acceleration
    # --------------------------------------------------------

    if "gas_raw_acceleration" in out.columns:

        out["gas_acceleration"] = out[
            "gas_raw_acceleration"
        ]

    elif "gas_acceleration" not in out.columns:

        out["gas_acceleration"] = (
            out["gas_change"]
            .diff()
            .fillna(0.0)
        )

    # --------------------------------------------------------
    # Weight change
    # --------------------------------------------------------

    if "weight_g_delta" in out.columns:

        out["weight_change"] = out[
            "weight_g_delta"
        ]

    elif "weight_change" not in out.columns:

        if "weight_g" in out.columns:

            out["weight_change"] = (
                pd.to_numeric(
                    out["weight_g"],
                    errors="coerce"
                )
                .diff()
                .fillna(0.0)
            )

        else:

            out["weight_change"] = 0.0

    # --------------------------------------------------------
    # Weight acceleration
    # --------------------------------------------------------

    if "weight_g_acceleration" in out.columns:

        out["weight_acceleration"] = out[
            "weight_g_acceleration"
        ]

    elif "weight_acceleration" not in out.columns:

        out["weight_acceleration"] = (
            out["weight_change"]
            .diff()
            .fillna(0.0)
        )

    # --------------------------------------------------------
    # Gas increase
    # --------------------------------------------------------

    if "gas_increase" not in out.columns:

        out["gas_increase"] = np.maximum(
            out["gas_change"],
            0.0
        )

    # --------------------------------------------------------
    # Weight loss
    # --------------------------------------------------------

    if "weight_loss" not in out.columns:

        out["weight_loss"] = np.maximum(
            -out["weight_change"],
            0.0
        )

    return out


# ============================================================
# ADD DEGRADATION TRAJECTORY
# ============================================================

def add_trajectory_features(
    df,
    window=DEFAULT_WINDOW
):
    """
    Create degradation trajectory features.

    The trajectory is based on changes and trends in:
        - gas
        - weight
        - temperature
        - humidity

    It does not claim to be a biological spoilage equation.
    """

    out = ensure_trajectory_inputs(
        df
    )

    # ========================================================
    # GAS TRAJECTORY
    # ========================================================

    gas_change = safe_series(
        out,
        "gas_change"
    )

    gas_acceleration = safe_series(
        out,
        "gas_acceleration"
    )

    gas_increase = safe_series(
        out,
        "gas_increase"
    )

    # Rolling gas trend

    gas_trend = (
        gas_change
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    out[
        "gas_trajectory"
    ] = gas_trend

    # Gas acceleration trend

    out[
        "gas_acceleration_trend"
    ] = (
        gas_acceleration
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    # Positive gas trajectory

    gas_positive = np.maximum(
        gas_trend,
        0.0
    )

    gas_acceleration_positive = np.maximum(
        out[
            "gas_acceleration_trend"
        ],
        0.0
    )

    # ========================================================
    # WEIGHT TRAJECTORY
    # ========================================================

    weight_change = safe_series(
        out,
        "weight_change"
    )

    weight_acceleration = safe_series(
        out,
        "weight_acceleration"
    )

    weight_loss = safe_series(
        out,
        "weight_loss"
    )

    weight_trend = (
        weight_change
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    out[
        "weight_trajectory"
    ] = weight_trend

    out[
        "weight_acceleration_trend"
    ] = (
        weight_acceleration
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    weight_loss_positive = np.maximum(
        -weight_trend,
        0.0
    )

    weight_acceleration_positive = np.maximum(
        -out[
            "weight_acceleration_trend"
        ],
        0.0
    )

    # ========================================================
    # TEMPERATURE TRAJECTORY
    # ========================================================

    temperature = safe_series(
        out,
        "temperature_c"
    )

    temperature_delta = safe_series(
        out,
        "temperature_c_delta"
    )

    temperature_trend = (
        temperature_delta
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    out[
        "temperature_trajectory"
    ] = temperature_trend

    # ========================================================
    # HUMIDITY TRAJECTORY
    # ========================================================

    humidity = safe_series(
        out,
        "humidity_pct"
    )

    humidity_delta = safe_series(
        out,
        "humidity_pct_delta"
    )

    humidity_trend = (
        humidity_delta
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    out[
        "humidity_trajectory"
    ] = humidity_trend

    # ========================================================
    # GAS RELATIVE TRAJECTORY
    # ========================================================

    if "gas_raw_relative_change" in out.columns:

        gas_relative = safe_series(
            out,
            "gas_raw_relative_change"
        )

    else:

        gas_raw = safe_series(
            out,
            "gas_raw"
        )

        initial_gas = (
            gas_raw
            .iloc[0]
            if len(gas_raw) > 0
            else 0.0
        )

        if initial_gas != 0:

            gas_relative = (
                gas_raw - initial_gas
            ) / initial_gas

        else:

            gas_relative = pd.Series(
                0.0,
                index=out.index
            )

    out[
        "gas_relative_trajectory"
    ] = (
        gas_relative
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    # ========================================================
    # WEIGHT RELATIVE TRAJECTORY
    # ========================================================

    if "weight_g_relative_change" in out.columns:

        weight_relative = safe_series(
            out,
            "weight_g_relative_change"
        )

    else:

        weight_raw = safe_series(
            out,
            "weight_g"
        )

        initial_weight = (
            weight_raw
            .iloc[0]
            if len(weight_raw) > 0
            else 0.0
        )

        if initial_weight != 0:

            weight_relative = (
                weight_raw - initial_weight
            ) / initial_weight

        else:

            weight_relative = pd.Series(
                0.0,
                index=out.index
            )

    out[
        "weight_relative_trajectory"
    ] = (
        weight_relative
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    # ========================================================
    # NORMALIZED GAS SIGNAL
    # ========================================================

    gas_relative_signal = normalize_signal(
        out[
            "gas_relative_trajectory"
        ].abs(),
        0.0,
        0.50
    )

    gas_trend_signal = normalize_signal(
        gas_positive.abs(),
        0.0,
        10.0
    )

    gas_acceleration_signal = normalize_signal(
        gas_acceleration_positive.abs(),
        0.0,
        5.0
    )

    out[
        "gas_trajectory_signal"
    ] = (
        0.40
        * gas_relative_signal
        +
        0.40
        * gas_trend_signal
        +
        0.20
        * gas_acceleration_signal
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # NORMALIZED WEIGHT SIGNAL
    # ========================================================

    weight_relative_signal = normalize_signal(
        out[
            "weight_relative_trajectory"
        ].abs(),
        0.0,
        0.10
    )

    weight_trend_signal = normalize_signal(
        weight_loss_positive.abs(),
        0.0,
        1.0
    )

    weight_acceleration_signal = normalize_signal(
        weight_acceleration_positive.abs(),
        0.0,
        0.50
    )

    out[
        "weight_trajectory_signal"
    ] = (
        0.45
        * weight_relative_signal
        +
        0.35
        * weight_trend_signal
        +
        0.20
        * weight_acceleration_signal
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # ENVIRONMENT TRAJECTORY
    # ========================================================

    temperature_signal = normalize_signal(
        out[
            "temperature_trajectory"
        ].abs(),
        0.0,
        2.0
    )

    humidity_signal = normalize_signal(
        out[
            "humidity_trajectory"
        ].abs(),
        0.0,
        5.0
    )

    out[
        "environment_trajectory_signal"
    ] = (
        0.60
        * temperature_signal
        +
        0.40
        * humidity_signal
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # GAS-WEIGHT AGREEMENT
    # ========================================================

    gas_direction = np.sign(
        gas_trend
    )

    weight_direction = np.sign(
        weight_trend
    )

    # Gas increasing + weight decreasing
    agreement = (
        (
            gas_direction > 0
        )
        &
        (
            weight_direction < 0
        )
    ).astype(float)

    out[
        "gas_weight_trajectory_agreement"
    ] = agreement

    # ========================================================
    # COMBINED TRAJECTORY SCORE
    # ========================================================

    out[
        "trajectory_score"
    ] = (
        0.45
        * out[
            "gas_trajectory_signal"
        ]
        +
        0.30
        * out[
            "weight_trajectory_signal"
        ]
        +
        0.15
        * out[
            "environment_trajectory_signal"
        ]
        +
        0.10
        * out[
            "gas_weight_trajectory_agreement"
        ]
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # TRAJECTORY CHANGE
    # ========================================================

    out[
        "trajectory_change"
    ] = (
        out[
            "trajectory_score"
        ]
        .diff()
        .fillna(0.0)
    )

    # ========================================================
    # TRAJECTORY ACCELERATION
    # ========================================================

    out[
        "trajectory_acceleration"
    ] = (
        out[
            "trajectory_change"
        ]
        .diff()
        .fillna(0.0)
    )

    # ========================================================
    # TRAJECTORY STABILITY
    # ========================================================

    out[
        "trajectory_rolling_mean"
    ] = (
        out[
            "trajectory_score"
        ]
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
    )

    out[
        "trajectory_rolling_std"
    ] = (
        out[
            "trajectory_score"
        ]
        .rolling(
            window=window,
            min_periods=1
        )
        .std()
        .fillna(0.0)
    )

    # ========================================================
    # DEGRADATION DIRECTION
    # ========================================================

    out[
        "degradation_direction"
    ] = np.sign(
        out[
            "trajectory_change"
        ]
    )

    return out


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("DEGRADATION TRAJECTORY ENGINE TEST")
    print("=" * 65)

    gas_values = [
        200,
        202,
        205,
        209,
        214,
        220,
        228,
        238,
        250,
        265,
        282,
        300
    ]

    weight_values = [
        150.0,
        149.95,
        149.90,
        149.80,
        149.70,
        149.55,
        149.40,
        149.20,
        149.00,
        148.70,
        148.40,
        148.00
    ]

    temperature_values = [
        24.0,
        24.1,
        24.2,
        24.3,
        24.5,
        24.7,
        25.0,
        25.4,
        25.8,
        26.2,
        26.7,
        27.2
    ]

    humidity_values = [
        70.0,
        70.1,
        70.2,
        70.3,
        70.5,
        70.6,
        70.8,
        71.0,
        71.2,
        71.4,
        71.7,
        72.0
    ]

    df = pd.DataFrame({

        "timestamp": pd.date_range(
            "2026-09-01 09:00:00",
            periods=12,
            freq="10min"
        ),

        "temperature_c":
            temperature_values,

        "humidity_pct":
            humidity_values,

        "gas_raw":
            gas_values,

        "weight_g":
            weight_values
    })

    # Add the same type of temporal signals
    # that the real pipeline generates.

    df[
        "gas_raw_delta"
    ] = (
        df[
            "gas_raw"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "weight_g_delta"
    ] = (
        df[
            "weight_g"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "temperature_c_delta"
    ] = (
        df[
            "temperature_c"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "humidity_pct_delta"
    ] = (
        df[
            "humidity_pct"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "gas_raw_acceleration"
    ] = (
        df[
            "gas_raw_delta"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "weight_g_acceleration"
    ] = (
        df[
            "weight_g_delta"
        ]
        .diff()
        .fillna(0)
    )

    df[
        "gas_raw_relative_change"
    ] = (
        df[
            "gas_raw"
        ] - 200
    ) / 200

    df[
        "weight_g_relative_change"
    ] = (
        df[
            "weight_g"
        ] - 150
    ) / 150

    result = add_trajectory_features(
        df
    )

    print(
        "\nImportant trajectory features:"
    )

    features = [

        "gas_trajectory",
        "gas_acceleration_trend",
        "gas_trajectory_signal",

        "weight_trajectory",
        "weight_acceleration_trend",
        "weight_trajectory_signal",

        "temperature_trajectory",
        "humidity_trajectory",
        "environment_trajectory_signal",

        "gas_weight_trajectory_agreement",

        "trajectory_score",
        "trajectory_change",
        "trajectory_acceleration",

        "trajectory_rolling_mean",
        "trajectory_rolling_std",

        "degradation_direction"
    ]

    for feature in features:

        if feature in result.columns:

            print(
                f"✓ {feature}"
            )

    print(
        "\nTrajectory progression:"
    )

    print("-" * 65)

    print(
        result[
            [
                "gas_raw",
                "weight_g",
                "temperature_c",
                "gas_trajectory_signal",
                "weight_trajectory_signal",
                "environment_trajectory_signal",
                "gas_weight_trajectory_agreement",
                "trajectory_score"
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nFinal trajectory state:"
    )

    print(
        result.iloc[-1][
            [
                "trajectory_score",
                "trajectory_change",
                "trajectory_acceleration",
                "trajectory_rolling_mean",
                "trajectory_rolling_std",
                "degradation_direction"
            ]
        ]
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "DEGRADATION TRAJECTORY ENGINE TEST COMPLETE"
    )

    print(
        "=" * 65
    )