import numpy as np
import pandas as pd


# ============================================================
# ADAPTIVE SENSOR FUSION ENGINE
# ============================================================
#
# Proposed architecture:
#
# Individual Baseline
#        +
# Temporal Behaviour
#        +
# Degradation Trajectory
#        +
# Degradation State
#        +
# Sensor Reliability
#        +
# Environmental Disturbance
#        +
# Reference Coverage
#        ↓
# Adaptive Sensor Weighting
#        ↓
# Fused Food-Response Signal
#        ↓
# Fusion Confidence
#
# This is a research prototype.
# Final coefficients must be calibrated and validated using
# real experimental food-freshness labels.
# ============================================================


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
# CLIP
# ============================================================

def clip_series(
    series,
    lower=0.0,
    upper=1.0
):

    return pd.to_numeric(
        series,
        errors="coerce"
    ).fillna(0.0).clip(
        lower,
        upper
    )


# ============================================================
# NORMALIZE
# ============================================================

def normalize_signal(
    series,
    lower=0.0,
    upper=1.0
):

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
# ENSURE REQUIRED FEATURES
# ============================================================

def ensure_required_features(df):

    out = df.copy()

    # --------------------------------------------------------
    # Gas change score
    # --------------------------------------------------------

    if "gas_change_score" not in out.columns:

        gas_delta = safe_series(
            out,
            "gas_raw_delta"
        )

        out[
            "gas_change_score"
        ] = normalize_signal(
            gas_delta.abs(),
            0.0,
            max(
                float(
                    gas_delta.abs().quantile(0.95)
                ),
                1e-6
            )
        ) * 3.0

    # --------------------------------------------------------
    # Weight loss score
    # --------------------------------------------------------

    if "weight_loss_score" not in out.columns:

        weight_delta = safe_series(
            out,
            "weight_g_delta"
        )

        weight_loss = np.maximum(
            -weight_delta,
            0.0
        )

        scale = max(
            float(
                weight_loss.quantile(0.95)
            ),
            1e-6
        )

        out[
            "weight_loss_score"
        ] = (
            weight_loss / scale
        ).clip(
            0.0,
            3.0
        )

    # --------------------------------------------------------
    # Temperature change score
    # --------------------------------------------------------

    if "temperature_change_score" not in out.columns:

        temperature_delta = safe_series(
            out,
            "temperature_c_delta"
        )

        out[
            "temperature_change_score"
        ] = temperature_delta.abs()

    # --------------------------------------------------------
    # Humidity change score
    # --------------------------------------------------------

    if "humidity_change_score" not in out.columns:

        humidity_delta = safe_series(
            out,
            "humidity_pct_delta"
        )

        out[
            "humidity_change_score"
        ] = humidity_delta.abs()

    # --------------------------------------------------------
    # Gas-weight interaction
    # --------------------------------------------------------

    if "gas_weight_interaction" not in out.columns:

        gas_score = safe_series(
            out,
            "gas_change_score"
        )

        weight_score = safe_series(
            out,
            "weight_loss_score"
        )

        out[
            "gas_weight_interaction"
        ] = (
            gas_score
            *
            weight_score
        )

    # --------------------------------------------------------
    # Food response score
    # --------------------------------------------------------

    if "food_response_score" not in out.columns:

        gas_signal = normalize_signal(
            safe_series(
                out,
                "gas_change_score"
            ),
            0.0,
            3.0
        )

        weight_signal = normalize_signal(
            safe_series(
                out,
                "weight_loss_score"
            ),
            0.0,
            3.0
        )

        out[
            "food_response_score"
        ] = (
            0.60 * gas_signal
            +
            0.40 * weight_signal
        ).clip(
            0.0,
            1.0
        )

    # --------------------------------------------------------
    # Environment disturbance
    # --------------------------------------------------------

    if "environment_disturbance_score" not in out.columns:

        if "environment_change_score" in out.columns:

            out[
                "environment_disturbance_score"
            ] = normalize_signal(
                safe_series(
                    out,
                    "environment_change_score"
                ),
                0.0,
                3.0
            )

        else:

            out[
                "environment_disturbance_score"
            ] = 0.0

    # --------------------------------------------------------
    # Environmental disturbance flag
    # --------------------------------------------------------

    if "environmental_disturbance" not in out.columns:

        out[
            "environmental_disturbance"
        ] = (
            safe_series(
                out,
                "environment_disturbance_score"
            )
            >= 0.70
        ).astype(int)

    # --------------------------------------------------------
    # Degradation state
    # --------------------------------------------------------

    if "state_score" not in out.columns:

        if "degradation_index" in out.columns:

            out[
                "state_score"
            ] = clip_series(
                safe_series(
                    out,
                    "degradation_index"
                )
            )

        elif "trajectory_score" in out.columns:

            out[
                "state_score"
            ] = clip_series(
                safe_series(
                    out,
                    "trajectory_score"
                )
            )

        else:

            out[
                "state_score"
            ] = out[
                "food_response_score"
            ]

    # --------------------------------------------------------
    # Trajectory score
    # --------------------------------------------------------

    if "trajectory_score" not in out.columns:

        out[
            "trajectory_score"
        ] = out[
            "food_response_score"
        ]

    # --------------------------------------------------------
    # Sensor reliability
    # --------------------------------------------------------

    reliability_defaults = {

        "gas_reliability": 0.70,

        "weight_reliability": 0.70,

        "temperature_reliability": 0.70,

        "humidity_reliability": 0.70
    }

    for column, default in reliability_defaults.items():

        if column not in out.columns:

            out[
                column
            ] = default

    # --------------------------------------------------------
    # Overall reliability
    # --------------------------------------------------------

    if "overall_sensor_reliability" not in out.columns:

        out[
            "overall_sensor_reliability"
        ] = out[
            [
                "gas_reliability",
                "weight_reliability",
                "temperature_reliability",
                "humidity_reliability"
            ]
        ].mean(
            axis=1
        )

    # --------------------------------------------------------
    # Sensor agreement
    # --------------------------------------------------------

    if "sensor_agreement" not in out.columns:

        gas_direction = np.sign(
            safe_series(
                out,
                "gas_raw_delta"
            )
        )

        weight_direction = np.sign(
            safe_series(
                out,
                "weight_g_delta"
            )
        )

        out[
            "sensor_agreement"
        ] = (
            (
                gas_direction > 0
            )
            &
            (
                weight_direction < 0
            )
        ).astype(float)

    return out


# ============================================================
# MAIN ADAPTIVE FUSION
# ============================================================

def calculate_adaptive_fusion(df):

    out = ensure_required_features(
        df
    )

    # ========================================================
    # 1. SENSOR RELIABILITY
    # ========================================================

    gas_rel = clip_series(
        out[
            "gas_reliability"
        ]
    )

    weight_rel = clip_series(
        out[
            "weight_reliability"
        ]
    )

    temp_rel = clip_series(
        out[
            "temperature_reliability"
        ]
    )

    humidity_rel = clip_series(
        out[
            "humidity_reliability"
        ]
    )

    overall_rel = clip_series(
        out[
            "overall_sensor_reliability"
        ]
    )

    # ========================================================
    # 2. ENVIRONMENTAL DISTURBANCE
    # ========================================================

    disturbance = clip_series(
        out[
            "environment_disturbance_score"
        ]
    )

    # ========================================================
    # 3. FOOD RESPONSE
    # ========================================================

    food_response = clip_series(
        out[
            "food_response_score"
        ]
    )

    # ========================================================
    # 4. DEGRADATION TRAJECTORY
    # ========================================================

    trajectory = clip_series(
        out[
            "trajectory_score"
        ]
    )

    # ========================================================
    # 5. DEGRADATION STATE
    # ========================================================

    state_score = clip_series(
        out[
            "state_score"
        ]
    )

    # ========================================================
    # 6. SENSOR EVIDENCE
    # ========================================================

    gas_signal = normalize_signal(
        safe_series(
            out,
            "gas_change_score"
        ),
        0.0,
        3.0
    )

    weight_signal = normalize_signal(
        safe_series(
            out,
            "weight_loss_score"
        ),
        0.0,
        3.0
    )

    temperature_signal = normalize_signal(
        safe_series(
            out,
            "temperature_change_score"
        ),
        0.0,
        3.0
    )

    humidity_signal = normalize_signal(
        safe_series(
            out,
            "humidity_change_score"
        ),
        0.0,
        5.0
    )

    # ========================================================
    # 7. GAS + WEIGHT AGREEMENT
    # ========================================================

    interaction = safe_series(
        out,
        "gas_weight_interaction"
    )

    interaction_signal = normalize_signal(
        interaction,
        0.0,
        3.0
    )

    agreement = clip_series(
        out[
            "sensor_agreement"
        ]
    )

    # ========================================================
    # 8. INITIAL ADAPTIVE WEIGHTS
    # ========================================================
    #
    # Base development weights:
    #
    # Gas          35%
    # Weight       30%
    # Temperature 20%
    # Humidity     15%
    #
    # Reliability and context then modify them.
    # ========================================================

    gas_weight = (
        0.35
        * gas_rel
    )

    weight_weight = (
        0.30
        * weight_rel
    )

    temperature_weight = (
        0.20
        * temp_rel
    )

    humidity_weight = (
        0.15
        * humidity_rel
    )

    # ========================================================
    # 9. FOOD RESPONSE ADAPTATION
    # ========================================================

    gas_weight *= (
        1.0
        +
        0.50 * food_response
    )

    weight_weight *= (
        1.0
        +
        0.40 * food_response
    )

    # ========================================================
    # 10. TRAJECTORY ADAPTATION
    # ========================================================

    gas_weight *= (
        1.0
        +
        0.25 * trajectory
    )

    weight_weight *= (
        1.0
        +
        0.20 * trajectory
    )

    # ========================================================
    # 11. GAS-WEIGHT AGREEMENT
    # ========================================================

    gas_weight *= (
        1.0
        +
        0.30 * agreement
        +
        0.30 * interaction_signal
    )

    weight_weight *= (
        1.0
        +
        0.30 * agreement
        +
        0.20 * interaction_signal
    )

    # ========================================================
    # 12. ENVIRONMENTAL DISTURBANCE ADAPTATION
    # ========================================================
    #
    # When environmental disturbance increases,
    # temperature/humidity should contribute less to
    # food-degradation evidence.
    # ========================================================

    temperature_weight *= (
        1.0
        -
        0.70 * disturbance
    )

    humidity_weight *= (
        1.0
        -
        0.70 * disturbance
    )

    # Prevent complete disappearance.

    temperature_weight = temperature_weight.clip(
        lower=0.02
    )

    humidity_weight = humidity_weight.clip(
        lower=0.02
    )

    # ========================================================
    # 13. NORMALIZE WEIGHTS
    # ========================================================

    total_weight = (
        gas_weight
        +
        weight_weight
        +
        temperature_weight
        +
        humidity_weight
    )

    total_weight = total_weight.replace(
        0,
        1e-9
    )

    out[
        "adaptive_gas_weight"
    ] = (
        gas_weight
        /
        total_weight
    )

    out[
        "adaptive_weight_weight"
    ] = (
        weight_weight
        /
        total_weight
    )

    out[
        "adaptive_temperature_weight"
    ] = (
        temperature_weight
        /
        total_weight
    )

    out[
        "adaptive_humidity_weight"
    ] = (
        humidity_weight
        /
        total_weight
    )

    # ========================================================
    # 14. RELIABILITY-WEIGHTED SENSOR EVIDENCE
    # ========================================================

    gas_evidence = (
        gas_signal
        *
        out[
            "adaptive_gas_weight"
        ]
    )

    weight_evidence = (
        weight_signal
        *
        out[
            "adaptive_weight_weight"
        ]
    )

    temperature_evidence = (
        temperature_signal
        *
        out[
            "adaptive_temperature_weight"
        ]
    )

    humidity_evidence = (
        humidity_signal
        *
        out[
            "adaptive_humidity_weight"
        ]
    )

    # ========================================================
    # 15. BASE FUSED SIGNAL
    # ========================================================

    fused_signal = (
        gas_evidence
        +
        weight_evidence
        +
        temperature_evidence
        +
        humidity_evidence
    )

    # ========================================================
    # 16. TRAJECTORY / STATE INTEGRATION
    # ========================================================

    out[
        "adaptive_degradation_signal"
    ] = (
        0.55 * fused_signal
        +
        0.25 * trajectory
        +
        0.20 * state_score
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 17. ENVIRONMENTAL SUPPRESSION
    # ========================================================
    #
    # If the environment is highly disturbed, reduce
    # confidence in a degradation interpretation.
    # ========================================================

    environment_suppression = (
        1.0
        -
        0.40 * disturbance
    )

    out[
        "adaptive_degradation_signal"
    ] *= environment_suppression

    out[
        "adaptive_degradation_signal"
    ] = out[
        "adaptive_degradation_signal"
    ].clip(
        0.0,
        1.0
    )

    # ========================================================
    # 18. FUSION CONFIDENCE
    # ========================================================

    # Reliability
    reliability_component = overall_rel

    # Sensor agreement
    agreement_component = agreement

    # Trajectory consistency
    trajectory_component = (
        1.0
        -
        safe_series(
            out,
            "trajectory_rolling_std"
        ).clip(
            0.0,
            1.0
        )
    )

    # Environmental stability
    environment_component = (
        1.0
        -
        disturbance
    )

    out[
        "adaptive_fusion_confidence"
    ] = (
        0.40
        * reliability_component

        +
        0.25
        * agreement_component

        +
        0.20
        * trajectory_component

        +
        0.15
        * environment_component
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 19. REFERENCE CONFIDENCE
    # ========================================================

    if "reference_confidence" in out.columns:

        reference_confidence = clip_series(
            out[
                "reference_confidence"
            ]
        )

        out[
            "adaptive_fusion_confidence"
        ] = (
            0.85
            * out[
                "adaptive_fusion_confidence"
            ]
            +
            0.15
            * reference_confidence
        ).clip(
            0.0,
            1.0
        )

    # ========================================================
    # 20. FOOD RESPONSE / ENVIRONMENT RATIO
    # ========================================================

    food_evidence = (
        gas_evidence
        +
        weight_evidence
    )

    environment_evidence = (
        temperature_evidence
        +
        humidity_evidence
    )

    total_evidence = (
        food_evidence
        +
        environment_evidence
        +
        1e-9
    )

    out[
        "food_response_ratio"
    ] = (
        food_evidence
        /
        total_evidence
    ).clip(
        0.0,
        1.0
    )

    out[
        "environment_food_ratio"
    ] = (
        environment_evidence
        /
        total_evidence
    ).clip(
        0.0,
        1.0
    )

    # ========================================================
    # 21. CONDITION CLASSIFICATION
    # ========================================================

    environmental_flag = (
        safe_series(
            out,
            "environmental_disturbance"
        ) == 1
    )

    degradation_flag = (
        (
            out[
                "adaptive_degradation_signal"
            ]
            >= 0.40
        )
        |
        (
            state_score
            >= 0.40
        )
    )

    mixed_flag = (
        environmental_flag
        &
        degradation_flag
    )

    out[
        "possible_food_degradation"
    ] = degradation_flag.astype(
        int
    )

    out[
        "mixed_condition"
    ] = mixed_flag.astype(
        int
    )

    out[
        "fusion_condition"
    ] = np.select(

        [
            mixed_flag,

            environmental_flag,

            degradation_flag
        ],

        [
            "Mixed Condition",

            "Environmental Disturbance",

            "Food Degradation"
        ],

        default="Normal Condition"
    )

    # ========================================================
    # 22. ADAPTIVE WEIGHT SUM CHECK
    # ========================================================

    out[
        "adaptive_weight_sum"
    ] = (
        out[
            "adaptive_gas_weight"
        ]
        +
        out[
            "adaptive_weight_weight"
        ]
        +
        out[
            "adaptive_temperature_weight"
        ]
        +
        out[
            "adaptive_humidity_weight"
        ]
    )

    return out


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("ADAPTIVE SENSOR FUSION ENGINE TEST")
    print("=" * 65)

    # --------------------------------------------------------
    # Synthetic software-test data
    # --------------------------------------------------------

    np.random.seed(42)

    n = 12

    df = pd.DataFrame({

        "gas_change_score": [
            0.1,
            0.2,
            0.3,
            0.4,
            0.6,
            0.8,
            1.0,
            1.2,
            1.5,
            1.8,
            2.2,
            2.6
        ],

        "weight_loss_score": [
            0.05,
            0.08,
            0.10,
            0.15,
            0.20,
            0.25,
            0.30,
            0.40,
            0.50,
            0.65,
            0.80,
            1.00
        ],

        "temperature_change_score": [
            0.1,
            0.1,
            0.2,
            0.2,
            0.3,
            0.3,
            0.4,
            0.5,
            0.6,
            0.8,
            1.0,
            1.2
        ],

        "humidity_change_score": [
            0.1,
            0.1,
            0.2,
            0.2,
            0.3,
            0.3,
            0.4,
            0.4,
            0.5,
            0.6,
            0.7,
            0.8
        ],

        "gas_weight_interaction": [
            0.05,
            0.10,
            0.15,
            0.20,
            0.30,
            0.40,
            0.50,
            0.70,
            0.90,
            1.20,
            1.50,
            2.00
        ],

        "gas_reliability": [
            0.80,
            0.80,
            0.78,
            0.78,
            0.75,
            0.73,
            0.70,
            0.68,
            0.65,
            0.63,
            0.60,
            0.58
        ],

        "weight_reliability": [
            0.85,
            0.85,
            0.84,
            0.84,
            0.83,
            0.82,
            0.81,
            0.80,
            0.80,
            0.79,
            0.78,
            0.78
        ],

        "temperature_reliability": [
            0.90,
            0.90,
            0.89,
            0.89,
            0.88,
            0.87,
            0.85,
            0.84,
            0.82,
            0.80,
            0.78,
            0.76
        ],

        "humidity_reliability": [
            0.88,
            0.88,
            0.87,
            0.87,
            0.86,
            0.85,
            0.84,
            0.83,
            0.82,
            0.80,
            0.78,
            0.76
        ],

        "overall_sensor_reliability": [
            0.86,
            0.86,
            0.845,
            0.845,
            0.83,
            0.815,
            0.80,
            0.7875,
            0.7725,
            0.755,
            0.735,
            0.72
        ],

        "sensor_agreement": [
            0.0,
            0.2,
            0.3,
            0.4,
            0.5,
            0.6,
            0.7,
            0.75,
            0.80,
            0.85,
            0.90,
            1.0
        ],

        "trajectory_score": [
            0.00,
            0.02,
            0.04,
            0.07,
            0.10,
            0.15,
            0.20,
            0.27,
            0.34,
            0.42,
            0.50,
            0.60
        ],

        "state_score": [
            0.00,
            0.02,
            0.04,
            0.07,
            0.10,
            0.15,
            0.20,
            0.27,
            0.34,
            0.42,
            0.50,
            0.60
        ],

        "environment_disturbance_score": [
            0.05,
            0.05,
            0.06,
            0.06,
            0.07,
            0.08,
            0.10,
            0.12,
            0.15,
            0.18,
            0.22,
            0.25
        ],

        "environmental_disturbance": [
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0
        ],

        "gas_raw_delta": [
            0,
            2,
            3,
            4,
            5,
            6,
            8,
            10,
            12,
            15,
            17,
            20
        ],

        "weight_g_delta": [
            0,
            -0.1,
            -0.1,
            -0.2,
            -0.2,
            -0.3,
            -0.3,
            -0.4,
            -0.5,
            -0.6,
            -0.7,
            -0.8
        ],

        "trajectory_rolling_std": [
            0.00,
            0.01,
            0.01,
            0.02,
            0.02,
            0.03,
            0.03,
            0.04,
            0.04,
            0.05,
            0.05,
            0.06
        ]
    })

    result = calculate_adaptive_fusion(
        df
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print(
        "\nRequired adaptive features:"
    )

    features = [

        "food_response_score",

        "adaptive_gas_weight",

        "adaptive_weight_weight",

        "adaptive_temperature_weight",

        "adaptive_humidity_weight",

        "adaptive_degradation_signal",

        "adaptive_fusion_confidence",

        "fusion_condition",

        "food_response_ratio",

        "environment_food_ratio",

        "adaptive_weight_sum"
    ]

    for feature in features:

        if feature in result.columns:

            print(
                f"✓ {feature}"
            )

        else:

            print(
                f"✗ {feature}"
            )

    print(
        "\nFinal observation:"
    )

    print("-" * 65)

    print(
        result.iloc[-1][
            features
        ]
    )

    print(
        "\nWeight-sum validation:"
    )

    print(
        result[
            "adaptive_weight_sum"
        ].describe()
    )

    print(
        "\nFusion progression:"
    )

    print("-" * 65)

    print(
        result[
            [
                "adaptive_gas_weight",
                "adaptive_weight_weight",
                "adaptive_temperature_weight",
                "adaptive_humidity_weight",
                "adaptive_degradation_signal",
                "adaptive_fusion_confidence",
                "fusion_condition"
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "ADAPTIVE SENSOR FUSION ENGINE TEST COMPLETE"
    )

    print(
        "=" * 65
    )