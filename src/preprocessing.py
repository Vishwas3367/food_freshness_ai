import pandas as pd


# Canonical sensor columns used throughout the project
SENSOR_COLS = [
    "temperature_c",
    "humidity_pct",
    "gas_raw",
    "weight_g"
]


def load_data(path):
    """
    Load food-freshness sensor data from a CSV file.

    The input is expected to contain:
        timestamp
        food_type
        temperature_c
        humidity_pct
        gas_raw
        weight_g
        storage_day
    """

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(
            "Sensor data file is empty."
        )

    # Required columns
    required_columns = [
        "timestamp",
        "food_type",
        "temperature_c",
        "humidity_pct",
        "gas_raw",
        "weight_g",
        "storage_day"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    # Convert timestamp
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    # Convert sensor values to numeric
    numeric_columns = SENSOR_COLS + [
        "storage_day"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Remove rows without timestamp or food type
    df = df.dropna(
        subset=[
            "timestamp",
            "food_type"
        ]
    )

    # Remove empty food-type strings
    df["food_type"] = (
        df["food_type"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["food_type"] != ""
    ]

    # Sort chronologically within each food type
    df = df.sort_values(
        [
            "food_type",
            "timestamp"
        ]
    )

    # Reset index
    df = df.reset_index(
        drop=True
    )

    return df


def clean_data(df):
    """
    Clean and validate food-freshness sensor data.

    Missing sensor values are interpolated within each
    food type. Physically invalid sensor values are
    converted to missing values before interpolation.
    """

    df = df.copy()

    # --------------------------------------------------
    # 1. Validate physically meaningful sensor ranges
    # --------------------------------------------------

    # Temperature
    df.loc[
        (df["temperature_c"] < -40) |
        (df["temperature_c"] > 85),
        "temperature_c"
    ] = pd.NA

    # Relative humidity
    df.loc[
        (df["humidity_pct"] < 0) |
        (df["humidity_pct"] > 100),
        "humidity_pct"
    ] = pd.NA

    # Gas sensor response
    df.loc[
        df["gas_raw"] < 0,
        "gas_raw"
    ] = pd.NA

    # Weight
    df.loc[
        df["weight_g"] < 0,
        "weight_g"
    ] = pd.NA

    # Storage day
    df.loc[
        df["storage_day"] < 0,
        "storage_day"
    ] = pd.NA

    # --------------------------------------------------
    # 2. Interpolate missing values by food type
    # --------------------------------------------------

    for column in SENSOR_COLS + ["storage_day"]:

        df[column] = (
            df.groupby("food_type")[column]
            .transform(
                lambda series:
                series.interpolate(
                    limit_direction="both"
                )
            )
        )

    # --------------------------------------------------
    # 3. Remove rows still containing missing values
    # --------------------------------------------------

    df = df.dropna(
        subset=SENSOR_COLS + ["storage_day"]
    )

    # --------------------------------------------------
    # 4. Remove duplicate measurements
    # --------------------------------------------------

    df = df.drop_duplicates(
        subset=[
            "food_type",
            "timestamp"
        ],
        keep="last"
    )

    # --------------------------------------------------
    # 5. Sort again after cleaning
    # --------------------------------------------------

    df = df.sort_values(
        [
            "food_type",
            "timestamp"
        ]
    )

    # --------------------------------------------------
    # 6. Reset index
    # --------------------------------------------------

    df = df.reset_index(
        drop=True
    )

    return df