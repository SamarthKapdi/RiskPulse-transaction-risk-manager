"""
Rule-based anomaly detection for transaction DataFrames.

Rules
-----
1. STATISTICAL_OUTLIER  – amount > 3 × median for that account_id
2. DOMESTIC_MERCHANT_USD – domestic-only merchant transacting in USD
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Merchants that only operate domestically (India)
_DOMESTIC_MERCHANTS: set[str] = {"Swiggy", "Ola", "IRCTC"}


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Annotate each row with ``is_anomaly`` and ``anomaly_reason``.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned transaction data. Must contain columns:
        account_id, amount, merchant, currency.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with ``is_anomaly`` (bool) and ``anomaly_reason``
        (str | None) columns populated.
    """
    logger.info("Running anomaly detection on %d rows", len(df))

    # Initialise anomaly columns
    df["is_anomaly"] = False
    df["anomaly_reason"] = None

    # Ensure amount is numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # ── Rule 1: Statistical outlier ─────────────────────────────────────
    median_by_account: pd.Series = df.groupby("account_id")["amount"].transform("median")
    stat_mask = df["amount"] > 3 * median_by_account

    stat_count = stat_mask.sum()
    if stat_count:
        logger.info("STATISTICAL_OUTLIER flagged: %d rows", stat_count)
        df.loc[stat_mask, "is_anomaly"] = True
        df.loc[stat_mask, "anomaly_reason"] = "STATISTICAL_OUTLIER"

    # ── Rule 2: Domestic merchant with USD currency ─────────────────────
    # Case-insensitive comparison for merchant names
    merchant_upper = df["merchant"].astype(str).str.strip()
    domestic_mask = (
        merchant_upper.isin(_DOMESTIC_MERCHANTS)
        & (df["currency"].astype(str).str.upper() == "USD")
    )

    domestic_count = domestic_mask.sum()
    if domestic_count:
        logger.info("DOMESTIC_MERCHANT_USD flagged: %d rows", domestic_count)

    # Combine reasons when both rules fire for the same row
    both_mask = stat_mask & domestic_mask
    only_domestic_mask = domestic_mask & ~stat_mask

    if both_mask.sum():
        df.loc[both_mask, "anomaly_reason"] = "STATISTICAL_OUTLIER;DOMESTIC_MERCHANT_USD"

    if only_domestic_mask.sum():
        df.loc[only_domestic_mask, "is_anomaly"] = True
        df.loc[only_domestic_mask, "anomaly_reason"] = "DOMESTIC_MERCHANT_USD"

    total_anomalies = df["is_anomaly"].sum()
    logger.info("Total anomalies detected: %d", total_anomalies)
    return df
