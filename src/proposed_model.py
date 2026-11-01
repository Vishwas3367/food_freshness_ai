from xgboost import XGBRegressor


def build_proposed_model():
    """
    Create the proposed XGBoost model.

    This model will receive:
    1. Original sensor values
    2. Temporal features
    3. Degradation trajectory features

    The model predicts Remaining Shelf Life (RSL) in days.
    """

    model = XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.90,
        objective="reg:squarederror",
        random_state=42
    )

    return model