"""
Tests for the CSV cleaner service.

Validates date normalisation, currency symbol removal, status uppercasing,
currency normalisation, missing category fill, duplicate removal, and
txn_id generation.
"""

import os
import tempfile

import pandas as pd
import pytest

from app.services.csv_cleaner import clean_csv


def _write_csv(rows: list[str]) -> str:
    """Write CSV lines to a temp file and return its path."""
    header = "txn_id,date,merchant,amount,currency,status,category,account_id,notes"
    content = "\n".join([header] + rows) + "\n"
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------
class TestNormalizeDates:
    def test_dd_mm_yyyy(self):
        path = _write_csv(["T001,25-12-2024,TestMerchant,100,INR,SUCCESS,Food,ACC001,"])
        df, _ = clean_csv(path)
        assert df["date"].iloc[0] == "2024-12-25"
        os.unlink(path)

    def test_yyyy_slash_mm_dd(self):
        path = _write_csv(["T002,2024/06/15,Amazon,200,USD,FAILED,Shopping,ACC002,"])
        df, _ = clean_csv(path)
        assert df["date"].iloc[0] == "2024-06-15"
        os.unlink(path)

    def test_iso_format_passthrough(self):
        path = _write_csv(["T003,2024-03-10,Flipkart,300,INR,SUCCESS,Shopping,ACC003,"])
        df, _ = clean_csv(path)
        assert df["date"].iloc[0] == "2024-03-10"
        os.unlink(path)


# ---------------------------------------------------------------------------
# Currency symbol removal
# ---------------------------------------------------------------------------
class TestRemoveCurrencySymbols:
    def test_dollar_sign(self):
        path = _write_csv(["T003,$1200,Apple,1200,USD,SUCCESS,Tech,ACC003,"])
        # Fix: amount is second positional column, let's write properly
        os.unlink(path)
        path = _write_csv(["T003,2024-01-01,Apple,$1200,USD,SUCCESS,Tech,ACC003,"])
        df, _ = clean_csv(path)
        assert df["amount"].iloc[0] == 1200.0
        os.unlink(path)

    def test_comma_in_amount(self):
        path = _write_csv(['T004,2024-01-01,Apple,"1,200.50",USD,SUCCESS,Tech,ACC003,'])
        df, _ = clean_csv(path)
        assert df["amount"].iloc[0] == 1200.50
        os.unlink(path)


# ---------------------------------------------------------------------------
# Status uppercasing
# ---------------------------------------------------------------------------
class TestUppercaseStatus:
    def test_lowercase_status(self):
        path = _write_csv(["T005,2024-01-01,Zomato,100,INR,success,Food,ACC005,"])
        df, _ = clean_csv(path)
        assert df["status"].iloc[0] == "SUCCESS"
        os.unlink(path)

    def test_mixed_case_status(self):
        path = _write_csv(["T006,2024-01-01,Uber,100,INR,Pending,Transport,ACC006,"])
        df, _ = clean_csv(path)
        assert df["status"].iloc[0] == "PENDING"
        os.unlink(path)


# ---------------------------------------------------------------------------
# Currency normalisation
# ---------------------------------------------------------------------------
class TestCurrencyNormalization:
    def test_lowercase_currency(self):
        path = _write_csv(["T007,2024-01-01,Swiggy,100,inr,SUCCESS,Food,ACC007,"])
        df, _ = clean_csv(path)
        assert df["currency"].iloc[0] == "INR"
        os.unlink(path)


# ---------------------------------------------------------------------------
# Missing category fill
# ---------------------------------------------------------------------------
class TestFillMissingCategory:
    def test_empty_category(self):
        path = _write_csv(["T008,2024-01-01,TestMerchant,100,INR,SUCCESS,,ACC008,"])
        df, _ = clean_csv(path)
        assert df["category"].iloc[0] == "Uncategorised"
        os.unlink(path)


# ---------------------------------------------------------------------------
# Duplicate removal
# ---------------------------------------------------------------------------
class TestRemoveDuplicates:
    def test_exact_duplicates(self):
        row = "T010,2024-01-01,Swiggy,100,INR,SUCCESS,Food,ACC010,"
        path = _write_csv([row, row])
        df, raw = clean_csv(path)
        assert raw == 2
        assert len(df) == 1
        os.unlink(path)


# ---------------------------------------------------------------------------
# txn_id generation for missing values
# ---------------------------------------------------------------------------
class TestGenerateTxnId:
    def test_missing_txn_id_filled(self):
        path = _write_csv([",2024-01-01,Uber,100,INR,SUCCESS,Transport,ACC011,"])
        df, _ = clean_csv(path)
        txn_id = df["txn_id"].iloc[0]
        assert txn_id is not None
        assert len(str(txn_id)) > 0
        os.unlink(path)


# ---------------------------------------------------------------------------
# Raw row count
# ---------------------------------------------------------------------------
class TestRawRowCount:
    def test_returns_raw_count(self):
        path = _write_csv([
            "T020,2024-01-01,Amazon,100,INR,SUCCESS,Shopping,ACC001,",
            "T021,2024-01-02,Flipkart,200,INR,FAILED,Shopping,ACC002,",
            "T020,2024-01-01,Amazon,100,INR,SUCCESS,Shopping,ACC001,",  # duplicate
        ])
        df, raw = clean_csv(path)
        assert raw == 3
        assert len(df) == 2  # one duplicate removed
        os.unlink(path)
