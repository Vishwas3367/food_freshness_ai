import os
import glob
import pandas as pd
import numpy as np


# ============================================================
# EXTERNAL DATASET CONFIGURATION
# ============================================================

EXTERNAL_DATA_DIR = "data/external_datasets"


# ============================================================
# COLUMN GROUPS
# ============================================================

# Common temperature column names
TEMPERATURE_COLUMNS = [
    "temperature_c",
    "temperature",
    "temp_c",
    "temp",
    "Temperature",
    "Temperature_C"
]

# Common humidity column names
HUMIDITY_COLUMNS = [
    "humidity_pct",
    "humidity",
    "relative_humidity",
    "rh",
    "RH",
    "Humidity"
]

# Common weight column names
INITIAL_WEIGHT_COLUMNS = [
    "initial_weight_g",
    "initial_weight",
    "minitial",
    "weight_initial",
    "m_initial"
]

CURRENT_WEIGHT_COLUMNS = [
    "current_weight_g",
    "current_weight",
    "mcurrent",
    "weight_current",
    "m_current"
]

# Common storage-time column names
STORAGE_DAY_COLUMNS = [
    "storage_day",
    "Storage Day",
    "storage_days",
    "day",
    "days",
    "Storage_Day"
]

# Common storage-condition column names
STORAGE_SCENARIO_COLUMNS = [
    "storage_scenario",
    "Storage Scenario",
    "storage_condition",
    "condition",
    "Storage_Condition"
]

# Common sample ID column names
SAMPLE_ID_COLUMNS = [
    "sample_id",
    "Sample ID",
    "sample",
    "Sample",
    "id",
    "ID"
]

# Common food-name column names
FOOD_TYPE_COLUMNS = [
    "food_type",
    "food",
    "Food",
    "food_name",
    "Food_Type",
    "fruit",
    "Fruit",
    "vegetable",
    "Vegetable"
]

# Known MQ sensor naming patterns.
# The adapter detects them automatically.
MQ_PREFIXES = (
    "mq",
    "MQ"
)

# Known VOC sensor columns from the Banana dataset.
VOC_COLUMNS = [
    "voc_tgs2620_response",
    "voc_tgs2602_response",
    "voc_sgp40_response"
]


# ============================================================
# BASIC HELPERS
# ============================================================

def find_column(df, candidates):
    """
    Return the first matching column from a list of candidates.
    Matching is case-insensitive after stripping whitespace.
    """

    normalized = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in candidates:
        key = str(candidate).strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def find_columns(df, candidates):
    """
    Return all matching columns from a list of candidates.
    """

    normalized = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    matches = []

    for candidate in candidates:
        key = str(candidate).strip().lower()

        if key in normalized:
            matches.append(normalized[key])

    return matches


def detect_mq_columns(df):
    """
    Automatically detect MQ sensor columns.

    Examples:
        MQ2
        MQ3
        MQ3_1
        MQ135
        mq135
        mq4
    """

    columns = []

    for column in df.columns:

        name = str(column).strip()

        if name.startswith(MQ_PREFIXES):
            remainder = name[2:]

            if remainder and any(
                character.isdigit()
                for character in remainder
            ):
                columns.append(column)

    return columns


def detect_voc_columns(df):
    """
    Detect known VOC-response columns.
    """

    columns = []

    for column in VOC_COLUMNS:

        actual = find_column(
            df,
            [column]
        )

        if actual is not None:
            columns.append(actual)

    return columns


# ============================================================
# LOAD DATASET
# ============================================================

def load_external_dataset(path):
    """
    Load an external research dataset.

    The original CSV is never modified.
    """

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"External dataset not found: {path}"
        )

    df = pd.read_csv(
        path,
        sep=None,
        engine="python",
        encoding="utf-8-sig"
    )

    # Remove accidental whitespace/BOM
    df.columns = (
        df.columns
        .astype(str)
        .str.replace(
            "\ufeff",
            "",
            regex=False
        )
        .str.strip()
    )

    return df


# ============================================================
# DATASET TYPE DETECTION
# ============================================================

def detect_dataset_type(df):
    """
    Detect the general type of external dataset
    from its available columns.

    This is intentionally generic and does not depend
    on a particular food name.
    """

    columns = set(
        str(column).strip().lower()
        for column in df.columns
    )

    has_food = any(
        str(column).strip().lower()
        in columns
        for column in FOOD_TYPE_COLUMNS
    )

    has_temperature = find_column(
        df,
        TEMPERATURE_COLUMNS
    ) is not None

    has_humidity = find_column(
        df,
        HUMIDITY_COLUMNS
    ) is not None

    has_initial_weight = find_column(
        df,
        INITIAL_WEIGHT_COLUMNS
    ) is not None

    has_current_weight = find_column(
        df,
        CURRENT_WEIGHT_COLUMNS
    ) is not None

    has_storage_day = find_column(
        df,
        STORAGE_DAY_COLUMNS
    ) is not None

    has_mq = len(
        detect_mq_columns(df)
    ) > 0

    has_voc = len(
        detect_voc_columns(df)
    ) > 0

    if has_mq and (
        has_initial_weight
        or has_current_weight
    ):
        return "multisensor_mq"

    if has_voc and (
        has_temperature
        or has_humidity
    ):
        return "multisensor_voc"

    if has_temperature or has_humidity:
        return "environmental_reference"

    if has_initial_weight or has_current_weight:
        return "weight_reference"

    if has_storage_day:
        return "storage_reference"

    if has_food:
        return "food_reference"

    return "general_reference"


# ============================================================
# VALIDATE DATASET
# ============================================================

def validate_external_dataset(df):
    """
    Validate that the dataset contains enough information
    to be useful as external reference data.

    No food-specific columns are required.
    """

    if df is None:
        raise ValueError(
            "Dataset is empty."
        )

    if len(df) == 0:
        raise ValueError(
            "Dataset contains zero rows."
        )

    if len(df.columns) == 0:
        raise ValueError(
            "Dataset contains no columns."
        )

    return True


# ============================================================
# FOOD INFORMATION
# ============================================================

def add_food_features(df):
    """
    Standardize food identity.

    If food type is unavailable, it remains NaN.
    The adapter never guesses the food.
    """

    data = df.copy()

    food_column = find_column(
        data,
        FOOD_TYPE_COLUMNS
    )

    if food_column is not None:

        data["food_type"] = (
            data[food_column]
            .astype("string")
            .str.strip()
        )

    else:

        data["food_type"] = pd.NA

    return data


# ============================================================
# SAMPLE INFORMATION
# ============================================================

def add_sample_features(df):
    """
    Standardize sample IDs.
    """

    data = df.copy()

    sample_column = find_column(
        data,
        SAMPLE_ID_COLUMNS
    )

    if sample_column is not None:

        data["sample_id"] = (
            data[sample_column]
            .astype("string")
            .str.strip()
        )

    else:

        data["sample_id"] = pd.NA

    return data


# ============================================================
# PROCESS WEIGHT INFORMATION
# ============================================================

def add_weight_features(df):
    """
    Calculate weight-loss features when weight information exists.

    If the dataset has no weight measurements, the output
    columns remain NaN.
    """

    data = df.copy()

    initial_column = find_column(
        data,
        INITIAL_WEIGHT_COLUMNS
    )

    current_column = find_column(
        data,
        CURRENT_WEIGHT_COLUMNS
    )

    if (
        initial_column is None
        or current_column is None
    ):

        data["weight_initial_external"] = np.nan
        data["weight_current_external"] = np.nan
        data["weight_loss_external"] = np.nan
        data["weight_loss_percent_external"] = np.nan

        return data

    initial = pd.to_numeric(
        data[initial_column],
        errors="coerce"
    )

    current = pd.to_numeric(
        data[current_column],
        errors="coerce"
    )

    data["weight_initial_external"] = initial
    data["weight_current_external"] = current

    data["weight_loss_external"] = (
        initial - current
    )

    data["weight_loss_percent_external"] = np.where(
        initial > 0,
        (
            data["weight_loss_external"]
            / initial
        ) * 100,
        np.nan
    )

    return data


# ============================================================
# PROCESS GAS / MQ INFORMATION
# ============================================================

def add_gas_features(df):
    """
    Automatically detect gas/MQ sensor columns.

    Original sensor readings are retained.

    Summary features:
        gas_mean_external
        gas_max_external
        gas_std_external

    No MQ sensor is converted into another sensor type.
    """

    data = df.copy()

    mq_columns = detect_mq_columns(
        data
    )

    for column in mq_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    if mq_columns:

        data["gas_mean_external"] = (
            data[mq_columns]
            .mean(axis=1)
        )

        data["gas_max_external"] = (
            data[mq_columns]
            .max(axis=1)
        )

        data["gas_std_external"] = (
            data[mq_columns]
            .std(axis=1)
        )

    else:

        data["gas_mean_external"] = np.nan
        data["gas_max_external"] = np.nan
        data["gas_std_external"] = np.nan

    # --------------------------------------------------------
    # VOC reference sensors
    # --------------------------------------------------------

    voc_columns = detect_voc_columns(
        data
    )

    for column in voc_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    if voc_columns:

        data["gas_voc_reference"] = (
            data[voc_columns]
            .mean(axis=1)
        )

        data["gas_voc_max_reference"] = (
            data[voc_columns]
            .max(axis=1)
        )

        data["gas_voc_std_reference"] = (
            data[voc_columns]
            .std(axis=1)
        )

    else:

        data["gas_voc_reference"] = np.nan
        data["gas_voc_max_reference"] = np.nan
        data["gas_voc_std_reference"] = np.nan

    return data


# ============================================================
# PROCESS STORAGE INFORMATION
# ============================================================

def add_storage_features(df):
    """
    Standardize storage-day and storage-condition information.
    """

    data = df.copy()

    storage_day_column = find_column(
        data,
        STORAGE_DAY_COLUMNS
    )

    if storage_day_column is not None:

        storage_day = pd.to_numeric(
            data[storage_day_column],
            errors="coerce"
        )

        data["storage_day_external"] = (
            storage_day
        )

    else:

        data["storage_day_external"] = np.nan

    storage_scenario_column = find_column(
        data,
        STORAGE_SCENARIO_COLUMNS
    )

    if storage_scenario_column is not None:

        data["storage_scenario"] = (
            data[storage_scenario_column]
            .astype("string")
            .str.strip()
        )

    else:

        data["storage_scenario"] = pd.NA

    return data


# ============================================================
# PROCESS ENVIRONMENTAL INFORMATION
# ============================================================

def add_environment_features(df):
    """
    Standardize temperature and humidity.

    Missing environmental measurements remain NaN.
    """

    data = df.copy()

    temperature_column = find_column(
        data,
        TEMPERATURE_COLUMNS
    )

    humidity_column = find_column(
        data,
        HUMIDITY_COLUMNS
    )

    if temperature_column is not None:

        data["temperature_c"] = pd.to_numeric(
            data[temperature_column],
            errors="coerce"
        )

    else:

        data["temperature_c"] = np.nan

    if humidity_column is not None:

        data["humidity_pct"] = pd.to_numeric(
            data[humidity_column],
            errors="coerce"
        )

    else:

        data["humidity_pct"] = np.nan

    return data


# ============================================================
# PROCESS REFERENCE TARGET / CLASS
# ============================================================

def add_reference_target_features(df):
    """
    Preserve an existing reference class or RSL value
    when the dataset provides one.

    The adapter does NOT create an RSL target from
    storage day because storage day is not automatically
    equivalent to remaining shelf life.
    """

    data = df.copy()

    # --------------------------------------------------------
    # Reference class
    # --------------------------------------------------------

    reference_class_column = find_column(
        data,
        [
            "reference_class",
            "Reference Class",
            "class",
            "Class",
            "ripeness_class",
            "freshness_class"
        ]
    )

    if reference_class_column is not None:

        data["reference_class"] = (
            data[reference_class_column]
        )

    else:

        data["reference_class"] = pd.NA

    # --------------------------------------------------------
    # RSL
    # --------------------------------------------------------

    rsl_column = find_column(
        data,
        [
            "rsl_days",
            "RSL",
            "rsl",
            "remaining_shelf_life",
            "remaining_shelf_life_days"
        ]
    )

    if rsl_column is not None:

        data["rsl_days"] = pd.to_numeric(
            data[rsl_column],
            errors="coerce"
        )

    else:

        data["rsl_days"] = np.nan

    return data


# ============================================================
# COMPLETE ADAPTER
# ============================================================

def prepare_external_dataset(path):
    """
    Complete generic processing pipeline.

    The dataset is identified from its columns rather than
    from its filename or food name.
    """

    df = load_external_dataset(
        path
    )

    validate_external_dataset(
        df
    )

    dataset_type = detect_dataset_type(
        df
    )

    df = add_food_features(
        df
    )

    df = add_sample_features(
        df
    )

    df = add_weight_features(
        df
    )

    df = add_gas_features(
        df
    )

    df = add_storage_features(
        df
    )

    df = add_environment_features(
        df
    )

    df = add_reference_target_features(
        df
    )

    df["external_dataset_type"] = (
        dataset_type
    )

    return df


# ============================================================
# DISCOVER DATASETS AUTOMATICALLY
# ============================================================

def discover_external_datasets(
    directory=EXTERNAL_DATA_DIR
):
    """
    Automatically find all CSV datasets inside
    data/external_datasets/.

    No dataset names need to be added to the code.
    """

    if not os.path.isdir(directory):

        return []

    paths = sorted(
        glob.glob(
            os.path.join(
                directory,
                "*.csv"
            )
        )
    )

    return paths


# ============================================================
# DATASET SUMMARY
# ============================================================

def print_dataset_summary(
    df,
    path
):
    """
    Print a compact validation summary.
    """

    dataset_type = (
        df["external_dataset_type"]
        .iloc[0]
        if len(df) > 0
        else "unknown"
    )

    print("\n" + "-" * 65)
    print(
        os.path.basename(path)
    )
    print("-" * 65)

    print(
        f"Dataset type: {dataset_type}"
    )

    print(
        f"Rows loaded: {len(df)}"
    )

    print(
        f"Columns available: {len(df.columns)}"
    )

    if df["food_type"].notna().any():

        print("\nFood type:")

        print(
            df["food_type"]
            .value_counts(
                dropna=False
            )
        )

    mq_columns = detect_mq_columns(
        df
    )

    if mq_columns:

        print(
            f"\nMQ sensors detected: "
            f"{len(mq_columns)}"
        )

        print(
            ", ".join(
                str(column)
                for column in mq_columns
            )
        )

        print("\nMQ gas-response example:")

        print(
            df[
                [
                    "gas_mean_external",
                    "gas_max_external",
                    "gas_std_external"
                ]
            ].head()
        )

    else:

        print(
            "\nMQ sensors detected: 0"
        )

    voc_columns = detect_voc_columns(
        df
    )

    if voc_columns:

        print(
            "\nVOC sensors detected: "
            f"{len(voc_columns)}"
        )

        print(
            ", ".join(
                str(column)
                for column in voc_columns
            )
        )

        print(
            "\nVOC reference example:"
        )

        print(
            df[
                [
                    "gas_voc_reference",
                    "gas_voc_max_reference",
                    "gas_voc_std_reference"
                ]
            ].head()
        )

    if df["weight_loss_external"].notna().any():

        print(
            "\nWeight-loss example:"
        )

        print(
            df[
                [
                    "weight_initial_external",
                    "weight_current_external",
                    "weight_loss_external",
                    "weight_loss_percent_external"
                ]
            ].head()
        )

    else:

        print(
            "\nWeight data: not available."
        )

    print(
        "\nTemperature available:",
        df["temperature_c"].notna().any()
    )

    print(
        "Humidity available:",
        df["humidity_pct"].notna().any()
    )

    print(
        "RSL target available:",
        df["rsl_days"].notna().any()
    )

    print(
        "Reference class available:",
        df["reference_class"].notna().any()
    )


# ============================================================
# TEST ALL DATASETS
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print(
        "GENERIC EXTERNAL RESEARCH DATASET ADAPTER TEST"
    )
    print("=" * 65)

    dataset_paths = (
        discover_external_datasets()
    )

    if not dataset_paths:

        print(
            "\nNo CSV datasets found in:"
        )

        print(
            EXTERNAL_DATA_DIR
        )

        raise SystemExit(1)

    successful = 0
    failed = 0

    for path in dataset_paths:

        print(
            f"\nLoading: "
            f"{os.path.basename(path)}"
        )

        try:

            df = prepare_external_dataset(
                path
            )

            print_dataset_summary(
                df,
                path
            )

            successful += 1

        except Exception as error:

            failed += 1

            print(
                "\nERROR:"
            )

            print(
                str(error)
            )

    print("\n" + "=" * 65)

    print(
        f"Datasets discovered: "
        f"{len(dataset_paths)}"
    )

    print(
        f"Datasets processed successfully: "
        f"{successful}"
    )

    print(
        f"Datasets failed: "
        f"{failed}"
    )

    if failed == 0:

        print(
            "\nExternal dataset adapter "
            "working successfully."
        )

    else:

        print(
            "\nSome external datasets "
            "could not be processed."
        )

    print("=" * 65)