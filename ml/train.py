"""
Model training for RazorGuard risk detection.

Trains multiple models, selects best based on validation PR-AUC,
and persists the winning model + preprocessor.

Usage:
    python ml/train.py
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.features import prepare_features, get_feature_names

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "artifacts")


def train_models(
    train_path: str,
    val_path: str,
    output_dir: str = MODEL_DIR,
) -> dict:
    """
    Train multiple models and select the best one.

    Parameters
    ----------
    train_path : str
        Path to training CSV.
    val_path : str
        Path to validation CSV.
    output_dir : str
        Where to save model artifacts.

    Returns
    -------
    dict
        Training results including metrics for each model.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load data
    logger.info("Loading training data from %s", train_path)
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    logger.info("Train: %d rows (fraud=%.1f%%), Val: %d rows (fraud=%.1f%%)",
                len(train_df), train_df["fraud_label"].mean() * 100,
                len(val_df), val_df["fraud_label"].mean() * 100)

    # Prepare features
    X_train, y_train, preprocessor = prepare_features(train_df)
    X_val, y_val, _ = prepare_features(val_df, fit_preprocessor=preprocessor)
    logger.info("Feature matrix: train=%s, val=%s", X_train.shape, X_val.shape)

    # Save preprocessor
    preprocessor_path = os.path.join(output_dir, "preprocessor.joblib")
    joblib.dump(preprocessor, preprocessor_path)
    logger.info("Preprocessor saved to %s", preprocessor_path)

    # Define models
    models = {
        "logistic_regression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
            C=0.1,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            class_weight="balanced",
        ),
    }

    results = {}
    best_model_name = None
    best_pr_auc = -1.0

    for name, model in models.items():
        logger.info("Training: %s", name)
        model.fit(X_train, y_train)

        # Predictions
        y_pred = model.predict(X_val)
        y_prob = model.predict_proba(X_val)[:, 1]

        # Metrics
        pr_auc = average_precision_score(y_val, y_prob)
        roc_auc = roc_auc_score(y_val, y_prob)
        f1 = f1_score(y_val, y_pred)

        report = classification_report(y_val, y_pred, output_dict=True)

        results[name] = {
            "pr_auc": float(pr_auc),
            "roc_auc": float(roc_auc),
            "f1": float(f1),
            "precision": float(report["1"]["precision"]),
            "recall": float(report["1"]["recall"]),
            "classification_report": report,
        }

        logger.info("  %s: PR-AUC=%.4f, ROC-AUC=%.4f, F1=%.4f, P=%.4f, R=%.4f",
                     name, pr_auc, roc_auc, f1,
                     report["1"]["precision"], report["1"]["recall"])

        if pr_auc > best_pr_auc:
            best_pr_auc = pr_auc
            best_model_name = name

    # Save best model
    logger.info("Best model: %s (PR-AUC=%.4f)", best_model_name, best_pr_auc)
    best_model = models[best_model_name]
    model_path = os.path.join(output_dir, "risk_model.joblib")
    joblib.dump(best_model, model_path)
    logger.info("Model saved to %s", model_path)

    # Feature importances (if available)
    feature_names = get_feature_names(preprocessor)
    importances = None
    if hasattr(best_model, "feature_importances_"):
        importances = dict(zip(feature_names, best_model.feature_importances_.tolist()))
    elif hasattr(best_model, "coef_"):
        importances = dict(zip(feature_names, np.abs(best_model.coef_[0]).tolist()))

    if importances:
        # Sort by importance
        importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
        importances_path = os.path.join(output_dir, "feature_importances.json")
        with open(importances_path, "w") as f:
            json.dump(importances, f, indent=2)
        logger.info("Feature importances saved to %s", importances_path)

        logger.info("Top 10 features:")
        for i, (feat, imp) in enumerate(list(importances.items())[:10]):
            logger.info("  %d. %s: %.4f", i + 1, feat, imp)

    # Save training metadata
    metadata = {
        "timestamp": datetime.utcnow().isoformat(),
        "best_model": best_model_name,
        "model_path": model_path,
        "preprocessor_path": preprocessor_path,
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "train_fraud_rate": float(train_df["fraud_label"].mean()),
        "val_fraud_rate": float(val_df["fraud_label"].mean()),
        "num_features": X_train.shape[1],
        "feature_names": feature_names,
        "results": results,
        "feature_importances": importances,
    }

    metadata_path = os.path.join(output_dir, "training_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info("Training metadata saved to %s", metadata_path)

    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train RazorGuard risk model")
    parser.add_argument("--train", default="data/train.csv", help="Training CSV")
    parser.add_argument("--val", default="data/validation.csv", help="Validation CSV")
    parser.add_argument("--output", default=MODEL_DIR, help="Output directory for artifacts")
    args = parser.parse_args()

    train_models(args.train, args.val, args.output)
    logger.info("Training complete.")
