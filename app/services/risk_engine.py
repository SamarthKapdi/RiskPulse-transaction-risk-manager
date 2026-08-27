"""
Risk Engine for RiskPulse.

Combines ML model predictions with risk signals to produce
a comprehensive risk assessment for each transaction.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from app.services.risk_signals import RiskSignalEngine, RiskSignal

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml", "artifacts")

# Risk level thresholds (configurable)
DEFAULT_THRESHOLDS = {
    "low_max": 0.30,
    "medium_max": 0.60,
    "high_max": 0.85,
    # Anything above high_max is CRITICAL
}


class RiskEngine:
    """
    Core risk assessment engine.

    Combines:
    1. ML model probability score
    2. Interpretable risk signals
    3. Risk level classification
    """

    def __init__(
        self,
        model_dir: str = MODEL_DIR,
        thresholds: Optional[dict] = None,
        model_version: str = "v1.0",
    ):
        self.model_version = model_version
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.signal_engine = RiskSignalEngine()

        # Load ML model and preprocessor
        self._model = None
        self._preprocessor = None
        self._model_dir = model_dir
        self._load_model()

    def _load_model(self):
        """Load the trained ML model and preprocessor."""
        model_path = os.path.join(self._model_dir, "risk_model.joblib")
        preprocessor_path = os.path.join(self._model_dir, "preprocessor.joblib")

        if os.path.exists(model_path) and os.path.exists(preprocessor_path):
            self._model = joblib.load(model_path)
            self._preprocessor = joblib.load(preprocessor_path)
            logger.info("Risk model loaded from %s", model_path)
        else:
            logger.warning("ML model not found at %s â€” using signal-only mode", model_path)

    def _classify_risk_level(self, score: float) -> str:
        """Map a risk score to a risk level."""
        if score < self.thresholds["low_max"]:
            return "LOW"
        elif score < self.thresholds["medium_max"]:
            return "MEDIUM"
        elif score < self.thresholds["high_max"]:
            return "HIGH"
        else:
            return "CRITICAL"

    def analyze_transaction(self, transaction: dict) -> dict:
        """
        Perform full risk analysis on a single transaction.

        Parameters
        ----------
        transaction : dict
            Transaction data with feature columns.

        Returns
        -------
        dict
            Risk assessment including score, level, decision, confidence, signals.
        """
        txn_id = transaction.get("transaction_id", "unknown")

        # Get ML risk score
        risk_score = 0.0
        confidence = 0.0

        if self._model is not None and self._preprocessor is not None:
            try:
                df = pd.DataFrame([transaction])
                # Ensure boolean columns are int
                for col in ["new_device", "new_location"]:
                    if col in df.columns:
                        df[col] = df[col].astype(int)
                X = self._preprocessor.transform(df)
                proba = self._model.predict_proba(X)[0]
                risk_score = float(proba[1])
                confidence = float(max(proba))
            except Exception as e:
                logger.error("ML prediction failed for %s: %s", txn_id, e)
                risk_score = 0.5
                confidence = 0.5

        # Generate risk signals
        signals = self.signal_engine.generate_signals(transaction)

        # If no ML model, estimate risk from signals
        if self._model is None:
            risk_score = self._estimate_from_signals(signals)
            confidence = min(0.6 + len(signals) * 0.1, 0.95)

        # Classify risk level
        risk_level = self._classify_risk_level(risk_score)

        return {
            "transaction_id": txn_id,
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "confidence": round(confidence, 4),
            "model_version": self.model_version,
            "signals": [s.to_dict() for s in signals],
            "signal_count": len(signals),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def analyze_batch(self, transactions: list[dict]) -> list[dict]:
        """Analyze a batch of transactions."""
        results = []
        for txn in transactions:
            result = self.analyze_transaction(txn)
            results.append(result)
        return results

    def _estimate_from_signals(self, signals: list[RiskSignal]) -> float:
        """Estimate risk score from signals when ML model is unavailable."""
        if not signals:
            return 0.1

        severity_weights = {
            "LOW": 0.15,
            "MEDIUM": 0.35,
            "HIGH": 0.65,
            "CRITICAL": 0.90,
        }

        max_severity = max(severity_weights.get(s.severity, 0.1) for s in signals)
        signal_count_factor = min(len(signals) * 0.1, 0.3)
        return min(max_severity + signal_count_factor, 0.99)


# Module-level singleton
_engine_instance: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    """Get or create the singleton RiskEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RiskEngine()
    return _engine_instance

