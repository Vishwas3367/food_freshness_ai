import numpy as np
import pandas as pd


def calculate_temperature_exposure(
    df,
    min_preferred=None,
    max_preferred=None,
    critical_temperature=None
):
    """
    Calculate temperature-history and thermal-exposure features.

    The module is food-independent.

    Temperature limits are supplied by the selected food profile.
    The function can work with timestamped sensor data and calculates
    exposure using elapsed time rather than simply counting readings.
    """

    if df is None or df.empty:
        raise ValueError(
            "Cannot calculate temperature exposure from empty data."
        )

    data = df.copy()

    if "temperature_c" not in data.columns:
        raise ValueError(
            "temperature_c column is required."
        )

    # ---------------------------------------------------------------
    # TEMPERATURE CLEANING
    # ---------------------------------------------------------------

    data["temperature_c"] = pd.to_numeric(
        data["temperature_c"],
        errors="coerce"
    )

    # ---------------------------------------------------------------
    # TIMESTAMP HANDLING
    # ---------------------------------------------------------------

    timestamp_column = None

    possible_timestamp_columns = [
        "timestamp",
        "datetime",
        "date_time",
        "time"
    ]

    for column in possible_timestamp_columns:
        if column in data.columns:
            timestamp_column = column
            break

    if timestamp_column is not None:

        data[timestamp_column] = pd.to_datetime(
            data[timestamp_column],
            errors="coerce"
        )

        data = data.sort_values(
            timestamp_column
        ).reset_index(drop=True)

        time_difference_seconds = (
            data[timestamp_column]
            .diff()
            .dt.total_seconds()
            .fillna(0)
        )

        # Prevent invalid negative time differences
        time_difference_seconds = (
            time_difference_seconds.clip(lower=0)
        )

    else:
        # If timestamps are unavailable, assume each row
        # represents one observation interval.
        #
        # This is only a fallback for software testing.
        time_difference_seconds = pd.Series(
            np.ones(len(data)),
            index=data.index
        )

    data["elapsed_seconds"] = time_difference_seconds

    data["elapsed_hours"] = (
        data["elapsed_seconds"] / 3600.0
    )

    # ---------------------------------------------------------------
    # BASIC TEMPERATURE HISTORY
    # ---------------------------------------------------------------

    temperature = data["temperature_c"]

    data["temperature_rolling_mean"] = (
        temperature
        .rolling(
            window=10,
            min_periods=1
        )
        .mean()
    )

    data["temperature_rolling_max"] = (
        temperature
        .rolling(
            window=10,
            min_periods=1
        )
        .max()
    )

    data["temperature_rolling_min"] = (
        temperature
        .rolling(
            window=10,
            min_periods=1
        )
        .min()
    )

    # ---------------------------------------------------------------
    # TEMPERATURE CHANGE
    # ---------------------------------------------------------------

    data["temperature_delta"] = (
        temperature
        .diff()
        .fillna(0)
    )

    data["temperature_rate"] = (
        data["temperature_delta"]
        .abs()
    )

    # ---------------------------------------------------------------
    # PREFERRED TEMPERATURE RANGE
    # ---------------------------------------------------------------

    if (
        min_preferred is not None
        and max_preferred is not None
    ):

        outside_range = (
            (temperature < min_preferred)
            |
            (temperature > max_preferred)
        )

        data["temperature_outside_range"] = (
            outside_range.astype(int)
        )

        # Exposure based on actual elapsed time
        exposure_seconds = (
            data["elapsed_seconds"]
            * outside_range.astype(float)
        )

        data["temperature_exposure_seconds"] = (
            exposure_seconds.cumsum()
        )

        data["temperature_exposure_hours"] = (
            data["temperature_exposure_seconds"]
            / 3600.0
        )

        # -----------------------------------------------------------
        # DISTANCE FROM PREFERRED RANGE
        # -----------------------------------------------------------

        distance_low = np.maximum(
            min_preferred - temperature,
            0
        )

        distance_high = np.maximum(
            temperature - max_preferred,
            0
        )

        thermal_deviation = (
            distance_low + distance_high
        )

        data["thermal_deviation"] = (
            thermal_deviation
        )

        # Time-weighted thermal stress
        thermal_stress_increment = (
            thermal_deviation
            * data["elapsed_hours"]
        )

        data["cumulative_thermal_stress"] = (
            thermal_stress_increment.cumsum()
        )

        data["thermal_stress"] = (
            thermal_deviation
            .rolling(
                window=10,
                min_periods=1
            )
            .mean()
        )

    else:

        data["temperature_outside_range"] = 0

        data["temperature_exposure_seconds"] = 0.0

        data["temperature_exposure_hours"] = 0.0

        data["thermal_deviation"] = 0.0

        data["cumulative_thermal_stress"] = 0.0

        data["thermal_stress"] = 0.0

    # ---------------------------------------------------------------
    # CRITICAL TEMPERATURE
    # ---------------------------------------------------------------

    if critical_temperature is not None:

        critical = (
            temperature > critical_temperature
        )

        data["critical_temperature_flag"] = (
            critical.astype(int)
        )

        critical_exposure_seconds = (
            data["elapsed_seconds"]
            * critical.astype(float)
        )

        data["critical_temperature_exposure_seconds"] = (
            critical_exposure_seconds.cumsum()
        )

        data["critical_temperature_exposure_hours"] = (
            data["critical_temperature_exposure_seconds"]
            / 3600.0
        )

    else:

        data["critical_temperature_flag"] = 0

        data["critical_temperature_exposure_seconds"] = 0.0

        data["critical_temperature_exposure_hours"] = 0.0

    # ---------------------------------------------------------------
    # TEMPERATURE TREND
    # ---------------------------------------------------------------

    data["temperature_trend"] = (
        temperature
        .rolling(
            window=10,
            min_periods=2
        )
        .apply(
            lambda x: np.polyfit(
                np.arange(len(x)),
                x,
                1
            )[0]
            if len(x) >= 2
            else 0.0,
            raw=True
        )
        .fillna(0)
    )

    # ---------------------------------------------------------------
    # THERMAL RISK SIGNAL
    # ---------------------------------------------------------------

    if (
        min_preferred is not None
        and max_preferred is not None
    ):

        # Combines current deviation with accumulated exposure.
        #
        # This is a feature for the ML model, NOT a direct
        # biological spoilage equation.

        exposure_component = (
            data["temperature_exposure_hours"]
        )

        stress_component = (
            data["cumulative_thermal_stress"]
        )

        data["thermal_risk_signal"] = (
            exposure_component
            + stress_component
        )

    else:

        data["thermal_risk_signal"] = 0.0

    return data


# -------------------------------------------------------------------
# Helper function
# -------------------------------------------------------------------

def get_temperature_exposure_summary(df):
    """
    Return a compact summary of the temperature history.
    """

    if df is None or df.empty:
        return {}

    summary = {}

    if "temperature_c" in df.columns:

        temperature = pd.to_numeric(
            df["temperature_c"],
            errors="coerce"
        ).dropna()

        if not temperature.empty:

            summary["current_temperature_c"] = float(
                temperature.iloc[-1]
            )

            summary["average_temperature_c"] = float(
                temperature.mean()
            )

            summary["minimum_temperature_c"] = float(
                temperature.min()
            )

            summary["maximum_temperature_c"] = float(
                temperature.max()
            )

    if "temperature_exposure_hours" in df.columns:

        summary["temperature_exposure_hours"] = float(
            df["temperature_exposure_hours"].iloc[-1]
        )

    if "critical_temperature_exposure_hours" in df.columns:

        summary["critical_temperature_exposure_hours"] = float(
            df[
                "critical_temperature_exposure_hours"
            ].iloc[-1]
        )

    if "cumulative_thermal_stress" in df.columns:

        summary["cumulative_thermal_stress"] = float(
            df[
                "cumulative_thermal_stress"
            ].iloc[-1]
        )

    if "thermal_risk_signal" in df.columns:

        summary["thermal_risk_signal"] = float(
            df[
                "thermal_risk_signal"
            ].iloc[-1]
        )

    return summary


# -------------------------------------------------------------------
# Standalone software test
# -------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 65)
    print("TEMPERATURE EXPOSURE MODULE TEST")
    print("=" * 65)

    # Temporary test data.
    # Later this will come from ESP32.
    test_data = pd.DataFrame({

        "timestamp": pd.date_range(
            start="2026-08-31 10:00:00",
            periods=12,
            freq="30min"
        ),

        "temperature_c": [
            24.0,
            24.5,
            25.0,
            26.0,
            27.5,
            29.0,
            30.0,
            31.0,
            30.5,
            29.0,
            27.0,
            26.0
        ]
    })

    print("\nTest observations:")
    print(len(test_data))

    # Example limits.
    # IMPORTANT:
    # These are test values only.
    # Later they will come from food_profiles.json.
    preferred_min = 18.0
    preferred_max = 25.0
    critical_temperature = 30.0

    result = calculate_temperature_exposure(
        test_data,
        min_preferred=preferred_min,
        max_preferred=preferred_max,
        critical_temperature=critical_temperature
    )

    print("\nTemperature exposure features:")
    print("-" * 65)

    features_to_show = [
        "temperature_c",
        "temperature_delta",
        "temperature_exposure_hours",
        "critical_temperature_flag",
        "critical_temperature_exposure_hours",
        "thermal_deviation",
        "cumulative_thermal_stress",
        "thermal_risk_signal"
    ]

    print(
        result[features_to_show].to_string(
            index=False
        )
    )

    summary = get_temperature_exposure_summary(
        result
    )

    print("\nTemperature History Summary:")
    print("-" * 65)

    for key, value in summary.items():

        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    print("\n" + "=" * 65)
    print("TEMPERATURE EXPOSURE TEST COMPLETE")
    print("=" * 65)