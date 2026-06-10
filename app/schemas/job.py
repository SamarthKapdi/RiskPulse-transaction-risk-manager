"""
Pydantic v2 request / response schemas for the jobs API.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ── Upload ───────────────────────────────────────────────────────────────────

class JobUploadResponse(BaseModel):
    """Returned immediately after a CSV is uploaded."""

    job_id: str
    status: str


# ── Status ───────────────────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    """Lightweight status check for a job."""

    job_id: str
    status: str
    summary: Optional[dict[str, Any]] = None


# ── Transaction output ───────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    """Serialised representation of a single transaction row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    txn_id: str
    date: date
    merchant: str
    amount: Decimal
    currency: str
    status: str
    category: str
    account_id: str
    notes: Optional[str] = None
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_raw_response: Optional[str] = None
    llm_failed: bool


# ── Summary output ───────────────────────────────────────────────────────────

class JobSummaryOut(BaseModel):
    """Serialised representation of a job summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    total_spend_inr: Optional[Decimal] = None
    total_spend_usd: Optional[Decimal] = None
    top_merchants: Optional[list[Any]] = None
    anomaly_count: int
    narrative: Optional[str] = None
    risk_level: Optional[str] = None


# ── Full results ─────────────────────────────────────────────────────────────

class JobResultsResponse(BaseModel):
    """Complete results bundle for a finished job."""

    job: dict[str, Any]
    cleaned_transactions: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    category_breakdown: dict[str, int]
    summary: Optional[dict[str, Any]] = None


# ── Job listing ──────────────────────────────────────────────────────────────

class JobListItem(BaseModel):
    """Compact representation used when listing multiple jobs."""

    job_id: str
    filename: str
    status: str
    row_count: Optional[int] = None
    created_at: datetime


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Simple health-check response."""

    status: str
