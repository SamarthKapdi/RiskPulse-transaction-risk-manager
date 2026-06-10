"""
SQLAlchemy model for per-job aggregated summaries.
"""

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobSummary(Base):
    """Aggregated analytics summary for a completed processing job."""

    __tablename__ = "job_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    total_spend_inr = Column(Numeric(15, 2), nullable=True)
    total_spend_usd = Column(Numeric(15, 2), nullable=True)
    top_merchants = Column(JSON, nullable=True)
    anomaly_count = Column(Integer, nullable=False, default=0)
    narrative = Column(Text, nullable=True)
    risk_level = Column(String(16), nullable=True)

    # Relationship
    job = relationship("Job", back_populates="summary")

    def __repr__(self) -> str:
        return f"<JobSummary job_id={self.job_id} risk={self.risk_level}>"
