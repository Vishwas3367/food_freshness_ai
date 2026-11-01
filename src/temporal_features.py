import numpy as np
import pandas as pd


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

SENSOR_COLUMNS = [
    "temperature_c",
    "humidity_pct",
    "gas_raw",
    "weight_g"
]


# ============================================================
# ADD TEMPORAL FEATURES
# ============================================================

def add_temporal_features(
    df,
    window=10,
    time_column="timestamp",
    baseline=None
):
    """
    Create temporal, rate, acceleration and rolling features.

    The module does not assume universal biological thresholds.

    It measures how the sensor signals change over time.

    Parameters
    ----------
    df : pandas.DataFrame

    window : int
        Rolling-window size.

    time_column : str
        Timestamp column.

    baseline : dict, optional
        Individual or global baseline.

    Returns
    -------
    pandas.DataFrame
    """

    data = df.copy()

    # --------------------------------------------------------
    # Validate / prepare timestamp
    # --------------------------------------------------------

    if time_column in data.columns:

        data[time_column] = pd.to_datetime(
            data[time_column],
            errors="coerce"
        )

        data = data.sort_values(
            time_column
        ).reset_index(
            drop=True
        )

        elapsed_minutes = (
            data[time_column]
            .diff()
            .dt.total_seconds()
            .div(60)
        )

        elapsed_minutes = (
            elapsed_minutes
            .fillna(0)
            .clip(lower=0)
        )

    else:

        elapsed_minutes = pd.Series(
            1.0,
            index=data.index
        )

    # Avoid division by zero.
    elapsed_minutes_safe = (
        elapsed_minutes
        .replace(0, np.nan)
    )

    elapsed_hours = (
        elapsed_minutes
        / 60.0
    )

    data[
        "elapsed_time_minutes"
    ] = elapsed_minutes

    data[
        "elapsed_time_hours"
    ] = elapsed_hours

    # --------------------------------------------------------
    # Sensor features
    # --------------------------------------------------------

    for column in SENSOR_COLUMNS:

        if column not in data.columns:
            continue

        values = pd.to_numeric(
            data[column],
            errors="coerce"
        )

        data[column] = values

        # ====================================================
        # CHANGE FROM PREVIOUS OBSERVATION
        # ====================================================

        delta = values.diff()

        data[
            f"{column}_delta"
        ] = delta.fillna(0)

        # ====================================================
        # ABSOLUTE CHANGE
        # ====================================================

        data[
            f"{column}_absolute_change"
        ] = delta.abs().fillna(0)

        # ====================================================
        # RATE OF CHANGE
        # ====================================================

        rate = (
            delta
            / elapsed_hours.replace(
                0,
                np.nan
            )
        )

        rate = rate.replace(
            [np.inf, -np.inf],
            np.nan
        )

        data[
            f"{column}_rate"
        ] = rate.fillna(0)

        # ====================================================
        # ABSOLUTE RATE
        # ====================================================

        data[
            f"{column}_absolute_rate"
        ] = (
            rate
            .abs()
            .fillna(0)
        )

        # ====================================================
        # ACCELERATION
        # ====================================================

        acceleration = (
            data[
                f"{column}_rate"
            ].diff()
        )

        data[
            f"{column}_acceleration"
        ] = acceleration.fillna(0)

        # ====================================================
        # ROLLING MEAN
        # ====================================================

        data[
            f"{column}_rolling_mean"
        ] = (
            values
            .rolling(
                window=window,
                min_periods=1
            )
            .mean()
        )

        # ====================================================
        # ROLLING STD
        # ====================================================

        data[
            f"{column}_rolling_std"
        ] = (
            values
            .rolling(
                window=window,
                min_periods=1
            )
            .std()
            .fillna(0)
        )

        # ====================================================
        # ROLLING MIN
        # ====================================================

        data[
            f"{column}_rolling_min"
        ] = (
            values
            .rolling(
                window=window,
                min_periods=1
            )
            .min()
        )

        # ====================================================
        # ROLLING MAX
        # ====================================================

        data[
            f"{column}_rolling_max"
        ] = (
            values
            .rolling(
                window=window,
                min_periods=1
            )
            .max()
        )

        # ====================================================
        # ROLLING RANGE
        # ====================================================

        data[
            f"{column}_rolling_range"
        ] = (
            data[
                f"{column}_rolling_max"
            ]
            -
            data[
                f"{column}_rolling_min"
            ]
        )

    # ========================================================
    # BASELINE-RELATIVE FEATURES
    # ========================================================

    if baseline is not None:

        for column in SENSOR_COLUMNS:

            if column not in data.columns:
                continue

            if column not in baseline:
                continue

            baseline_value = baseline[
                column
            ]

            if baseline_value is None:
                continue

            baseline_value = float(
                baseline_value
            )

            deviation_column = (
                f"{column}_baseline_deviation"
            )

            relative_column = (
                f"{column}_relative_change"
            )

            data[
                deviation_column
            ] = (
                data[column]
                - baseline_value
            )

            if baseline_value != 0:

                data[
                    relative_column
                ] = (
                    (
                        data[column]
                        - baseline_value
                    )
                    / baseline_value
                )

            else:

                data[
                    relative_column
                ] = 0.0

    # ========================================================
    # DIRECTIONAL CHANGE SCORES
    # ========================================================

    # Gas increasing can be a degradation signal.
    if "gas_raw_delta" in data.columns:

        data[
            "gas_increase"
        ] = np.maximum(
            data[
                "gas_raw_delta"
            ],
            0
        )

        data[
            "gas_decrease"
        ] = np.maximum(
            -data[
                "gas_raw_delta"
            ],
            0
        )

    else:

        data["gas_increase"] = 0.0
        data["gas_decrease"] = 0.0

    # Weight decrease can be a degradation signal.
    if "weight_g_delta" in data.columns:

        data[
            "weight_loss"
        ] = np.maximum(
            -data[
                "weight_g_delta"
            ],
            0
        )

        data[
            "weight_gain"
        ] = np.maximum(
            data[
                "weight_g_delta"
            ],
            0
        )

    else:

        data["weight_loss"] = 0.0
        data["weight_gain"] = 0.0

    # ========================================================
    # CHANGE SCORES
    # ========================================================

    if "gas_raw_absolute_change" in data.columns:

        gas_scale = (
            data[
                "gas_raw"
            ]
            .rolling(
                window=window,
                min_periods=1
            )
            .std()
            .replace(0, np.nan)
        )

        data[
            "gas_change_score"
        ] = (
            data[
                "gas_raw_absolute_change"
            ]
            / gas_scale
        ).replace(
            [np.inf, -np.inf],
            np.nan
        ).fillna(0)

    else:

        data[
            "gas_change_score"
        ] = 0.0

    if "weight_g_absolute_change" in data.columns:

        weight_scale = (
            data[
                "weight_g"
            ]
            .rolling(
                window=window,
                min_periods=1
            )
            .std()
            .replace(0, np.nan)
        )

        data[
            "weight_loss_score"
        ] = (
            data[
                "weight_loss"
            ]
            / weight_scale
        ).replace(
            [np.inf, -np.inf],
            np.nan
        ).fillna(0)

    else:

        data[
            "weight_loss_score"
        ] = 0.0

    if "temperature_c_absolute_change" in data.columns:

        data[
            "temperature_change_score"
        ] = data[
            "temperature_c_absolute_change"
        ]

    else:

        data[
            "temperature_change_score"
        ] = 0.0

    if "humidity_pct_absolute_change" in data.columns:

        data[
            "humidity_change_score"
        ] = data[
            "humidity_pct_absolute_change"
        ]

    else:

        data[
            "humidity_change_score"
        ] = 0.0

    # ========================================================
    # ACCELERATION SCORES
    # ========================================================

    if "gas_raw_acceleration" in data.columns:

        data[
            "gas_acceleration_score"
        ] = data[
            "gas_raw_acceleration"
        ].abs()

    else:

        data[
            "gas_acceleration_score"
        ] = 0.0

    if "weight_g_acceleration" in data.columns:

        data[
            "weight_acceleration_score"
        ] = data[
            "weight_g_acceleration"
        ].abs()

    else:

        data[
            "weight_acceleration_score"
        ] = 0.0

    # ========================================================
    # GAS-WEIGHT INTERACTION
    # ========================================================

    data[
        "gas_weight_interaction"
    ] = (
        data[
            "gas_change_score"
        ]
        *
        data[
            "weight_loss_score"
        ]
    )

    # ========================================================
    # ENVIRONMENT CHANGE
    # ========================================================

    environment_components = []

    if "temperature_c_absolute_change" in data.columns:

        environment_components.append(
            data[
                "temperature_c_absolute_change"
            ]
        )

    if "humidity_pct_absolute_change" in data.columns:

        environment_components.append(
            data[
                "humidity_pct_absolute_change"
            ]
        )

    if environment_components:

        environment_matrix = pd.concat(
            environment_components,
            axis=1
        )

        data[
            "environment_change_score"
        ] = environment_matrix.mean(
            axis=1
        )

    else:

        data[
            "environment_change_score"
        ] = 0.0

    return data


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("TEMPORAL FEATURE ENGINE TEST")
    print("=" * 65)

    timestamps = pd.date_range(
        "2026-09-01 09:00:00",
        periods=12,
        freq="10min"
    )

    df = pd.DataFrame({

        "timestamp": timestamps,

        "food_type": [
            "tomato"
        ] * 12,

        "temperature_c": [
            24.0,
            24.2,
            24.5,
            25.0,
            25.4,
            26.0,
            26.5,
            27.0,
            27.4,
            28.0,
            28.5,
            29.0
        ],

        "humidity_pct": [
            70.0,
            70.2,
            70.5,
            71.0,
            71.2,
            71.5,
            72.0,
            72.3,
            72.8,
            73.0,
            73.5,
            74.0
        ],

        "gas_raw": [
            200,
            202,
            205,
            209,
            214,
            220,
            228,
            238,
            250,
            264,
            280,
            300
        ],

        "weight_g": [
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
            146.9
        ]
    })

    baseline = {
        "temperature_c": 24.0,
        "humidity_pct": 70.0,
        "gas_raw": 200.0,
        "weight_g": 150.0
    }

    result = add_temporal_features(
        df,
        window=5,
        baseline=baseline
    )

    print(
        "\nRows:"
    )

    print(
        len(result)
    )

    print(
        "\nImportant temporal features:"
    )

    features = [
        "temperature_c_delta",
        "humidity_pct_delta",
        "gas_raw_delta",
        "weight_g_delta",

        "temperature_c_rate",
        "gas_raw_rate",
        "weight_g_rate",

        "gas_raw_acceleration",
        "weight_g_acceleration",

        "gas_increase",
        "weight_loss",

        "gas_change_score",
        "weight_loss_score",

        "gas_acceleration_score",
        "weight_acceleration_score",

        "gas_weight_interaction",
        "environment_change_score"
    ]

    for feature in features:

        if feature in result.columns:

            print(
                f"✓ {feature}"
            )

    print(
        "\nFinal observation:"
    )

    print(
        result.iloc[-1][
            [
                "temperature_c",
                "humidity_pct",
                "gas_raw",
                "weight_g",
                "gas_increase",
                "weight_loss",
                "gas_weight_interaction",
                "environment_change_score"
            ]
        ]
    )

    print(
        "\nBaseline-relative values:"
    )

    print(
        result.iloc[-1][
            [
                "temperature_c_baseline_deviation",
                "temperature_c_relative_change",
                "humidity_pct_baseline_deviation",
                "humidity_pct_relative_change",
                "gas_raw_baseline_deviation",
                "gas_raw_relative_change",
                "weight_g_baseline_deviation",
                "weight_g_relative_change"
            ]
        ]
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "TEMPORAL FEATURE ENGINE TEST COMPLETE"
    )

    print(
        "=" * 65
    )