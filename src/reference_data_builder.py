"""
Reference Data Builder
======================

Purpose
-------
Build a food-specific reference layer from external research datasets.

Important design rule:
    Missing sensor measurements are NEVER invented.

The builder records:
    - food type
    - source
    - available sensor coverage
    - storage information
    - gas statistics
    - weight statistics
    - temperature statistics
    - humidity statistics
    - freshness/ripeness information when available
    - reference confidence

This module is a REFERENCE layer.

It does not replace the real ESP32 sensor data.
It does not create synthetic RSL labels.
"""

import json
import os
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd


# ============================================================
# SETTINGS
# ============================================================

REFERENCE_FOLDER = "data/reference_data"

DEFAULT_SENSOR_COLUMNS = [
    "temperature_c",
    "humidity_percent",
    "gas_raw",
    "weight_g",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_numeric(series):
    """
    Convert a pandas series to numeric values safely.
    Invalid values become NaN.
    """
    return pd.to_numeric(
        series,
        errors="coerce"
    )


def _mean_if_available(series):
    """
    Return mean if usable numerical data exists.
    Otherwise return None.
    """
    values = _safe_numeric(series).dropna()

    if len(values) == 0:
        return None

    return float(values.mean())


def _min_if_available(series):
    values = _safe_numeric(series).dropna()

    if len(values) == 0:
        return None

    return float(values.min())


def _max_if_available(series):
    values = _safe_numeric(series).dropna()

    if len(values) == 0:
        return None

    return float(values.max())


def _std_if_available(series):
    values = _safe_numeric(series).dropna()

    if len(values) < 2:
        return None

    return float(values.std())


# ============================================================
# GAS COLUMN DETECTION
# ============================================================

def detect_gas_columns(df):
    """
    Detect gas/VOC columns.

    Supports:
        gas_raw
        gas_mean_external
        MQ2 ... MQ138
        VOC-style columns

    Returns
    -------
    list
        Detected gas-related columns.
    """

    gas_columns = []

    for column in df.columns:

        name = str(column).lower()

        if (
            name == "gas_raw"
            or name.startswith("mq")
            or "voc" in name
            or "gas" in name
        ):
            gas_columns.append(column)

    return gas_columns


# ============================================================
# SENSOR COVERAGE
# ============================================================

def calculate_sensor_coverage(df):
    """
    Determine which project sensor categories are actually
    represented in the dataset.

    Missing information remains False.
    """

    columns_lower = {
        str(column).lower()
        for column in df.columns
    }

    temperature_available = any(
        name in columns_lower
        for name in [
            "temperature_c",
            "temperature",
            "temp_c",
            "air_temperature_c",
        ]
    )

    humidity_available = any(
        name in columns_lower
        for name in [
            "humidity_percent",
            "humidity_pct",
            "humidity",
            "relative_humidity",
            "rh",
        ]
    )

    weight_available = any(
        name in columns_lower
        for name in [
            "weight_g",
            "mcurrent",
            "current_weight_g",
            "initial_weight_g",
            "minitial",
        ]
    )

    gas_columns = detect_gas_columns(df)

    gas_available = len(gas_columns) > 0

    storage_available = any(
        name in columns_lower
        for name in [
            "storage_day",
            "storage day",
            "storage_days",
            "timestamp",
        ]
    )

    return {
        "temperature": temperature_available,
        "humidity": humidity_available,
        "gas": gas_available,
        "weight": weight_available,
        "storage_time": storage_available,
    }


# ============================================================
# GAS SUMMARY
# ============================================================

def calculate_gas_statistics(df):
    """
    Calculate gas/VOC summary without assuming that all gas
    sensors are equivalent.

    For multiple MQ columns, each row is summarized using:
        mean
        maximum
        standard deviation
    """

    gas_columns = detect_gas_columns(df)

    if not gas_columns:

        return {
            "available": False,
            "columns": [],
            "mean": None,
            "minimum": None,
            "maximum": None,
            "std": None,
        }

    numeric_data = df[
        gas_columns
    ].apply(
        pd.to_numeric,
        errors="coerce"
    )

    row_mean = numeric_data.mean(
        axis=1
    )

    row_max = numeric_data.max(
        axis=1
    )

    row_std = numeric_data.std(
        axis=1
    )

    return {
        "available": True,
        "columns": [
            str(column)
            for column in gas_columns
        ],
        "mean": _mean_if_available(
            row_mean
        ),
        "minimum": _min_if_available(
            row_mean
        ),
        "maximum": _max_if_available(
            row_max
        ),
        "std": _mean_if_available(
            row_std
        ),
    }


# ============================================================
# WEIGHT SUMMARY
# ============================================================

def calculate_weight_statistics(df):
    """
    Calculate weight information when available.

    Supports the tomato dataset format:
        minitial
        mcurrent
    """

    initial_column = None
    current_column = None

    for column in df.columns:

        name = str(column).lower()

        if name in [
            "minitial",
            "initial_weight_g",
            "initial_weight",
        ]:
            initial_column = column

        if name in [
            "mcurrent",
            "current_weight_g",
            "weight_g",
            "current_weight",
        ]:
            current_column = column

    if current_column is None:

        return {
            "available": False,
            "initial_weight_mean_g": None,
            "current_weight_mean_g": None,
            "weight_loss_mean_g": None,
            "weight_loss_percent_mean": None,
        }

    current = _safe_numeric(
        df[current_column]
    )

    result = {
        "available": True,
        "initial_weight_mean_g": None,
        "current_weight_mean_g": float(
            current.mean()
        ) if current.notna().any() else None,
        "weight_loss_mean_g": None,
        "weight_loss_percent_mean": None,
    }

    if initial_column is not None:

        initial = _safe_numeric(
            df[initial_column]
        )

        loss = (
            initial - current
        )

        loss_percent = (
            loss
            / initial.replace(0, np.nan)
            * 100
        )

        result[
            "initial_weight_mean_g"
        ] = (
            float(initial.mean())
            if initial.notna().any()
            else None
        )

        result[
            "weight_loss_mean_g"
        ] = (
            float(loss.mean())
            if loss.notna().any()
            else None
        )

        result[
            "weight_loss_percent_mean"
        ] = (
            float(loss_percent.mean())
            if loss_percent.notna().any()
            else None
        )

    return result


# ============================================================
# TEMPERATURE SUMMARY
# ============================================================

def calculate_temperature_statistics(df):
    """
    Calculate temperature statistics only if temperature
    data actually exists.
    """

    possible_columns = [
        "temperature_c",
        "temperature",
        "temp_c",
        "air_temperature_c",
    ]

    column = None

    for candidate in possible_columns:

        for actual in df.columns:

            if str(actual).lower() == candidate:
                column = actual
                break

        if column is not None:
            break

    if column is None:

        return {
            "available": False,
            "mean_c": None,
            "minimum_c": None,
            "maximum_c": None,
            "std_c": None,
        }

    return {
        "available": True,
        "mean_c": _mean_if_available(
            df[column]
        ),
        "minimum_c": _min_if_available(
            df[column]
        ),
        "maximum_c": _max_if_available(
            df[column]
        ),
        "std_c": _std_if_available(
            df[column]
        ),
    }


# ============================================================
# HUMIDITY SUMMARY
# ============================================================

def calculate_humidity_statistics(df):
    """
    Calculate humidity statistics only when actual humidity
    observations exist.
    """

    possible_columns = [
        "humidity_percent",
        "humidity_pct",
        "humidity",
        "relative_humidity",
        "rh",
    ]

    column = None

    for candidate in possible_columns:

        for actual in df.columns:

            if str(actual).lower() == candidate:
                column = actual
                break

        if column is not None:
            break

    if column is None:

        return {
            "available": False,
            "mean_percent": None,
            "minimum_percent": None,
            "maximum_percent": None,
            "std_percent": None,
        }

    return {
        "available": True,
        "mean_percent": _mean_if_available(
            df[column]
        ),
        "minimum_percent": _min_if_available(
            df[column]
        ),
        "maximum_percent": _max_if_available(
            df[column]
        ),
        "std_percent": _std_if_available(
            df[column]
        ),
    }


# ============================================================
# STORAGE INFORMATION
# ============================================================

def calculate_storage_statistics(df):
    """
    Extract storage-day information if present.
    """

    possible_columns = [
        "storage_day",
        "storage day",
        "storage_days",
    ]

    column = None

    for candidate in possible_columns:

        for actual in df.columns:

            if str(actual).lower() == candidate:
                column = actual
                break

        if column is not None:
            break

    if column is None:

        return {
            "available": False,
            "minimum_day": None,
            "maximum_day": None,
            "mean_day": None,
        }

    values = _safe_numeric(
        df[column]
    )

    return {
        "available": True,
        "minimum_day": _min_if_available(
            values
        ),
        "maximum_day": _max_if_available(
            values
        ),
        "mean_day": _mean_if_available(
            values
        ),
    }


# ============================================================
# REFERENCE CONFIDENCE
# ============================================================

def calculate_reference_confidence(
    coverage,
    row_count
):
    """
    Calculate a transparent reference-coverage score.

    This is NOT model accuracy.

    It only describes how much of the desired reference
    information is actually present.

    The five core categories are:
        temperature
        humidity
        gas
        weight
        storage_time
    """

    categories = [
        "temperature",
        "humidity",
        "gas",
        "weight",
        "storage_time",
    ]

    available = sum(
        1
        for category in categories
        if coverage.get(category, False)
    )

    coverage_score = (
        available
        / len(categories)
    )

    # Small datasets receive a modest reduction.
    if row_count < 10:
        sample_factor = 0.50

    elif row_count < 30:
        sample_factor = 0.75

    elif row_count < 50:
        sample_factor = 0.90

    else:
        sample_factor = 1.00

    confidence = (
        coverage_score
        * sample_factor
    )

    return round(
        float(confidence),
        4
    )


# ============================================================
# BUILD REFERENCE RECORD
# ============================================================

def build_reference_record(
    df,
    food_type,
    source_name,
    source_path=None
):
    """
    Build one standardized reference record.

    No missing measurement is replaced by an estimated value.
    """

    if df is None:
        raise ValueError(
            "Dataset cannot be None."
        )

    if len(df) == 0:
        raise ValueError(
            "Dataset contains no rows."
        )

    coverage = calculate_sensor_coverage(
        df
    )

    gas = calculate_gas_statistics(
        df
    )

    weight = calculate_weight_statistics(
        df
    )

    temperature = (
        calculate_temperature_statistics(
            df
        )
    )

    humidity = (
        calculate_humidity_statistics(
            df
        )
    )

    storage = (
        calculate_storage_statistics(
            df
        )
    )

    reference_confidence = (
        calculate_reference_confidence(
            coverage,
            len(df)
        )
    )

    record = {

        "food_type": str(
            food_type
        ).lower(),

        "source": str(
            source_name
        ),

        "source_path": source_path,

        "row_count": int(
            len(df)
        ),

        "sensor_coverage": coverage,

        "reference_confidence": (
            reference_confidence
        ),

        "temperature": temperature,

        "humidity": humidity,

        "gas": gas,

        "weight": weight,

        "storage": storage,

        "freshness_labels_available": False,

        "rsl_available": False,

        "notes": (
            "Reference statistics are "
            "derived only from observed "
            "dataset fields. Missing "
            "measurements are not "
            "imputed."
        ),
    }

    return record


# ============================================================
# SAVE REFERENCE RECORD
# ============================================================

def save_reference_record(
    record,
    output_folder=REFERENCE_FOLDER
):
    """
    Save a reference record as JSON.
    """

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    food_type = (
        record["food_type"]
        .replace(" ", "_")
    )

    output_path = os.path.join(
        output_folder,
        f"{food_type}_reference.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            record,
            file,
            indent=4,
            allow_nan=False
        )

    return output_path


# ============================================================
# LOAD REFERENCE RECORD
# ============================================================

def load_reference_record(
    food_type,
    reference_folder=REFERENCE_FOLDER
):
    """
    Load a food-specific reference record.
    """

    food_type = (
        str(food_type)
        .lower()
        .replace(" ", "_")
    )

    path = os.path.join(
        reference_folder,
        f"{food_type}_reference.json"
    )

    if not os.path.exists(path):
        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# REFERENCE AVAILABILITY
# ============================================================

def get_reference_coverage(
    food_type,
    reference_folder=REFERENCE_FOLDER
):
    """
    Return reference coverage for a food.

    If no reference record exists, return a safe empty
    structure rather than failing.
    """

    record = load_reference_record(
        food_type,
        reference_folder
    )

    if record is None:

        return {
            "temperature": False,
            "humidity": False,
            "gas": False,
            "weight": False,
            "storage_time": False,
            "reference_confidence": 0.0,
        }

    coverage = record.get(
        "sensor_coverage",
        {}
    )

    return {
        "temperature": bool(
            coverage.get(
                "temperature",
                False
            )
        ),
        "humidity": bool(
            coverage.get(
                "humidity",
                False
            )
        ),
        "gas": bool(
            coverage.get(
                "gas",
                False
            )
        ),
        "weight": bool(
            coverage.get(
                "weight",
                False
            )
        ),
        "storage_time": bool(
            coverage.get(
                "storage_time",
                False
            )
        ),
        "reference_confidence": float(
            record.get(
                "reference_confidence",
                0.0
            )
        ),
    }


# ============================================================
# TEST WITH A CSV
# ============================================================

def build_reference_from_csv(
    csv_path,
    food_type,
    source_name=None
):
    """
    Load a CSV and create a reference record.
    """

    if not os.path.exists(csv_path):

        raise FileNotFoundError(
            f"Dataset not found: {csv_path}"
        )

    df = pd.read_csv(
        csv_path,
        sep=None,
        engine="python",
        encoding="utf-8-sig"
    )

    if source_name is None:
        source_name = os.path.basename(
            csv_path
        )

    record = build_reference_record(
        df=df,
        food_type=food_type,
        source_name=source_name,
        source_path=csv_path,
    )

    output_path = save_reference_record(
        record
    )

    return record, output_path


# ============================================================
# COMMAND-LINE TEST
# ============================================================

# ============================================================
# COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("REFERENCE DATA BUILDER TEST")
    print("=" * 65)

    external_folder = "data/external_datasets"

    if not os.path.isdir(external_folder):

        print(
            "\nExternal dataset folder not found:"
        )

        print(
            external_folder
        )

        raise SystemExit(1)

    # --------------------------------------------------------
    # Automatically discover all CSV datasets
    # --------------------------------------------------------

    csv_files = sorted(
        [
            os.path.join(
                external_folder,
                filename
            )
            for filename in os.listdir(
                external_folder
            )
            if filename.lower().endswith(".csv")
        ]
    )

    if not csv_files:

        print(
            "\nNo CSV datasets found in:"
        )

        print(
            external_folder
        )

        raise SystemExit(1)

    print(
        f"\nExternal datasets found: "
        f"{len(csv_files)}"
    )

    successful = 0
    failed = 0

    # --------------------------------------------------------
    # Process every external dataset
    # --------------------------------------------------------

    for csv_path in csv_files:

        filename = os.path.basename(
            csv_path
        )

        print("\n" + "-" * 65)

        print(
            f"Loading: {filename}"
        )

        print("-" * 65)

        try:

            df = pd.read_csv(
                csv_path,
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

            if len(df) == 0:

                raise ValueError(
                    "Dataset contains no rows."
                )

            # ------------------------------------------------
            # Determine food type
            # ------------------------------------------------

            food_type = None

            possible_food_columns = [
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

            for column in possible_food_columns:

                if column in df.columns:

                    values = (
                        df[column]
                        .dropna()
                        .astype(str)
                        .str.strip()
                    )

                    if len(values) > 0:

                        food_type = (
                            values.iloc[0]
                        )

                        break

            # ------------------------------------------------
            # If food type isn't inside CSV,
            # derive it from filename.
            # ------------------------------------------------

            if not food_type:

                filename_without_extension = (
                    os.path.splitext(
                        filename
                    )[0]
                )

                food_type = (
                    filename_without_extension
                    .replace(
                        "_reference_dataset",
                        ""
                    )
                    .replace(
                        "_dataset",
                        ""
                    )
                    .replace(
                        "_reference",
                        ""
                    )
                    .replace(
                        "-reference-dataset",
                        ""
                    )
                )

            food_type = (
                str(food_type)
                .strip()
                .lower()
            )

            # ------------------------------------------------
            # Build reference record
            # ------------------------------------------------

            record = build_reference_record(
                df=df,
                food_type=food_type,
                source_name=filename,
                source_path=csv_path
            )

            # ------------------------------------------------
            # Save JSON
            # ------------------------------------------------

            output_path = save_reference_record(
                record
            )

            # ------------------------------------------------
            # Display result
            # ------------------------------------------------

            print(
                f"\nFood type: {food_type}"
            )

            print(
                f"Rows processed: "
                f"{record['row_count']}"
            )

            print(
                "\nSensor coverage:"
            )

            for key, value in (
                record[
                    "sensor_coverage"
                ].items()
            ):

                print(
                    f"  {key}: {value}"
                )

            print(
                "\nReference confidence:"
            )

            print(
                record[
                    "reference_confidence"
                ]
            )

            print(
                "\nReference file created:"
            )

            print(
                output_path
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

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print("\n" + "=" * 65)

    print(
        f"External datasets found: "
        f"{len(csv_files)}"
    )

    print(
        f"Reference files created successfully: "
        f"{successful}"
    )

    print(
        f"Datasets failed: "
        f"{failed}"
    )

    if failed == 0:

        print(
            "\nREFERENCE DATA BUILDER "
            "WORKING SUCCESSFULLY."
        )

    else:

        print(
            "\nSome datasets could not "
            "be converted."
        )

    print("=" * 65)