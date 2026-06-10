"""
SQLAlchemy model for individual transactions parsed from CSV files.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Transaction(Base):
    """A single financial transaction belonging to a processing job."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    txn_id = Column(String(128), nullable=False)
    date = Column(Date, nullable=False)
    merchant = Column(String(256), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(32), nullable=False)
    category = Column(String(128), nullable=False)
    account_id = Column(String(128), nullable=False)
    notes = Column(Text, nullable=True)

    # Anomaly detection fields
    is_anomaly = Column(Boolean, nullable=False, default=False)
    anomaly_reason = Column(String(256), nullable=True)

    # LLM enrichment fields
    llm_category = Column(String(128), nullable=True)
    llm_raw_response = Column(Text, nullable=True)
    llm_failed = Column(Boolean, nullable=False, default=False)

    # Relationship
    job = relationship("Job", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} txn_id={self.txn_id} amount={self.amount}>"
