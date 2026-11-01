import os

import matplotlib.pyplot as plt
import shap


def create_shap_explanation(
    model,
    X,
    output_path="results/shap_summary.png"
):
    """
    Generate a SHAP summary plot for the trained XGBoost model.

    SHAP helps us understand which sensor/trajectory
    features are influencing the Remaining Shelf Life
    prediction.

    Example:
        Gas increase       → strong influence
        Weight loss        → medium influence
        Temperature trend  → low influence
    """

    # Create results folder if it does not exist
    os.makedirs(
        os.path.dirname(output_path),
        exist_ok=True
    )

    # Use a limited number of rows for faster explanation
    sample_size = min(
        300,
        len(X)
    )

    X_sample = X.iloc[:sample_size]

    # ------------------------------------------------
    # CREATE SHAP EXPLAINER
    # ------------------------------------------------

    explainer = shap.TreeExplainer(
        model
    )

    # Calculate SHAP values
    shap_values = explainer.shap_values(
        X_sample
    )

    # ------------------------------------------------
    # CREATE SUMMARY PLOT
    # ------------------------------------------------

    plt.figure(
        figsize=(10, 7)
    )

    shap.summary_plot(
        shap_values,
        X_sample,
        show=False
    )

    plt.title(
        "SHAP Explanation - Food Freshness Prediction"
    )

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight"
    )

    plt.close()

    return output_path


def get_feature_importance(
    model,
    X
):
    """
    Return XGBoost feature importance.

    This gives us another simple way to identify
    which features are most important to the model.
    """

    importance = model.feature_importances_

    result = []

    for feature, value in zip(
        X.columns,
        importance
    ):

        result.append(
            {
                "feature": feature,
                "importance": float(value)
            }
        )

    # Sort from highest to lowest importance
    result.sort(
        key=lambda x: x["importance"],
        reverse=True
    )

    return result


def print_top_features(
    model,
    X,
    top_n=10
):
    """
    Print the most important features.
    """

    features = get_feature_importance(
        model,
        X
    )

    print("\nTop Important Features:")
    print("------------------------")

    for item in features[:top_n]:

        print(
            f"{item['feature']}: "
            f"{item['importance']:.4f}"
        )