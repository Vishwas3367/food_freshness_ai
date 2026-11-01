import os
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split

from src.preprocessing import load_data, clean_data

from src.food_profile import (
    list_available_foods,
    load_food_profile,
    get_temperature_limits,
)

from src.baseline_manager import (
    calculate_baseline,
    add_baseline_features,
    print_baseline,
)

from src.temperature_exposure import (
    calculate_temperature_exposure,
)

from src.temporal_features import add_temporal_features
from src.degradation_trajectory import add_trajectory_features
from src.degradation_state import calculate_state_features
from src.sensor_reliability import calculate_sensor_reliability
from src.disturbance_detection import calculate_disturbance_features
from src.adaptive_fusion import calculate_adaptive_fusion
from src.confidence_estimation import calculate_prediction_confidence

from src.baseline_xgboost import build_baseline
from src.proposed_model import build_proposed_model

from src.evaluation import (
    regression_metrics,
    freshness_class,
)

from src.shap_analysis import (
    create_shap_explanation,
    print_top_features,
)


# ============================================================
# SETTINGS
# ============================================================

DATA_PATH = "data/sensor_data.csv"
RESULTS_FOLDER = "results"


# ============================================================
# TEMPORARY SOFTWARE TEST DATA
# ============================================================

def create_sample_dataset():

    np.random.seed(42)

    # Food names now come from the database.
    foods = list_available_foods()

    if not foods:
        foods = ["tomato"]

    rows = []

    start_time = pd.Timestamp(
        "2026-08-29 09:00:00"
    )

    for food_index, food in enumerate(foods):

        for i in range(30):

            timestamp = (
                start_time
                + pd.Timedelta(
                    minutes=10 * i
                )
                + pd.Timedelta(
                    days=food_index
                )
            )

            # Temporary software-test values.
            # These are NOT real food measurements.
            temperature = (
                24
                + np.random.normal(0, 0.5)
            )

            humidity = (
                70
                + np.random.normal(0, 2)
            )

            gas = (
                200
                + i * 5
                + np.random.normal(0, 4)
            )

            weight = (
                150
                - i * 0.15
                + np.random.normal(0, 0.03)
            )

            storage_day = i / 6

            rows.append([
                timestamp,
                food,
                temperature,
                humidity,
                gas,
                weight,
                storage_day
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "food_type",
            "temperature_c",
            "humidity_pct",
            "gas_raw",
            "weight_g",
            "storage_day"
        ]
    )


# ============================================================
# TEMPORARY DEMO RSL TARGET
# ============================================================

def create_demo_rsl(df):

    np.random.seed(42)

    base_rsl = (
        8.0
        - 0.9 * df["storage_day"]
    )

    trajectory_effect = (
        0.8 * df["trajectory_score"]
    )

    thermal_effect = (
        0.05
        * df.get(
            "thermal_risk_signal",
            pd.Series(
                0.0,
                index=df.index
            )
        )
    )

    noise = np.random.normal(
        0,
        0.15,
        len(df)
    )

    rsl = (
        base_rsl
        - trajectory_effect
        - thermal_effect
        + noise
    )

    return np.clip(
        rsl,
        0,
        None
    )


# ============================================================
# FOOD-SPECIFIC TEMPERATURE EXPOSURE
# ============================================================

def apply_food_profile_temperature_exposure(df):
    """
    Calculate temperature exposure separately for every food.

    The selected food determines which validated temperature
    profile is used.

    If temperature limits are still null, the module still
    creates general temperature-history features.
    """

    outputs = []

    for food, group in df.groupby(
        "food_type",
        sort=False
    ):

        profile = load_food_profile(
            food
        )

        limits = get_temperature_limits(
            food
        )

        enriched = calculate_temperature_exposure(
            group,

            min_preferred=(
                limits["min_preferred"]
            ),

            max_preferred=(
                limits["max_preferred"]
            ),

            critical_temperature=(
                limits["critical"]
            )
        )

        outputs.append(
            enriched
        )

    result = pd.concat(
        outputs,
        ignore_index=True
    )

    if "timestamp" in result.columns:

        result = result.sort_values(
            [
                "food_type",
                "timestamp"
            ]
        ).reset_index(
            drop=True
        )

    return result


# ============================================================
# VALIDATE FOOD TYPES
# ============================================================

def validate_food_profiles(df):

    database_foods = set(
        list_available_foods()
    )

    dataset_foods = set(
        str(food).strip().lower()
        for food in
        df["food_type"].dropna().unique()
    )

    unknown_foods = (
        dataset_foods
        - database_foods
    )

    if unknown_foods:

        raise ValueError(
            "The following foods are not present "
            "in food_profiles.json: "
            + ", ".join(
                sorted(unknown_foods)
            )
        )

    for food in dataset_foods:

        load_food_profile(
            food
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")

    print(
        "=" * 70
    )

    print(
        " AI-BASED SMART FOOD FRESHNESS BOX"
    )

    print(
        " Adaptive Remaining Shelf-Life Prediction"
    )

    print(
        "=" * 70
    )


    # ========================================================
    # 1. LOAD DATA
    # ========================================================

    print(
        "\n[1] Loading sensor data..."
    )

    try:

        df = load_data(
            DATA_PATH
        )

        print(
            f"Loaded {len(df)} rows."
        )

    except Exception as error:

        print(
            "No usable real sensor data found."
        )

        print(
            "Creating temporary software-test data..."
        )

        print(
            f"Reason: {error}"
        )

        df = create_sample_dataset()


    # ========================================================
    # 2. CLEAN DATA
    # ========================================================

    print(
        "\n[2] Cleaning sensor data..."
    )

    df = clean_data(
        df
    )

    print(
        f"Clean dataset: {len(df)} rows."
    )


    # ========================================================
    # 3. VALIDATE FOOD PROFILE
    # ========================================================

    print(
        "\n[3] Loading food profiles..."
    )

    if "food_type" not in df.columns:

        raise ValueError(
            "food_type column is required."
        )

    validate_food_profiles(
        df
    )

    print(
        "Food profiles loaded:"
    )

    for food in sorted(
        df["food_type"]
        .dropna()
        .unique()
    ):

        profile = load_food_profile(
            food
        )

        print(
            f"  ✓ "
            f"{profile['display_name']}"
        )


    # ========================================================
    # 4. AUTOMATIC INDIVIDUAL BASELINE
    # ========================================================

    print(
        "\n[4] Calculating automatic individual baselines..."
    )

    baselines = calculate_baseline(
      df,
      baseline_fraction=0.30,
      min_observations=3
    )

    print_baseline(
        baselines
    )

    df = add_baseline_features(
        df,
        baselines
    )

    print(
        "Baseline-relative features created."
    )


    # ========================================================
    # 5. TEMPERATURE EXPOSURE
    # ========================================================

    print(
        "\n[5] Calculating temperature exposure/history..."
    )

    df = apply_food_profile_temperature_exposure(
        df
    )

    print(
        "Temperature-history features created."
    )


    # ========================================================
    # 6. TEMPORAL FEATURES
    # ========================================================

    print(
        "\n[6] Creating temporal features..."
    )

    df = add_temporal_features(
        df
    )

    print(
        "Temporal features created."
    )


    # ========================================================
    # 7. DEGRADATION TRAJECTORY
    # ========================================================

    print(
        "\n[7] Creating degradation trajectory..."
    )

    df = add_trajectory_features(
        df
    )

    print(
        "Degradation trajectory created."
    )


    # ========================================================
    # 8. DEGRADATION STATE
    # ========================================================

    print(
        "\n[8] Calculating degradation state..."
    )

    df = calculate_state_features(
        df
    )

    print(
        "Degradation state calculated."
    )


    # ========================================================
    # 9. SENSOR RELIABILITY
    # ========================================================

    print(
        "\n[9] Calculating sensor reliability..."
    )

    df = calculate_sensor_reliability(
        df
    )

    print(
        "Sensor reliability calculated."
    )


    # ========================================================
    # 10. DISTURBANCE DETECTION
    # ========================================================

    print(
        "\n[10] Detecting environmental disturbances..."
    )

    df = calculate_disturbance_features(
        df
    )

    print(
        "Disturbance analysis completed."
    )


    # ========================================================
    # 11. ADAPTIVE SENSOR FUSION
    # ========================================================

    print(
        "\n[11] Performing adaptive sensor fusion..."
    )

    df = calculate_adaptive_fusion(
        df
    )

    print(
        "Adaptive fusion completed."
    )


    # ========================================================
    # 12. TEMPORARY RSL TARGET
    # ========================================================

    print(
        "\n[12] Creating temporary RSL target..."
    )

    df["RSL_demo_days"] = (
        create_demo_rsl(
            df
        )
    )

    print(
        "WARNING: RSL target is synthetic."
    )

    print(
        "It is for software testing only."
    )


    # ========================================================
    # 13. FEATURE SETS
    # ========================================================

    baseline_features = [

        "temperature_c",
        "humidity_pct",
        "gas_raw",
        "weight_g",
        "storage_day"

    ]


    proposed_features = [

    # ====================================================
    # RAW SENSOR FEATURES
    # ====================================================

    "temperature_c",
    "humidity_pct",
    "gas_raw",
    "weight_g",
    "storage_day",


    # ====================================================
    # INDIVIDUAL BASELINE FEATURES
    # ====================================================

    "temperature_c_baseline_deviation",
    "temperature_c_relative_change",

    "humidity_pct_baseline_deviation",
    "humidity_pct_relative_change",

    "gas_raw_baseline_deviation",
    "gas_raw_relative_change",

    "weight_g_baseline_deviation",
    "weight_g_relative_change",


    # ====================================================
    # TEMPERATURE HISTORY / EXPOSURE
    # ====================================================

    "temperature_rolling_mean",
    "temperature_rolling_max",
    "temperature_rolling_min",

    "temperature_delta",
    "temperature_rate",

    "temperature_exposure_hours",
    "critical_temperature_exposure_hours",

    "thermal_deviation",
    "cumulative_thermal_stress",
    "thermal_stress",

    "temperature_trend",
    "thermal_risk_signal",


    # ====================================================
    # TEMPORAL FEATURES
    # ====================================================

    "temperature_c_delta",
    "humidity_pct_delta",
    "gas_raw_delta",
    "weight_g_delta",

    "temperature_c_rolling_mean",
    "humidity_pct_rolling_mean",
    "gas_raw_rolling_mean",
    "weight_g_rolling_mean",

    "temperature_c_rolling_std",
    "humidity_pct_rolling_std",
    "gas_raw_rolling_std",
    "weight_g_rolling_std",

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
    "environment_change_score",


    # ====================================================
    # DEGRADATION TRAJECTORY
    # ====================================================

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

    "degradation_direction",


    # ====================================================
    # DEGRADATION STATE
    # ====================================================

    "degradation_evidence",
    "degradation_index",
    "degradation_change",
    "degradation_acceleration",
    "state_score",


    # ====================================================
    # SENSOR RELIABILITY
    # ====================================================

    "overall_sensor_reliability",

    "temperature_reliability",
    "humidity_reliability",
    "gas_reliability",
    "weight_reliability",


    # ====================================================
    # DISTURBANCE / FOOD RESPONSE
    # ====================================================

    "environment_disturbance_score",
    "food_response_score",
    "sensor_agreement",

    "environment_food_ratio",
    "food_response_ratio",


    # ====================================================
    # ADAPTIVE FUSION
    # ====================================================

    "adaptive_gas_weight",
    "adaptive_weight_weight",
    "adaptive_temperature_weight",
    "adaptive_humidity_weight",

    "adaptive_degradation_signal",
    "adaptive_fusion_confidence",


    # ====================================================
    # REFERENCE ASSISTANCE
    # ====================================================

    "reference_confidence"

]


# Only use features actually generated by the
# existing modules.
    proposed_features = [
      feature
      for feature in proposed_features
      if feature in df.columns
    ]

    # ========================================================
    # 14. MACHINE LEARNING DATA
    # ========================================================

    print(
        "\n[13] Preparing machine-learning data..."
    )

    baseline_data = df[
        ["food_type"]
        + baseline_features
    ]


    proposed_data = df[
        ["food_type"]
        + proposed_features
    ]


    # Food type becomes machine-learning input
    # through one-hot encoding.
    X_baseline = pd.get_dummies(
        baseline_data,
        columns=["food_type"],
        dtype=float
    )


    X_proposed = pd.get_dummies(
        proposed_data,
        columns=["food_type"],
        dtype=float
    )


    y = df[
        "RSL_demo_days"
    ]
    

    
    # ========================================================
    # 15. TRAIN / TEST SPLIT
    # ========================================================

    print(
        "\n[14] Splitting training and test data..."
    )

    indices = np.arange(
        len(df)
    )


    train_indices, test_indices = (
        train_test_split(
            indices,
            test_size=0.25,
            random_state=42
        )
    )


    Xb_train = X_baseline.iloc[
        train_indices
    ]

    Xb_test = X_baseline.iloc[
        test_indices
    ]


    Xp_train = X_proposed.iloc[
        train_indices
    ]

    Xp_test = X_proposed.iloc[
        test_indices
    ]


    y_train = y.iloc[
        train_indices
    ]

    y_test = y.iloc[
        test_indices
    ]


    # ========================================================
    # 16. BASELINE XGBOOST
    # ========================================================

    print(
        "\n[15] Training baseline XGBoost..."
    )

    baseline_model = build_baseline()

    baseline_model.fit(
        Xb_train,
        y_train
    )


    baseline_prediction = (
        baseline_model.predict(
            Xb_test
        )
    )


    baseline_results = (
        regression_metrics(
            y_test,
            baseline_prediction
        )
    )


    # ========================================================
    # 17. PROPOSED XGBOOST
    # ========================================================

    print(
        "\n[16] Training adaptive proposed XGBoost..."
    )

    proposed_model = (
        build_proposed_model()
    )


    proposed_model.fit(
        Xp_train,
        y_train
    )


    proposed_prediction = (
        proposed_model.predict(
            Xp_test
        )
    )


    proposed_results = (
        regression_metrics(
            y_test,
            proposed_prediction
        )
    )


    # ========================================================
    # 18. CONFIDENCE
    # ========================================================

    print(
        "\n[17] Calculating prediction confidence..."
    )

    confidence_df = (
        df.iloc[
            test_indices
        ].copy()
    )


    confidence_df = (
        calculate_prediction_confidence(
            confidence_df
        )
    )


    # ========================================================
    # 19. FRESHNESS CLASSIFICATION
    # ========================================================

    freshness_predictions = [

        freshness_class(
            value
        )

        for value in proposed_prediction

    ]


    # ========================================================
    # 20. DISPLAY RESULTS
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        " MODEL COMPARISON"
    )

    print(
        "=" * 70
    )


    print(
        "\nBASELINE XGBOOST"
    )

    print(
        f"MAE  : "
        f"{baseline_results['MAE_days']:.3f} days"
    )

    print(
        f"RMSE : "
        f"{baseline_results['RMSE_days']:.3f} days"
    )

    print(
        f"R²   : "
        f"{baseline_results['R2']:.3f}"
    )


    print(
        "\nADAPTIVE PROPOSED XGBOOST"
    )

    print(
        f"MAE  : "
        f"{proposed_results['MAE_days']:.3f} days"
    )

    print(
        f"RMSE : "
        f"{proposed_results['RMSE_days']:.3f} days"
    )

    print(
        f"R²   : "
        f"{proposed_results['R2']:.3f}"
    )


    # ========================================================
    # 21. CONFIDENCE SUMMARY
    # ========================================================

    average_confidence = (
        confidence_df[
            "prediction_confidence"
        ].mean()
    )


    print(
        "\nAVERAGE PREDICTION CONFIDENCE"
    )

    print(
        f"{average_confidence * 100:.2f}%"
    )


    # ========================================================
    # 22. CONDITION SUMMARY
    # ========================================================

    print(
        "\nDETECTED CONDITIONS"
    )

    print(
        df[
            "fusion_condition"
        ].value_counts()
    )


    # ========================================================
    # 23. SAVE RESULTS
    # ========================================================

    os.makedirs(
        RESULTS_FOLDER,
        exist_ok=True
    )


    comparison = pd.DataFrame({

        "MAE_days": [

            baseline_results[
                "MAE_days"
            ],

            proposed_results[
                "MAE_days"
            ]

        ],

        "RMSE_days": [

            baseline_results[
                "RMSE_days"
            ],

            proposed_results[
                "RMSE_days"
            ]

        ],

        "R2": [

            baseline_results[
                "R2"
            ],

            proposed_results[
                "R2"
            ]

        ]

    }, index=[

        "Baseline_XGBoost",
        "Adaptive_Proposed_XGBoost"

    ])


    comparison.to_csv(
        "results/model_comparison.csv"
    )


    # ========================================================
    # 24. SAVE PREDICTIONS
    # ========================================================

    prediction_results = (
        df.iloc[
            test_indices
        ][
            [
                "timestamp",
                "food_type",
                "storage_day",
                "fusion_condition"
            ]
        ].copy()
    )


    prediction_results[
        "actual_RSL_demo_days"
    ] = y_test.to_numpy()


    prediction_results[
        "predicted_RSL_days"
    ] = proposed_prediction


    prediction_results[
        "freshness_class"
    ] = freshness_predictions


    prediction_results[
        "prediction_confidence"
    ] = confidence_df[
        "prediction_confidence"
    ].to_numpy()


    prediction_results[
        "confidence_level"
    ] = confidence_df[
        "confidence_level"
    ].to_numpy()


    prediction_results[
        "adaptive_sampling_required"
    ] = confidence_df[
        "adaptive_sampling_required"
    ].to_numpy()


    prediction_results.to_csv(
        "results/adaptive_predictions_demo.csv",
        index=False
    )


    # ========================================================
    # 25. SAVE COMPLETE DATA
    # ========================================================

    df.to_csv(
        "results/processed_demo_data.csv",
        index=False
    )


    # ========================================================
    # 26. FEATURE IMPORTANCE
    # ========================================================

    print(
        "\n[18] Finding important adaptive features..."
    )


    print_top_features(
        proposed_model,
        Xp_test,
        top_n=15
    )


    # ========================================================
    # 27. SHAP
    # ========================================================

    print(
        "\n[19] Creating SHAP explanation..."
    )


    shap_file = (
        create_shap_explanation(
            proposed_model,
            Xp_test
        )
    )


    print(
        f"SHAP plot saved to: {shap_file}"
    )


    # ========================================================
    # 28. FINAL SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        " ADAPTIVE SOFTWARE PIPELINE COMPLETE"
    )

    print(
        "=" * 70
    )


    print(
        "\nPipeline:"
    )

    print(
        "Food Profile"
        " -> Sensors"
        " -> Individual Baseline"
        " -> Temperature Exposure"
        " -> Temporal Features"
        " -> Degradation Analysis"
        " -> Sensor Reliability"
        " -> Disturbance Detection"
        " -> Adaptive Fusion"
        " -> XGBoost"
        " -> RSL"
        " -> Confidence"
    )


    print(
        "\nResults saved in:"
    )

    print(
        "results/"
    )


    print(
        "\nIMPORTANT:"
    )

    print(
        "Current RSL values are synthetic test targets."
    )

    print(
        "They are NOT real food-freshness results."
    )

    print(
        "Real experimental labels are required for"
    )

    print(
        "final scientific validation."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()