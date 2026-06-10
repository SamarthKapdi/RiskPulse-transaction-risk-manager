"""
Jobs API router.

Exposes endpoints for uploading CSVs, checking job status, retrieving
results, and listing all jobs.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import Job
from app.models.summary import JobSummary
from app.models.transaction import Transaction
from app.schemas.job import (
    JobListItem,
    JobResultsResponse,
    JobStatusResponse,
    JobUploadResponse,
)
from app.workers.tasks import process_job_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── POST /jobs/upload ────────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=JobUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV file for processing",
)
async def upload_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
) -> JobUploadResponse:
    """Accept a CSV upload, persist it, create a job record, and dispatch processing."""

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted. Please upload a file with a .csv extension.",
        )

    settings = get_settings()

    # Generate a unique filename to avoid collisions
    unique_prefix = str(uuid.uuid4())
    safe_filename = f"{unique_prefix}_{file.filename}"
    filepath = os.path.join(settings.UPLOAD_DIR, safe_filename)

    # Save uploaded file
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)
        logger.info("Saved uploaded file to %s (%d bytes)", filepath, len(contents))
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        ) from exc

    # Create job record
    job = Job(filename=safe_filename, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created job %s for file %s", job.id, safe_filename)

    # Dispatch Celery task
    process_job_task.delay(str(job.id))
    logger.info("Dispatched processing task for job %s", job.id)

    return JobUploadResponse(job_id=str(job.id), status=job.status)


# ── GET /jobs/{job_id}/status ────────────────────────────────────────────────


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Check job processing status",
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Return the current status of a job, with summary if completed."""

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    job: Job | None = db.query(Job).filter(Job.id == job_uuid).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    summary_dict: dict | None = None
    if job.status == "completed" and job.summary is not None:
        s = job.summary
        summary_dict = {
            "total_spend_inr": float(s.total_spend_inr) if s.total_spend_inr else None,
            "total_spend_usd": float(s.total_spend_usd) if s.total_spend_usd else None,
            "top_merchants": s.top_merchants,
            "anomaly_count": s.anomaly_count,
            "narrative": s.narrative,
            "risk_level": s.risk_level,
        }

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        summary=summary_dict,
    )


# ── GET /jobs/{job_id}/results ───────────────────────────────────────────────


@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    summary="Get full job results",
)
def get_job_results(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobResultsResponse:
    """Return complete results including transactions, anomalies, and summary."""

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    job: Job | None = db.query(Job).filter(Job.id == job_uuid).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found.",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed yet. Current status: {job.status}",
        )

    # All transactions
    all_transactions = (
        db.query(Transaction)
        .filter(Transaction.job_id == job_uuid)
        .all()
    )

    # Anomalies only
    anomalies = [t for t in all_transactions if t.is_anomaly]

    # Serialise transactions
    def _txn_dict(t: Transaction) -> dict:
        return {
            "id": t.id,
            "txn_id": t.txn_id,
            "date": str(t.date),
            "merchant": t.merchant,
            "amount": float(t.amount),
            "currency": t.currency,
            "status": t.status,
            "category": t.category,
            "account_id": t.account_id,
            "notes": t.notes,
            "is_anomaly": t.is_anomaly,
            "anomaly_reason": t.anomaly_reason,
            "llm_category": t.llm_category,
            "llm_failed": t.llm_failed,
        }

    cleaned_transactions = [_txn_dict(t) for t in all_transactions]
    anomaly_dicts = [_txn_dict(t) for t in anomalies]

    # Category breakdown (prefer llm_category when available)
    category_breakdown: dict[str, int] = {}
    for t in all_transactions:
        cat = t.llm_category if t.llm_category else t.category
        category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

    # Summary
    summary_dict: dict | None = None
    summary_obj: JobSummary | None = (
        db.query(JobSummary).filter(JobSummary.job_id == job_uuid).first()
    )
    if summary_obj is not None:
        summary_dict = {
            "total_spend_inr": float(summary_obj.total_spend_inr) if summary_obj.total_spend_inr else None,
            "total_spend_usd": float(summary_obj.total_spend_usd) if summary_obj.total_spend_usd else None,
            "top_merchants": summary_obj.top_merchants,
            "anomaly_count": summary_obj.anomaly_count,
            "narrative": summary_obj.narrative,
            "risk_level": summary_obj.risk_level,
        }

    job_dict = {
        "job_id": str(job.id),
        "filename": job.filename,
        "status": job.status,
        "row_count_raw": job.row_count_raw,
        "row_count_clean": job.row_count_clean,
        "created_at": str(job.created_at),
        "completed_at": str(job.completed_at) if job.completed_at else None,
    }

    return JobResultsResponse(
        job=job_dict,
        cleaned_transactions=cleaned_transactions,
        anomalies=anomaly_dicts,
        category_breakdown=category_breakdown,
        summary=summary_dict,
    )


# ── GET /jobs/ ───────────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[JobListItem],
    summary="List all jobs",
)
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[JobListItem]:
    """Return a list of all jobs, optionally filtered by status."""

    query = db.query(Job)
    if status_filter:
        query = query.filter(Job.status == status_filter)

    query = query.order_by(Job.created_at.desc())
    jobs = query.all()

    return [
        JobListItem(
            job_id=str(j.id),
            filename=j.filename,
            status=j.status,
            row_count=j.row_count_clean,
            created_at=j.created_at,
        )
        for j in jobs
    ]
