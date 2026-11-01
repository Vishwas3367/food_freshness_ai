import numpy as np
import pandas as pd


# ============================================================
# REQUIRED SENSOR COLUMNS
# ============================================================

BASELINE_COLUMNS = [
    "temperature_c",
    "humidity_pct",
    "gas_raw",
    "weight_g"
]


# ============================================================
# COLUMN ALIAS SUPPORT
# ============================================================

COLUMN_ALIASES = {

    "temperature_c": [
        "temperature_c",
        "temperature",
        "temp_c"
    ],

    "humidity_pct": [
        "humidity_pct",
        "humidity_percent",
        "humidity",
        "relative_humidity"
    ],

    "gas_raw": [
        "gas_raw",
        "gas",
        "gas_mean_external"
    ],

    "weight_g": [
        "weight_g",
        "mcurrent",
        "current_weight_g",
        "current_weight"
    ]
}


# ============================================================
# FIND COLUMN
# ============================================================

def find_column(df, target):

    if target not in COLUMN_ALIASES:
        return None

    for column in COLUMN_ALIASES[target]:

        if column in df.columns:
            return column

    return None


# ============================================================
# NORMALIZE SENSOR COLUMNS
# ============================================================

def normalize_baseline_columns(df):

    data = df.copy()

    for target in BASELINE_COLUMNS:

        source = find_column(
            data,
            target
        )

        if source is not None:

            data[target] = pd.to_numeric(
                data[source],
                errors="coerce"
            )

    return data


# ============================================================
# CALCULATE SINGLE BASELINE
# ============================================================

def calculate_baseline(
    df,
    baseline_fraction=0.30,
    min_observations=3
):
    """
    Calculate an automatic individual baseline.

    The baseline is calculated from the earliest stable
    portion of the observations.

    This avoids requiring:
        - harvest date
        - purchase date
        - known age of food

    Parameters
    ----------
    df : pandas.DataFrame

    baseline_fraction : float
        Fraction of observations used for baseline.

    min_observations : int
        Minimum observations required.

    Returns
    -------
    dict
    """

    if df is None or len(df) == 0:

        raise ValueError(
            "Cannot calculate baseline from empty data."
        )

    data = normalize_baseline_columns(
        df
    )

    observation_count = len(data)

    baseline_count = max(
        min_observations,
        int(
            np.ceil(
                observation_count
                * baseline_fraction
            )
        )
    )

    baseline_count = min(
        baseline_count,
        observation_count
    )

    baseline_data = data.iloc[
        :baseline_count
    ]

    baseline = {}

    for column in BASELINE_COLUMNS:

        if column not in baseline_data.columns:
            continue

        values = pd.to_numeric(
            baseline_data[column],
            errors="coerce"
        ).dropna()

        if len(values) == 0:
            continue

        baseline[column] = float(
            values.median()
        )

    if not baseline:

        raise ValueError(
            "No usable sensor columns found "
            "for baseline calculation."
        )

    return baseline


# ============================================================
# INDIVIDUAL BASELINE
# ============================================================

def calculate_individual_baseline(
    df,
    session_column="session_id",
    baseline_fraction=0.30,
    min_observations=3
):
    """
    Calculate a separate baseline for every food session/item.

    If session_id exists:

        session A -> baseline A
        session B -> baseline B
        session C -> baseline C

    If no session column exists, a single baseline is returned.
    """

    data = normalize_baseline_columns(
        df
    )

    if session_column not in data.columns:

        return {
            "global": calculate_baseline(
                data,
                baseline_fraction,
                min_observations
            )
        }

    baselines = {}

    for session_id, group in data.groupby(
        session_column,
        sort=False
    ):

        baselines[str(session_id)] = (
            calculate_baseline(
                group,
                baseline_fraction,
                min_observations
            )
        )

    return baselines


# ============================================================
# ADD BASELINE FEATURES
# ============================================================

def add_baseline_features(
    df,
    baseline=None,
    session_column="session_id"
):
    """
    Add baseline-relative features.

    Features:

        *_baseline_deviation
        *_relative_change

    If session-specific baselines are supplied,
    each observation is compared against its own session.
    """

    data = normalize_baseline_columns(
        df
    )

    # --------------------------------------------------------
    # No baseline supplied
    # --------------------------------------------------------

    if baseline is None:

        baseline = calculate_baseline(
            data
        )

    # --------------------------------------------------------
    # Session-specific baseline
    # --------------------------------------------------------

    session_based = (
        session_column in data.columns
        and isinstance(baseline, dict)
        and any(
            isinstance(value, dict)
            for value in baseline.values()
        )
    )

    for column in BASELINE_COLUMNS:

        if column not in data.columns:
            continue

        values = pd.to_numeric(
            data[column],
            errors="coerce"
        )

        # ====================================================
        # SESSION BASELINE
        # ====================================================

        if session_based:

            baseline_values = pd.Series(
                np.nan,
                index=data.index,
                dtype=float
            )

            for session_id, indices in data.groupby(
                session_column
            ).groups.items():

                session_key = str(
                    session_id
                )

                if session_key not in baseline:
                    continue

                session_baseline = baseline[
                    session_key
                ].get(
                    column
                )

                if session_baseline is None:
                    continue

                baseline_values.loc[
                    indices
                ] = session_baseline

        # ====================================================
        # GLOBAL BASELINE
        # ====================================================

        else:

            if column not in baseline:
                continue

            baseline_value = baseline[
                column
            ]

            baseline_values = pd.Series(
                baseline_value,
                index=data.index,
                dtype=float
            )

        # ====================================================
        # FEATURES
        # ====================================================

        deviation_column = (
            f"{column}_baseline_deviation"
        )

        relative_column = (
            f"{column}_relative_change"
        )

        data[
            deviation_column
        ] = (
            values
            - baseline_values
        )

        denominator = (
            baseline_values
            .replace(0, np.nan)
        )

        data[
            relative_column
        ] = (
            (
                values
                - baseline_values
            )
            / denominator
        )

    return data


# ============================================================
# CREATE SESSION ID
# ============================================================

def create_session_ids(
    df,
    food_column="food_type",
    item_column=None
):
    """
    Create a session identifier when one does not already exist.

    This is a software-side preparation for the future ESP32/cloud
    architecture.

    Example:

        tomato_001
        tomato_002
        banana_001
    """

    data = df.copy()

    if "session_id" in data.columns:
        return data

    if item_column is not None and item_column in data.columns:

        data["session_id"] = (
            data[food_column]
            .astype(str)
            + "_"
            + data[item_column]
            .astype(str)
        )

        return data

    if food_column not in data.columns:

        data["session_id"] = "session_001"

        return data

    # --------------------------------------------------------
    # Current software prototype:
    # one session per food type
    # --------------------------------------------------------

    counters = {}

    session_ids = []

    for food in data[
        food_column
    ].astype(str):

        food_key = food.lower()

        if food_key not in counters:
            counters[food_key] = 1

        session_ids.append(
            f"{food_key}_{counters[food_key]:03d}"
        )

    # For a dataframe representing a continuous stream,
    # all rows of the same food should normally belong to
    # the same session. Therefore, create stable IDs.

    stable_ids = {}

    final_ids = []

    for food in data[
        food_column
    ].astype(str):

        food_key = food.lower()

        if food_key not in stable_ids:

            stable_ids[food_key] = (
                f"{food_key}_001"
            )

        final_ids.append(
            stable_ids[food_key]
        )

    data[
        "session_id"
    ] = final_ids

    return data


# ============================================================
# BASELINE FEATURE SUMMARY
# ============================================================

def baseline_summary(
    baseline
):
    """
    Produce a clean printable baseline summary.
    """

    lines = []

    for key, value in baseline.items():

        if isinstance(value, dict):

            lines.append(
                f"{key}:"
            )

            for sensor, sensor_value in value.items():

                if sensor_value is None:
                    continue

                lines.append(
                    f"  {sensor}: "
                    f"{sensor_value:.4f}"
                )

        else:

            lines.append(
                f"{key}: {value:.4f}"
            )

    return "\n".join(
        lines
    )

# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def print_baseline(baseline):
    """
    Print the automatic individual baseline.
    """

    print("\nAutomatic Individual Baseline")
    print("----------------------------------------")

    for sensor, value in baseline.items():

        if value is None:
            continue

        if isinstance(
            value,
            (
                int,
                float,
                np.integer,
                np.floating
            )
        ):

            print(
                f"{sensor}: {float(value):.4f}"
            )

        else:

            print(
                f"{sensor}: {value}"
            )
# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("INDIVIDUAL BASELINE MANAGER TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Test data
    # --------------------------------------------------------

    np.random.seed(42)

    rows = []

    for food in [
        "tomato",
        "banana"
    ]:

        for i in range(10):

            rows.append({

                "food_type": food,

                "session_id":
                    f"{food}_001",

                "temperature_c":
                    25
                    + np.random.normal(
                        0,
                        0.2
                    ),

                "humidity_pct":
                    70
                    + np.random.normal(
                        0,
                        1.5
                    ),

                "gas_raw":
                    200
                    + i * 5
                    + np.random.normal(
                        0,
                        2
                    ),

                "weight_g":
                    150
                    - i * 0.2
                    + np.random.normal(
                        0,
                        0.03
                    )
            })

    df = pd.DataFrame(
        rows
    )

    print(
        "\nSensor data created:"
    )

    print(
        f"Rows: {len(df)}"
    )

    # --------------------------------------------------------
    # Individual baselines
    # --------------------------------------------------------

    baselines = calculate_individual_baseline(
        df,
        session_column="session_id"
    )

    print(
        "\nIndividual Session Baselines"
    )

    print("-" * 40)

    for session, baseline in baselines.items():

        print(
            f"\n{session}"
        )

        for key, value in baseline.items():

            print(
                f"{key}: {value:.4f}"
            )

    # --------------------------------------------------------
    # Baseline features
    # --------------------------------------------------------

    featured = add_baseline_features(
        df,
        baselines,
        session_column="session_id"
    )

    print(
        "\nBaseline Features Created"
    )

    print("-" * 40)

    feature_columns = [

        "temperature_c_baseline_deviation",
        "temperature_c_relative_change",

        "humidity_pct_baseline_deviation",
        "humidity_pct_relative_change",

        "gas_raw_baseline_deviation",
        "gas_raw_relative_change",

        "weight_g_baseline_deviation",
        "weight_g_relative_change"

    ]

    for column in feature_columns:

        if column in featured.columns:

            print(
                f"✓ {column}"
            )

    print(
        "\nLast observation:"
    )

    print(
        featured.iloc[-1][
            [
                "food_type",
                "session_id",
                "temperature_c",
                "humidity_pct",
                "gas_raw",
                "weight_g"
            ]
        ]
    )

    print(
        "\nBaseline-relative condition:"
    )

    print(
        featured.iloc[-1][
            feature_columns
        ]
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "INDIVIDUAL BASELINE TEST COMPLETE"
    )

    print(
        "=" * 60
    )