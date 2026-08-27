"""
Risk Signal Engine for RiskPulse.

Generates interpretable risk signals from transaction data.
Evolves the existing anomaly_detector.py into a comprehensive signal system.

Each signal contains:
- signal: signal name
- value: numeric value
- severity: LOW / MEDIUM / HIGH / CRITICAL
- evidence: human-readable explanation
"""

import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskSignal:
    """A single interpretable risk signal."""
    signal: str
    value: float
    severity: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


class RiskSignalEngine:
    """
    Generate interpretable risk signals from transaction features.

    Reuses statistical outlier logic from the existing anomaly detector
    and adds new behavioral/contextual signals.
    """

    def __init__(self, thresholds: Optional[dict] = None):
        """
        Parameters
        ----------
        thresholds : dict
            Custom thresholds for signal generation. Defaults provided.
        """
        self.thresholds = thresholds or {
            "amount_z_score_medium": 2.0,
            "amount_z_score_high": 3.0,
            "amount_z_score_critical": 5.0,
            "velocity_5m_medium": 3,
            "velocity_5m_high": 5,
            "velocity_1h_medium": 10,
            "velocity_1h_high": 20,
            "distance_medium_km": 500,
            "distance_high_km": 2000,
            "failed_attempts_medium": 2,
            "failed_attempts_high": 3,
            "account_age_young_days": 30,
            "account_age_very_young_days": 7,
        }

    def generate_signals(self, transaction: dict) -> list[RiskSignal]:
        """
        Generate all risk signals for a single transaction.

        Parameters
        ----------
        transaction : dict
            Transaction data including derived features.

        Returns
        -------
        list[RiskSignal]
            List of detected risk signals.
        """
        signals = []

        # 1. Amount anomaly
        sig = self._check_amount_anomaly(transaction)
        if sig:
            signals.append(sig)

        # 2. Velocity anomaly
        sig = self._check_velocity_anomaly(transaction)
        if sig:
            signals.append(sig)

        # 3. Location anomaly
        sig = self._check_location_anomaly(transaction)
        if sig:
            signals.append(sig)

        # 4. Device anomaly
        sig = self._check_device_anomaly(transaction)
        if sig:
            signals.append(sig)

        # 5. Failed attempts
        sig = self._check_failed_attempts(transaction)
        if sig:
            signals.append(sig)

        # 6. Account age signal
        sig = self._check_account_age(transaction)
        if sig:
            signals.append(sig)

        # 7. Merchant anomaly (amount vs merchant baseline)
        sig = self._check_merchant_anomaly(transaction)
        if sig:
            signals.append(sig)

        # 8. Behavioral deviation
        sig = self._check_behavioral_deviation(transaction)
        if sig:
            signals.append(sig)

        return signals

    def _check_amount_anomaly(self, txn: dict) -> Optional[RiskSignal]:
        """Check if transaction amount deviates from customer baseline."""
        z_score = txn.get("amount_vs_customer_baseline", 0)
        t = self.thresholds

        if abs(z_score) >= t["amount_z_score_critical"]:
            return RiskSignal(
                signal="amount_anomaly",
                value=round(z_score, 2),
                severity=Severity.CRITICAL,
                evidence=f"Transaction amount is {abs(z_score):.1f}Ã— standard deviations "
                         f"from customer's historical mean",
            )
        elif abs(z_score) >= t["amount_z_score_high"]:
            return RiskSignal(
                signal="amount_anomaly",
                value=round(z_score, 2),
                severity=Severity.HIGH,
                evidence=f"Transaction amount deviates {abs(z_score):.1f}Ïƒ from customer baseline",
            )
        elif abs(z_score) >= t["amount_z_score_medium"]:
            return RiskSignal(
                signal="amount_anomaly",
                value=round(z_score, 2),
                severity=Severity.MEDIUM,
                evidence=f"Transaction amount is moderately unusual ({abs(z_score):.1f}Ïƒ from mean)",
            )
        return None

    def _check_velocity_anomaly(self, txn: dict) -> Optional[RiskSignal]:
        """Check transaction velocity (frequency in recent windows)."""
        v5m = txn.get("transactions_last_5m", 1)
        v1h = txn.get("transactions_last_1h", 1)
        t = self.thresholds

        if v5m >= t["velocity_5m_high"]:
            return RiskSignal(
                signal="velocity_anomaly",
                value=float(v5m),
                severity=Severity.CRITICAL,
                evidence=f"{v5m} transactions occurred within 5 minutes",
            )
        elif v5m >= t["velocity_5m_medium"]:
            return RiskSignal(
                signal="velocity_anomaly",
                value=float(v5m),
                severity=Severity.HIGH,
                evidence=f"{v5m} transactions in last 5 minutes indicates rapid-fire activity",
            )
        elif v1h >= t["velocity_1h_high"]:
            return RiskSignal(
                signal="velocity_anomaly",
                value=float(v1h),
                severity=Severity.HIGH,
                evidence=f"{v1h} transactions in last hour exceeds normal pattern",
            )
        elif v1h >= t["velocity_1h_medium"]:
            return RiskSignal(
                signal="velocity_anomaly",
                value=float(v1h),
                severity=Severity.MEDIUM,
                evidence=f"{v1h} transactions in last hour is above average",
            )
        return None

    def _check_location_anomaly(self, txn: dict) -> Optional[RiskSignal]:
        """Check for unusual location / impossible travel."""
        distance = txn.get("distance_from_previous", 0)
        new_location = txn.get("new_location", 0)
        t = self.thresholds

        if distance >= t["distance_high_km"]:
            return RiskSignal(
                signal="location_anomaly",
                value=round(distance, 1),
                severity=Severity.HIGH,
                evidence=f"Transaction location is {distance:,.0f} km from previous transaction "
                         f"(possible impossible-travel pattern)",
            )
        elif distance >= t["distance_medium_km"]:
            return RiskSignal(
                signal="location_anomaly",
                value=round(distance, 1),
                severity=Severity.MEDIUM,
                evidence=f"Transaction originated {distance:,.0f} km from previous location",
            )
        elif new_location:
            return RiskSignal(
                signal="location_anomaly",
                value=1.0,
                severity=Severity.LOW,
                evidence="Transaction from a country not previously associated with this customer",
            )
        return None

    def _check_device_anomaly(self, txn: dict) -> Optional[RiskSignal]:
        """Check if device is new for this customer."""
        new_device = txn.get("new_device", False)
        amount_z = abs(txn.get("amount_vs_customer_baseline", 0))

        if new_device and amount_z >= 2.0:
            return RiskSignal(
                signal="device_anomaly",
                value=1.0,
                severity=Severity.HIGH,
                evidence="New device combined with unusual transaction amount",
            )
        elif new_device:
            return RiskSignal(
                signal="device_anomaly",
                value=1.0,
                severity=Severity.MEDIUM,
                evidence="Device has not previously been associated with this account",
            )
        return None

    def _check_failed_attempts(self, txn: dict) -> Optional[RiskSignal]:
        """Check for repeated failed attempts before this transaction."""
        failed = txn.get("failed_attempts", 0)
        t = self.thresholds

        if failed >= t["failed_attempts_high"]:
            return RiskSignal(
                signal="failed_attempt_signal",
                value=float(failed),
                severity=Severity.HIGH,
                evidence=f"{failed} failed transaction attempts preceded this successful one",
            )
        elif failed >= t["failed_attempts_medium"]:
            return RiskSignal(
                signal="failed_attempt_signal",
                value=float(failed),
                severity=Severity.MEDIUM,
                evidence=f"{failed} failed attempts before this transaction",
            )
        return None

    def _check_account_age(self, txn: dict) -> Optional[RiskSignal]:
        """Check if account is very new (higher fraud risk)."""
        age_days = txn.get("account_age_days", 365)
        t = self.thresholds

        if age_days <= t["account_age_very_young_days"]:
            return RiskSignal(
                signal="account_age_signal",
                value=float(age_days),
                severity=Severity.HIGH,
                evidence=f"Account is only {age_days} days old (very new account)",
            )
        elif age_days <= t["account_age_young_days"]:
            return RiskSignal(
                signal="account_age_signal",
                value=float(age_days),
                severity=Severity.MEDIUM,
                evidence=f"Account is {age_days} days old (relatively new)",
            )
        return None

    def _check_merchant_anomaly(self, txn: dict) -> Optional[RiskSignal]:
        """Check if amount is unusual for this merchant."""
        z_score = txn.get("amount_vs_merchant_baseline", 0)

        if abs(z_score) >= 4.0:
            return RiskSignal(
                signal="merchant_anomaly",
                value=round(z_score, 2),
                severity=Severity.HIGH,
                evidence=f"Transaction amount is {abs(z_score):.1f}Ïƒ from merchant's average",
            )
        elif abs(z_score) >= 2.5:
            return RiskSignal(
                signal="merchant_anomaly",
                value=round(z_score, 2),
                severity=Severity.MEDIUM,
                evidence=f"Amount is unusual for this merchant ({abs(z_score):.1f}Ïƒ from mean)",
            )
        return None

    def _check_behavioral_deviation(self, txn: dict) -> Optional[RiskSignal]:
        """Check for overall behavioral deviation (multiple weak signals)."""
        deviation_score = 0.0

        # Count weak signals
        if abs(txn.get("amount_vs_customer_baseline", 0)) >= 1.5:
            deviation_score += 1
        if txn.get("new_location", 0):
            deviation_score += 1
        if txn.get("new_device", False):
            deviation_score += 1
        if txn.get("failed_attempts", 0) >= 1:
            deviation_score += 1
        if txn.get("transactions_last_1h", 1) >= 5:
            deviation_score += 1

        if deviation_score >= 4:
            return RiskSignal(
                signal="behavioral_deviation",
                value=deviation_score,
                severity=Severity.CRITICAL,
                evidence=f"Multiple behavioral deviations detected ({int(deviation_score)} signals)",
            )
        elif deviation_score >= 3:
            return RiskSignal(
                signal="behavioral_deviation",
                value=deviation_score,
                severity=Severity.HIGH,
                evidence=f"Significant behavioral deviation ({int(deviation_score)} weak signals combined)",
            )
        return None

