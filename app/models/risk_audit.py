"""
SQLAlchemy models for risk audit trail.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class RiskAuditTrail(Base):
    """
    Audit trail for risk decisions.
    Records the full context of a decision for compliance and investigation.
    """
    __tablename__ = "risk_audit_trail"

    transaction_id = Column(String(50), primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Model details
    model_version = Column(String(20), nullable=False)
    risk_score = Column(Float, nullable=False, index=True)
    
    # Decision
    risk_level = Column(String(20), nullable=False, index=True)
    decision = Column(String(20), nullable=False, index=True)
    requires_review = Column(Boolean, nullable=False, default=False)
    
    # Evidence (Stored as JSON for flexibility)
    signals = Column(JSON, nullable=False)
    
    # Policy details
    policy_version = Column(String(20), nullable=False)
    
    # Explanation
    explanation = Column(String, nullable=True)
