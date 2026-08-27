"""
Feature engineering for RiskPulse risk model.

Transforms raw transaction data into ML-ready features.
Handles missing values, categorical encoding, and feature scaling.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer

logger = logging.getLogger(__name__)

# â”€â”€ Feature Definitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

NUMERIC_FEATURES = [
    "amount",
    "transaction_velocity",
    "amount_vs_customer_baseline",
    "amount_vs_merchant_baseline",
    "transactions_last_5m",
    "transactions_last_1h",
    "transactions_last_24h",
    "failed_attempts",
    "distance_from_previous",
    "account_age_days",
    "historical_transaction_count",
    "historical_avg_amount",
    "historical_std_amount",
]

CATEGORICAL_FEATURES = [
    "payment_method",
    "currency",
    "new_device",
    "new_location",
]

BINARY_FEATURES = [
    "new_device",
    "new_location",
]

TARGET = "fraud_label"

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Feature descriptions for documentation
FEATURE_DESCRIPTIONS = {
    "amount": "Transaction amount in original currency",
    "transaction_velocity": "Ratio of current 24h txn count vs customer average",
    "amount_vs_customer_baseline": "Z-score of amount vs customer's historical mean",
    "amount_vs_merchant_baseline": "Z-score of amount vs merchant's mean",
    "transactions_last_5m": "Number of customer transactions in last 5 minutes",
    "transactions_last_1h": "Number of customer transactions in last 1 hour",
    "transactions_last_24h": "Number of customer transactions in last 24 hours",
    "failed_attempts": "Number of failed transaction attempts before this one",
    "distance_from_previous": "Approximate km from customer's previous transaction",
    "account_age_days": "Age of customer account in days",
    "historical_transaction_count": "Customer's total transaction count before this one",
    "historical_avg_amount": "Customer's historical average transaction amount",
    "historical_std_amount": "Customer's historical std dev of transaction amounts",
    "payment_method": "Payment method used (credit_card, debit_card, upi, etc.)",
    "currency": "Transaction currency (INR, USD, EUR)",
    "new_device": "Whether the device has been seen before for this customer",
    "new_location": "Whether the location differs from customer's usual country",
}


def build_preprocessor() -> ColumnTransformer:
    """Build a sklearn ColumnTransformer for preprocessing features."""
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    # Only include non-binary categoricals for one-hot encoding
    cat_for_encoding = [f for f in CATEGORICAL_FEATURES if f not in BINARY_FEATURES]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, cat_for_encoding),
            ("bin", "passthrough", BINARY_FEATURES),
        ],
        remainder="drop",
    )

    return preprocessor


def prepare_features(
    df: pd.DataFrame,
    fit_preprocessor: Optional[ColumnTransformer] = None,
) -> tuple[np.ndarray, np.ndarray, ColumnTransformer]:
    """
    Prepare features and labels from a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Raw data with all feature columns and fraud_label.
    fit_preprocessor : Optional[ColumnTransformer]
        If provided, use this fitted preprocessor (for validation/test).
        If None, fit a new one (for training).

    Returns
    -------
    X : np.ndarray
        Feature matrix.
    y : np.ndarray
        Label vector.
    preprocessor : ColumnTransformer
        Fitted preprocessor.
    """
    # Ensure boolean columns are int
    for col in BINARY_FEATURES:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # Separate features and target
    y = df[TARGET].values.astype(int)

    if fit_preprocessor is not None:
        X = fit_preprocessor.transform(df)
        return X, y, fit_preprocessor
    else:
        preprocessor = build_preprocessor()
        X = preprocessor.fit_transform(df)
        return X, y, preprocessor


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Get feature names from fitted preprocessor."""
    names = []
    for name, transformer, columns in preprocessor.transformers_:
        if name == "num":
            names.extend(columns)
        elif name == "cat":
            encoder = transformer.named_steps["encoder"]
            cat_names = encoder.get_feature_names_out(columns)
            names.extend(cat_names)
        elif name == "bin":
            names.extend(columns)
    return names

