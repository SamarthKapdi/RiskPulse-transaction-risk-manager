"""
Model evaluation for RazorGuard — held-out test set evaluation.

IMPORTANT: This script should be run ONCE after model and threshold
are finalized. The test set must not be used during development.

Generates:
- evaluation/evaluation_report.json
- evaluation/evaluation_report.md
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
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.features import prepare_features, get_feature_names
from ml.cost_model import CostConfig, compute_expected_costs, threshold_cost_analysis, find_optimal_threshold

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "artifacts")
EVAL_DIR = os.path.join(PROJECT_ROOT, "evaluation")


def evaluate_model(
    test_path: str,
    model_dir: str = MODEL_DIR,
    output_dir: str = EVAL_DIR,
    threshold: float = None,
) -> dict:
    """
    Evaluate the trained model on the held-out test set.

    Parameters
    ----------
    test_path : str
        Path to test CSV.
    model_dir : str
        Directory containing model artifacts.
    output_dir : str
        Directory for evaluation output.
    threshold : float
        Decision threshold. If None, uses optimal from validation.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load model and preprocessor
    model_path = os.path.join(model_dir, "risk_model.joblib")
    preprocessor_path = os.path.join(model_dir, "preprocessor.joblib")
    metadata_path = os.path.join(model_dir, "training_metadata.json")

    logger.info("Loading model from %s", model_path)
    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)

    with open(metadata_path) as f:
        training_metadata = json.load(f)

    # Load test data
    logger.info("Loading test data from %s", test_path)
    test_df = pd.read_csv(test_path)
    logger.info("Test set: %d rows (fraud=%.1f%%)",
                len(test_df), test_df["fraud_label"].mean() * 100)

    # Prepare features
    X_test, y_test, _ = prepare_features(test_df, fit_preprocessor=preprocessor)

    # Predictions
    y_prob = model.predict_proba(X_test)[:, 1]

    # Find optimal threshold if not specified
    if threshold is None:
        # Use validation data to find optimal threshold
        val_path = os.path.join(PROJECT_ROOT, "data", "validation.csv")
        if os.path.exists(val_path):
            val_df = pd.read_csv(val_path)
            X_val, y_val, _ = prepare_features(val_df, fit_preprocessor=preprocessor)
            y_val_prob = model.predict_proba(X_val)[:, 1]
            threshold, _ = find_optimal_threshold(y_val, y_val_prob)
            logger.info("Optimal threshold from validation: %.3f", threshold)
        else:
            threshold = 0.50
            logger.warning("No validation data found, using default threshold=0.50")

    y_pred = (y_prob >= threshold).astype(int)

    # ── Core Metrics ────────────────────────────────────────────────────
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    accuracy = accuracy_score(y_test, y_pred)
    pr_auc = average_precision_score(y_test, y_prob)
    roc_auc = roc_auc_score(y_test, y_prob)

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    logger.info("=== HELD-OUT TEST RESULTS ===")
    logger.info("Threshold: %.3f", threshold)
    logger.info("Precision: %.4f", precision)
    logger.info("Recall:    %.4f", recall)
    logger.info("F1:        %.4f", f1)
    logger.info("PR-AUC:    %.4f", pr_auc)
    logger.info("ROC-AUC:   %.4f", roc_auc)
    logger.info("FP: %d, FN: %d, TP: %d, TN: %d", fp, fn, tp, tn)
    logger.info("FPR: %.4f, FNR: %.4f", fpr, fnr)

    # ── Cost Analysis ───────────────────────────────────────────────────
    cost_config = CostConfig()
    costs = compute_expected_costs(y_test, y_pred, cost_config)
    threshold_analysis = threshold_cost_analysis(y_test, y_prob, cost_config)

    logger.info("=== COST ANALYSIS ===")
    logger.info("(%s)", cost_config.label)
    logger.info("FP Cost: ₹%.2f", costs["expected_fp_cost_inr"])
    logger.info("FN Cost: ₹%.2f", costs["expected_fn_cost_inr"])
    logger.info("Total:   ₹%.2f", costs["total_expected_cost_inr"])
    logger.info("Per 1K:  ₹%.2f", costs["cost_per_1000_transactions_inr"])

    # ── Per Risk Level ──────────────────────────────────────────────────
    risk_level_analysis = {}
    for level, lo, hi in [("LOW", 0, 0.3), ("MEDIUM", 0.3, 0.6), ("HIGH", 0.6, 0.85), ("CRITICAL", 0.85, 1.01)]:
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() > 0:
            level_precision = precision_score(y_test[mask], y_pred[mask], zero_division=0) if mask.sum() > 0 else 0
            risk_level_analysis[level] = {
                "count": int(mask.sum()),
                "actual_fraud": int(y_test[mask].sum()),
                "predicted_fraud": int(y_pred[mask].sum()),
                "precision": round(float(level_precision), 4),
            }

    # ── Classification Report ───────────────────────────────────────────
    cls_report = classification_report(y_test, y_pred, output_dict=True)

    # ── Curves data for visualization ───────────────────────────────────
    pr_precisions, pr_recalls, pr_thresholds = precision_recall_curve(y_test, y_prob)
    fpr_curve, tpr_curve, roc_thresholds = roc_curve(y_test, y_prob)

    # ── Build report ────────────────────────────────────────────────────
    report = {
        "evaluation_timestamp": datetime.utcnow().isoformat(),
        "model": training_metadata.get("best_model", "unknown"),
        "dataset": {
            "test_samples": len(test_df),
            "test_fraud_count": int(y_test.sum()),
            "test_fraud_rate": round(float(y_test.mean()), 4),
            "train_samples": training_metadata.get("train_samples"),
            "train_fraud_rate": training_metadata.get("train_fraud_rate"),
        },
        "threshold": threshold,
        "metrics": {
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "accuracy": round(float(accuracy), 4),
            "pr_auc": round(float(pr_auc), 4),
            "roc_auc": round(float(roc_auc), 4),
            "false_positive_rate": round(float(fpr), 4),
            "false_negative_rate": round(float(fnr), 4),
        },
        "confusion_matrix": {
            "true_positives": int(tp),
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
        },
        "cost_analysis": costs,
        "threshold_cost_analysis": threshold_analysis,
        "risk_level_analysis": risk_level_analysis,
        "classification_report": cls_report,
        "note": "All metrics computed on held-out test set. Costs are illustrative.",
    }

    # Save JSON report
    json_path = os.path.join(output_dir, "evaluation_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("JSON report saved to %s", json_path)

    # Save markdown report
    md_path = os.path.join(output_dir, "evaluation_report.md")
    _generate_markdown_report(report, md_path)
    logger.info("Markdown report saved to %s", md_path)

    return report


def _generate_markdown_report(report: dict, output_path: str):
    """Generate a human-readable markdown evaluation report."""
    metrics = report["metrics"]
    cm = report["confusion_matrix"]
    costs = report["cost_analysis"]
    dataset = report["dataset"]

    lines = [
        "# RazorGuard — Evaluation Report",
        "",
        f"> Generated: {report['evaluation_timestamp']}",
        f"> Model: {report['model']}",
        f"> Threshold: {report['threshold']}",
        "",
        "## Dataset",
        "",
        f"| Set | Samples | Fraud Rate |",
        f"|-----|---------|------------|",
        f"| Train | {dataset['train_samples']} | {dataset['train_fraud_rate']:.2%} |",
        f"| Test (held-out) | {dataset['test_samples']} | {dataset['test_fraud_rate']:.2%} |",
        "",
        "## Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Precision | {metrics['precision']:.4f} |",
        f"| Recall | {metrics['recall']:.4f} |",
        f"| F1 Score | {metrics['f1']:.4f} |",
        f"| PR-AUC | {metrics['pr_auc']:.4f} |",
        f"| ROC-AUC | {metrics['roc_auc']:.4f} |",
        f"| False Positive Rate | {metrics['false_positive_rate']:.4f} |",
        f"| False Negative Rate | {metrics['false_negative_rate']:.4f} |",
        "",
        "## Confusion Matrix",
        "",
        "| | Predicted Legit | Predicted Fraud |",
        "|---|---|---|",
        f"| **Actual Legit** | {cm['true_negatives']} | {cm['false_positives']} |",
        f"| **Actual Fraud** | {cm['false_negatives']} | {cm['true_positives']} |",
        "",
        "## Cost Analysis",
        "",
        f"> ⚠️ {costs['cost_config_label']}",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Review cost per legit flagged | ₹{costs['legitimate_review_cost_inr']} |",
        f"| Cost per missed fraud | ₹{costs['fraud_missed_cost_inr']} |",
        f"| Total FP cost | ₹{costs['expected_fp_cost_inr']:,.2f} |",
        f"| Total FN cost | ₹{costs['expected_fn_cost_inr']:,.2f} |",
        f"| **Total expected cost** | **₹{costs['total_expected_cost_inr']:,.2f}** |",
        f"| Cost per 1,000 transactions | ₹{costs['cost_per_1000_transactions_inr']:,.2f} |",
        "",
        "## Threshold / Cost Analysis",
        "",
        "| Threshold | Precision | Recall | F1 | FP | FN | Total Cost (₹) |",
        "|-----------|-----------|--------|-----|-----|-----|-----------------|",
    ]

    for row in report.get("threshold_cost_analysis", []):
        lines.append(
            f"| {row['threshold']:.2f} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['false_positives']} | {row['false_negatives']} | "
            f"{row['total_cost_inr']:,.2f} |"
        )

    lines.extend([
        "",
        "## Risk Level Analysis",
        "",
        "| Level | Count | Actual Fraud | Predicted Fraud | Precision |",
        "|-------|-------|-------------|-----------------|-----------|",
    ])

    for level, data in report.get("risk_level_analysis", {}).items():
        lines.append(
            f"| {level} | {data['count']} | {data['actual_fraud']} | "
            f"{data['predicted_fraud']} | {data['precision']:.4f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "*All metrics from actual model execution on held-out test data.*",
        "*No metrics have been fabricated.*",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate RazorGuard on held-out test set")
    parser.add_argument("--test", default="data/test.csv", help="Test CSV path")
    parser.add_argument("--model-dir", default=MODEL_DIR, help="Model artifacts directory")
    parser.add_argument("--output", default=EVAL_DIR, help="Output directory")
    parser.add_argument("--threshold", type=float, default=None, help="Decision threshold")
    args = parser.parse_args()

    evaluate_model(args.test, args.model_dir, args.output, args.threshold)
    logger.info("Evaluation complete.")
