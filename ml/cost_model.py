"""
Cost model for RiskPulse false-positive / false-negative economics.

IMPORTANT: All cost values are ILLUSTRATIVE merchant assumptions.
They do NOT represent real Razorpay economics.
They are configurable to demonstrate threshold/cost tradeoffs.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CostConfig:
    """
    Illustrative cost configuration for risk decisions.

    All values in INR. Clearly labeled as illustrative assumptions.
    """
    # Cost of reviewing a legitimate transaction (false positive)
    # Includes: manual review time, customer friction, potential lost sale
    legitimate_review_cost: float = 150.0  # INR

    # Cost of missing a fraudulent transaction (false negative)
    # Includes: chargeback, investigation, reputation damage
    fraud_missed_cost: float = 5000.0  # INR

    # Label for transparency
    label: str = "Illustrative merchant cost assumptions"


def compute_expected_costs(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    config: Optional[CostConfig] = None,
) -> dict:
    """
    Compute expected costs from predictions.

    Parameters
    ----------
    y_true : array-like
        True labels (0=legit, 1=fraud).
    y_pred : array-like
        Predicted labels.
    config : CostConfig
        Cost configuration.

    Returns
    -------
    dict
        Cost breakdown.
    """
    if config is None:
        config = CostConfig()

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    n = len(y_true)

    # False positives: predicted fraud but actually legit
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    # False negatives: predicted legit but actually fraud
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    # True positives
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    # True negatives
    tn = int(((y_pred == 0) & (y_true == 0)).sum())

    fp_cost = fp * config.legitimate_review_cost
    fn_cost = fn * config.fraud_missed_cost
    total_cost = fp_cost + fn_cost

    # Per 1000 transactions
    cost_per_1k = (total_cost / n * 1000) if n > 0 else 0

    return {
        "cost_config_label": config.label,
        "legitimate_review_cost_inr": config.legitimate_review_cost,
        "fraud_missed_cost_inr": config.fraud_missed_cost,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "expected_fp_cost_inr": round(fp_cost, 2),
        "expected_fn_cost_inr": round(fn_cost, 2),
        "total_expected_cost_inr": round(total_cost, 2),
        "cost_per_1000_transactions_inr": round(cost_per_1k, 2),
    }


def threshold_cost_analysis(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    config: Optional[CostConfig] = None,
    thresholds: Optional[list[float]] = None,
) -> list[dict]:
    """
    Analyze cost at different decision thresholds.

    Parameters
    ----------
    y_true : array-like
        True labels.
    y_prob : array-like
        Predicted probabilities.
    config : CostConfig
        Cost configuration.
    thresholds : list[float]
        Thresholds to evaluate.

    Returns
    -------
    list[dict]
        Cost analysis at each threshold.
    """
    if config is None:
        config = CostConfig()

    if thresholds is None:
        thresholds = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)

    results = []
    for threshold in thresholds:
        y_pred = (y_prob >= threshold).astype(int)

        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        costs = compute_expected_costs(y_true, y_pred, config)

        results.append({
            "threshold": threshold,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "false_positives": fp,
            "false_negatives": fn,
            "expected_fp_cost_inr": costs["expected_fp_cost_inr"],
            "expected_fn_cost_inr": costs["expected_fn_cost_inr"],
            "total_cost_inr": costs["total_expected_cost_inr"],
            "cost_per_1000_inr": costs["cost_per_1000_transactions_inr"],
        })

    return results


def find_optimal_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    config: Optional[CostConfig] = None,
) -> tuple[float, dict]:
    """Find the threshold that minimizes total expected cost."""
    if config is None:
        config = CostConfig()

    thresholds = np.arange(0.05, 0.96, 0.01)
    analysis = threshold_cost_analysis(y_true, y_prob, config, thresholds.tolist())

    best = min(analysis, key=lambda x: x["total_cost_inr"])
    return best["threshold"], best

