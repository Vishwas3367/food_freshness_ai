from xgboost import XGBRegressor


def build_baseline():
    """
    Create the baseline XGBoost regression model.

    The baseline model uses the original sensor values
    without our proposed degradation-trajectory features.
    """

    model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="reg:squarederror",
        random_state=42
    )

    return model