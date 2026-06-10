"""
Summary generation service.

Aggregates transaction data, computes statistics, calls the LLM for a
narrative, and persists a JobSummary record.
"""

import logging
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.summary import JobSummary
from app.services import llm_service

logger = logging.getLogger(__name__)


def generate_job_summary(
    db_session: Session,
    job_id: str,
    transactions_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Build and persist an aggregated summary for the given job.

    Parameters
    ----------
    db_session : Session
        Active SQLAlchemy session.
    job_id : str
        UUID of the parent job.
    transactions_df : pd.DataFrame
        Cleaned and anomaly-annotated transaction data.

    Returns
    -------
    dict
        Summary fields written to the database.
    """
    logger.info("Generating summary for job %s", job_id)

    # Ensure amount is numeric
    transactions_df["amount"] = pd.to_numeric(transactions_df["amount"], errors="coerce")

    # ── Total spend by currency ─────────────────────────────────────────
    total_spend_inr: float = 0.0
    total_spend_usd: float = 0.0

    if "currency" in transactions_df.columns:
        inr_mask = transactions_df["currency"].str.upper() == "INR"
        usd_mask = transactions_df["currency"].str.upper() == "USD"
        total_spend_inr = float(transactions_df.loc[inr_mask, "amount"].sum())
        total_spend_usd = float(transactions_df.loc[usd_mask, "amount"].sum())

    # ── Top 3 merchants by transaction count ────────────────────────────
    top_merchants_list: list[str] = []
    if "merchant" in transactions_df.columns:
        top_merchants_series = (
            transactions_df["merchant"]
            .value_counts()
            .head(3)
        )
        top_merchants_list = top_merchants_series.index.tolist()

    # ── Anomaly count ───────────────────────────────────────────────────
    anomaly_count: int = 0
    if "is_anomaly" in transactions_df.columns:
        anomaly_count = int(transactions_df["is_anomaly"].sum())

    # ── Risk level ──────────────────────────────────────────────────────
    if anomaly_count == 0:
        risk_level = "LOW"
    elif anomaly_count <= 5:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    # ── LLM narrative ───────────────────────────────────────────────────
    llm_input: dict[str, Any] = {
        "total_spend_by_currency": {"INR": total_spend_inr, "USD": total_spend_usd},
        "top_merchants": top_merchants_list,
        "anomaly_count": anomaly_count,
        "total_transactions": len(transactions_df),
        "risk_level": risk_level,
    }

    llm_result = llm_service.generate_summary(llm_input)
    narrative: str | None = llm_result.get("narrative")

    # ── Persist to DB ───────────────────────────────────────────────────
    summary = JobSummary(
        job_id=job_id,
        total_spend_inr=Decimal(str(round(total_spend_inr, 2))),
        total_spend_usd=Decimal(str(round(total_spend_usd, 2))),
        top_merchants=top_merchants_list,
        anomaly_count=anomaly_count,
        narrative=narrative,
        risk_level=risk_level,
    )
    db_session.add(summary)
    db_session.flush()
    logger.info("Job summary persisted for job %s (risk=%s)", job_id, risk_level)

    return {
        "total_spend_inr": total_spend_inr,
        "total_spend_usd": total_spend_usd,
        "top_merchants": top_merchants_list,
        "anomaly_count": anomaly_count,
        "narrative": narrative,
        "risk_level": risk_level,
    }
