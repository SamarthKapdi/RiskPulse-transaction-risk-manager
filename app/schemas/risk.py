"""
Pydantic v2 schemas for the RiskPulse risk API.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# â”€â”€ Transaction Input â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TransactionAnalysisRequest(BaseModel):
    """Single transaction for risk analysis."""
    transaction_id: Optional[str] = None
    customer_id: str
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", max_length=3)
    timestamp: Optional[str] = None
    payment_method: Optional[str] = None
    device_id: Optional[str] = None
    country: Optional[str] = None
    account_age_days: Optional[int] = None
    transaction_velocity: Optional[float] = None
    amount_vs_customer_baseline: Optional[float] = None
    amount_vs_merchant_baseline: Optional[float] = None
    transactions_last_5m: Optional[int] = None
    transactions_last_1h: Optional[int] = None
    transactions_last_24h: Optional[int] = None
    failed_attempts: Optional[int] = 0
    new_device: Optional[bool] = False
    new_location: Optional[bool] = False
    distance_from_previous: Optional[float] = 0.0
    historical_transaction_count: Optional[int] = None
    historical_avg_amount: Optional[float] = None
    historical_std_amount: Optional[float] = None


# â”€â”€ Risk Signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class RiskSignalOut(BaseModel):
    """A single risk signal."""
    signal: str
    value: float
    severity: str
    evidence: str


# â”€â”€ Risk Result â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class RiskResult(BaseModel):
    """Complete risk assessment result."""
    transaction_id: str
    risk_score: float
    risk_level: str
    confidence: float
    decision: str
    action_details: str
    requires_review: bool
    model_version: str
    policy_version: str
    signals: list[RiskSignalOut]
    signal_count: int
    timestamp: str


class RiskTransactionSummary(BaseModel):
    """Persisted transaction summary for historical dashboard views."""
    transaction_id: str
    timestamp: str
    risk_score: float
    risk_level: str
    decision: str
    requires_review: bool
    signals: list[RiskSignalOut]
    signal_count: int
    model_version: str
    policy_version: str


# â”€â”€ Explanation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class RiskExplanation(BaseModel):
    """Explanation for a risk decision."""
    transaction_id: str
    explanation: str
    evidence_summary: str
    evidence_items: list[str]
    recommended_action: str
    risk_level: str
    risk_score: float
    decision: str
    source: str  # "gemini" or "deterministic"


# â”€â”€ Batch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class BatchAnalysisRequest(BaseModel):
    """Batch risk analysis request."""
    transactions: list[TransactionAnalysisRequest]


class BatchAnalysisResponse(BaseModel):
    """Batch risk analysis response."""
    results: list[RiskResult]
    total: int
    high_risk_count: int
    review_required_count: int


# â”€â”€ Evaluation Metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class EvaluationMetrics(BaseModel):
    """Model evaluation metrics."""
    model: str
    threshold: float
    precision: float
    recall: float
    f1: float
    pr_auc: float
    roc_auc: float
    false_positive_rate: float
    false_negative_rate: float
    confusion_matrix: dict
    cost_analysis: dict
    dataset: dict


# â”€â”€ Audit Record â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class AuditRecord(BaseModel):
    """Audit trail record for a risk decision."""
    transaction_id: str
    timestamp: str
    model_version: str
    risk_score: float
    risk_level: str
    decision: str
    requires_review: bool
    signals: list[dict]
    evidence: Optional[str] = None
    policy_version: str
    explanation: Optional[str] = None


# â”€â”€ Risk Metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class RiskMetrics(BaseModel):
    """Aggregate risk metrics."""
    total_analyzed: int
    risk_distribution: dict[str, int]
    decision_distribution: dict[str, int]
    review_queue_size: int
    avg_risk_score: float
    model_version: str

