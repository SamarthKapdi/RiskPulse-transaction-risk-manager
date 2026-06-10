"""
Tests for the anomaly detection service.

Validates statistical outlier detection, domestic-merchant-foreign-currency
rule, no false-positives on clean data, and combined rule triggers.
"""

import pandas as pd
import pytest

from app.services.anomaly_detector import detect_anomalies


def _base_row(**overrides) -> dict:
    """Return a single-row dict with sensible defaults, applying overrides."""
    row = {
        "txn_id": "T001",
        "date": "2024-01-01",
        "merchant": "GenericMerchant",
        "amount": 500.0,
        "currency": "INR",
        "status": "SUCCESS",
        "category": "Shopping",
        "account_id": "ACC001",
        "notes": "",
    }
    row.update(overrides)
    return row


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Statistical outlier detection
# ---------------------------------------------------------------------------
class TestStatisticalOutlier:
    def test_high_amount_flagged(self):
        """A single extremely high amount among normal ones should be flagged."""
        rows = [
            _base_row(txn_id=f"T{i}", amount=500.0, account_id="ACC001")
            for i in range(20)
        ]
        # Inject an outlier (well above 3 * median of 500 = 1500)
        rows.append(
            _base_row(txn_id="T_OUTLIER", amount=99999.0, account_id="ACC001")
        )
        df = _make_df(rows)
        result = detect_anomalies(df)
        outlier = result[result["txn_id"] == "T_OUTLIER"].iloc[0]
        assert outlier["is_anomaly"] == True
        assert "STATISTICAL_OUTLIER" in outlier["anomaly_reason"]

    def test_normal_amount_not_flagged(self):
        """An amount within 3x median should not be flagged."""
        rows = [
            _base_row(txn_id=f"T{i}", amount=500.0, account_id="ACC001")
            for i in range(10)
        ]
        # Add an amount at exactly 3x median — should NOT be flagged (> 3x, not >=)
        rows.append(
            _base_row(txn_id="T_BORDER", amount=1500.0, account_id="ACC001")
        )
        df = _make_df(rows)
        result = detect_anomalies(df)
        border = result[result["txn_id"] == "T_BORDER"].iloc[0]
        assert border["is_anomaly"] == False


# ---------------------------------------------------------------------------
# Domestic merchant with foreign currency
# ---------------------------------------------------------------------------
class TestDomesticMerchantUsd:
    def test_swiggy_usd_flagged(self):
        """Swiggy (domestic) transacting in USD should be flagged."""
        rows = [_base_row(merchant="Swiggy", currency="USD")]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True
        assert "DOMESTIC_MERCHANT_USD" in result["anomaly_reason"].iloc[0]

    def test_ola_usd_flagged(self):
        """Ola (domestic) transacting in USD should be flagged."""
        rows = [_base_row(merchant="Ola", currency="USD")]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True
        assert "DOMESTIC_MERCHANT_USD" in result["anomaly_reason"].iloc[0]

    def test_irctc_usd_flagged(self):
        """IRCTC (domestic) transacting in USD should be flagged."""
        rows = [_base_row(merchant="IRCTC", currency="USD")]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == True
        assert "DOMESTIC_MERCHANT_USD" in result["anomaly_reason"].iloc[0]

    def test_domestic_merchant_inr_not_flagged(self):
        """Swiggy in INR should NOT be flagged."""
        rows = [_base_row(merchant="Swiggy", currency="INR")]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == False

    def test_foreign_merchant_usd_not_flagged(self):
        """A non-domestic merchant in USD should NOT be flagged."""
        rows = [_base_row(merchant="Amazon", currency="USD")]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].iloc[0] == False


# ---------------------------------------------------------------------------
# No anomaly on clean data
# ---------------------------------------------------------------------------
class TestNoAnomaly:
    def test_normal_transactions(self):
        """Normal, in-range transactions should not be flagged."""
        rows = [
            _base_row(txn_id=f"T{i}", amount=float(400 + i * 10), account_id="ACC001")
            for i in range(10)
        ]
        df = _make_df(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].sum() == 0


# ---------------------------------------------------------------------------
# Both rules triggered
# ---------------------------------------------------------------------------
class TestBothRules:
    def test_outlier_and_domestic_currency(self):
        """A transaction that is both an outlier and has wrong currency."""
        rows = [
            _base_row(txn_id=f"T{i}", amount=500.0, account_id="ACC001")
            for i in range(20)
        ]
        # This row is both a statistical outlier and a domestic-merchant-foreign-currency anomaly
        rows.append(
            _base_row(
                txn_id="T_BOTH",
                amount=99999.0,
                merchant="Swiggy",
                currency="USD",
                account_id="ACC001",
            )
        )
        df = _make_df(rows)
        result = detect_anomalies(df)
        both_row = result[result["txn_id"] == "T_BOTH"].iloc[0]
        assert both_row["is_anomaly"] == True
        assert "STATISTICAL_OUTLIER" in both_row["anomaly_reason"]
        assert "DOMESTIC_MERCHANT_USD" in both_row["anomaly_reason"]
