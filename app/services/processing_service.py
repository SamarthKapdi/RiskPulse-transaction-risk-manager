"""
Pipeline orchestration service.

Coordinates the full processing pipeline for a single job:
CSV cleaning → anomaly detection → LLM classification → DB persistence → summary.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.job import Job
from app.models.transaction import Transaction
from app.services import anomaly_detector, csv_cleaner, llm_service, summary_service

logger = logging.getLogger(__name__)


def _build_transaction_records(
    job_id: str,
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Convert a DataFrame to a list of dicts suitable for bulk insert."""
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        records.append(
            {
                "job_id": job_id,
                "txn_id": row.get("txn_id", ""),
                "date": row.get("date"),
                "merchant": row.get("merchant", ""),
                "amount": row.get("amount"),
                "currency": row.get("currency", ""),
                "status": row.get("status", ""),
                "category": row.get("category", "Uncategorised"),
                "account_id": row.get("account_id", ""),
                "notes": row.get("notes") if pd.notna(row.get("notes")) else None,
                "is_anomaly": bool(row.get("is_anomaly", False)),
                "anomaly_reason": row.get("anomaly_reason") if pd.notna(row.get("anomaly_reason")) else None,
                "llm_category": row.get("llm_category") if pd.notna(row.get("llm_category")) else None,
                "llm_raw_response": row.get("llm_raw_response") if pd.notna(row.get("llm_raw_response")) else None,
                "llm_failed": bool(row.get("llm_failed", False)),
            }
        )
    return records


def process_job(job_id: str) -> None:
    """
    Execute the full processing pipeline for a job.

    Steps
    -----
    1. Mark job as *processing*
    2. Clean the CSV
    3. Detect anomalies
    4. Classify uncategorised rows via LLM
    5. Bulk-insert transactions
    6. Generate & persist summary
    7. Mark job as *completed*

    On any unhandled exception the job is marked *failed* with the error
    message recorded.
    """
    settings = get_settings()
    db: Session = SessionLocal()

    try:
        # ── 1. Fetch job and set status ─────────────────────────────────
        job_uuid = uuid.UUID(job_id)
        job: Job | None = db.query(Job).filter(Job.id == job_uuid).first()
        if job is None:
            logger.error("Job %s not found in database", job_id)
            return

        job.status = "processing"
        db.commit()
        logger.info("Job %s status set to processing", job_id)

        # ── 2. Read & clean CSV ─────────────────────────────────────────
        filepath = os.path.join(settings.UPLOAD_DIR, job.filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"CSV file not found: {filepath}")

        cleaned_df, raw_row_count = csv_cleaner.clean_csv(filepath)

        job.row_count_raw = raw_row_count
        job.row_count_clean = len(cleaned_df)
        db.commit()
        logger.info(
            "Job %s: raw=%d, clean=%d rows",
            job_id,
            raw_row_count,
            len(cleaned_df),
        )

        # ── 3. Anomaly detection ────────────────────────────────────────
        cleaned_df = anomaly_detector.detect_anomalies(cleaned_df)

        # ── 4. LLM classification for uncategorised rows ────────────────
        uncategorised_mask = cleaned_df["category"] == "Uncategorised"
        uncategorised_df = cleaned_df[uncategorised_mask]

        # Initialise LLM columns
        cleaned_df["llm_category"] = None
        cleaned_df["llm_raw_response"] = None
        cleaned_df["llm_failed"] = False

        if len(uncategorised_df) > 0:
            logger.info(
                "Job %s: %d uncategorised rows queued for LLM",
                job_id,
                len(uncategorised_df),
            )
            batch_input: list[dict[str, str]] = [
                {
                    "merchant": str(row.get("merchant", "")),
                    "notes": str(row.get("notes", "")) if pd.notna(row.get("notes")) else "",
                }
                for _, row in uncategorised_df.iterrows()
            ]

            llm_results = llm_service.classify_transactions_batch(batch_input)

            # Map results back into the DataFrame
            uncat_indices = uncategorised_df.index.tolist()
            for idx, result in zip(uncat_indices, llm_results):
                cleaned_df.at[idx, "llm_category"] = result.get("category", "Other")
                cleaned_df.at[idx, "llm_raw_response"] = result.get("raw_response")
                cleaned_df.at[idx, "llm_failed"] = result.get("llm_failed", False)
        else:
            logger.info("Job %s: no uncategorised rows – skipping LLM", job_id)

        # ── 5. Bulk insert transactions ─────────────────────────────────
        records = _build_transaction_records(job_id, cleaned_df)
        db.bulk_insert_mappings(Transaction, records)
        db.flush()
        logger.info("Job %s: %d transactions inserted", job_id, len(records))

        # ── 6. Generate summary ─────────────────────────────────────────
        summary_service.generate_job_summary(db, job_id, cleaned_df)

        # ── 7. Mark complete ────────────────────────────────────────────
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        db.rollback()
        try:
            job_uuid = uuid.UUID(job_id)
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as inner_exc:
            logger.exception(
                "Failed to update job %s status to failed: %s",
                job_id,
                inner_exc,
            )
    finally:
        db.close()
