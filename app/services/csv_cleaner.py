"""
CSV cleaning service.

Reads a raw CSV file, normalises its contents, and returns a clean
pandas DataFrame ready for downstream processing.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Date formats we accept (order matters – most specific first)
_DATE_FORMATS: list[str] = [
    "%d-%m-%Y",   # DD-MM-YYYY
    "%Y/%m/%d",   # YYYY/MM/DD
    "%Y-%m-%d",   # YYYY-MM-DD (ISO)
    "%m/%d/%Y",   # MM/DD/YYYY
    "%d/%m/%Y",   # DD/MM/YYYY
]


def _parse_date(value: str) -> Optional[str]:
    """Try multiple date formats and return YYYY-MM-DD or None."""
    if pd.isna(value):
        return None
    raw = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning("Unable to parse date value: %s", raw)
    return None


def _clean_amount(value: str) -> Optional[float]:
    """Strip currency symbols/commas from an amount string and convert to float."""
    if pd.isna(value):
        return None
    raw = str(value).strip()
    # Remove common currency symbols and commas
    cleaned = re.sub(r"[$€£,]", "", raw)
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Unable to convert amount value to float: %s", raw)
        return None


def clean_csv(filepath: str) -> tuple[pd.DataFrame, int]:
    """
    Read and clean a CSV file.

    Returns
    -------
    tuple[pd.DataFrame, int]
        (cleaned DataFrame, original raw row count)
    """
    logger.info("Reading CSV file: %s", filepath)
    df = pd.read_csv(filepath, dtype=str)  # read everything as str first
    raw_row_count: int = len(df)
    logger.info("Raw row count: %d", raw_row_count)

    # ── 1. Strip whitespace from column names ───────────────────────────
    df.columns = df.columns.str.strip().str.lower()

    # ── 2. Remove exact duplicate rows ──────────────────────────────────
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    if dropped:
        logger.info("Dropped %d exact duplicate rows", dropped)

    # ── 3. Normalise dates ──────────────────────────────────────────────
    if "date" in df.columns:
        df["date"] = df["date"].apply(_parse_date)
        null_dates = df["date"].isna().sum()
        if null_dates:
            logger.warning("Dropping %d rows with unparseable dates", null_dates)
            df = df.dropna(subset=["date"])

    # ── 4. Clean amount column ──────────────────────────────────────────
    if "amount" in df.columns:
        df["amount"] = df["amount"].apply(_clean_amount)
        null_amounts = df["amount"].isna().sum()
        if null_amounts:
            logger.warning("Dropping %d rows with invalid amounts", null_amounts)
            df = df.dropna(subset=["amount"])

    # ── 5. Uppercase status ─────────────────────────────────────────────
    if "status" in df.columns:
        df["status"] = df["status"].astype(str).str.strip().str.upper()

    # ── 6. Uppercase currency ───────────────────────────────────────────
    if "currency" in df.columns:
        df["currency"] = df["currency"].astype(str).str.strip().str.upper()

    # ── 7. Fill missing categories ──────────────────────────────────────
    if "category" in df.columns:
        df["category"] = df["category"].fillna("Uncategorised")
        df["category"] = df["category"].apply(
            lambda v: "Uncategorised" if str(v).strip() == "" else str(v).strip()
        )
    else:
        df["category"] = "Uncategorised"

    # ── 8. Generate UUID for missing txn_id ─────────────────────────────
    if "txn_id" in df.columns:
        df["txn_id"] = df["txn_id"].apply(
            lambda v: str(uuid.uuid4()) if pd.isna(v) or str(v).strip() == "" else str(v).strip()
        )
    else:
        df["txn_id"] = [str(uuid.uuid4()) for _ in range(len(df))]

    # ── 9. Strip whitespace from remaining string columns ───────────────
    for col in ("merchant", "account_id", "notes"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            # Replace literal 'nan' strings produced by astype on NaN
            df[col] = df[col].replace("nan", "")

    # Make notes truly nullable
    if "notes" in df.columns:
        df["notes"] = df["notes"].replace("", None)

    df = df.reset_index(drop=True)
    logger.info("Cleaned row count: %d", len(df))
    return df, raw_row_count
