"""
Tests for FastAPI REST endpoints.

Validates the health endpoint, CSV upload, invalid file rejection,
job listing, and individual job status retrieval.
"""

import io
import uuid
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# Upload CSV
# ---------------------------------------------------------------------------
class TestUploadCsv:
    @patch("app.workers.tasks.process_job_task.delay")
    def test_upload_valid_csv(self, mock_delay, client):
        """Uploading a well-formed CSV should return 201 with a job_id."""
        mock_delay.return_value = MagicMock(id="mock-task-id")

        csv_content = (
            "txn_id,date,merchant,amount,currency,status,category,account_id,notes\n"
            "T001,2024-01-15,Amazon,1500.00,INR,SUCCESS,Shopping,ACC001,test note\n"
        )
        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post("/jobs/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_upload_invalid_file_type(self, client):
        """Uploading a non-CSV file should be rejected."""
        content = b"this is not a csv"
        files = {"file": ("data.txt", io.BytesIO(content), "text/plain")}
        response = client.post("/jobs/upload", files=files)

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------
class TestListJobs:
    def test_list_jobs_empty(self, client):
        """When no jobs exist, the endpoint should return an empty list."""
        response = client.get("/jobs/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @patch("app.workers.tasks.process_job_task.delay")
    def test_list_jobs_after_upload(self, mock_delay, client):
        """After uploading a CSV, the jobs list should contain one entry."""
        mock_delay.return_value = MagicMock(id="mock-task-id")

        csv_content = (
            "txn_id,date,merchant,amount,currency,status,category,account_id,notes\n"
            "T001,2024-01-15,Amazon,1500.00,INR,SUCCESS,Shopping,ACC001,\n"
        )
        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        client.post("/jobs/upload", files=files)

        response = client.get("/jobs/")
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) >= 1


# ---------------------------------------------------------------------------
# Get job status
# ---------------------------------------------------------------------------
class TestGetJobStatus:
    @patch("app.workers.tasks.process_job_task.delay")
    def test_get_existing_job_status(self, mock_delay, client):
        """Retrieve the status of a previously created job."""
        mock_delay.return_value = MagicMock(id="mock-task-id")

        csv_content = (
            "txn_id,date,merchant,amount,currency,status,category,account_id,notes\n"
            "T001,2024-01-15,Amazon,1500.00,INR,SUCCESS,Shopping,ACC001,\n"
        )
        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        upload_response = client.post("/jobs/upload", files=files)
        job_id = upload_response.json()["job_id"]

        response = client.get(f"/jobs/{job_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_get_nonexistent_job_status(self, client):
        """Requesting status for a non-existent job should return 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/jobs/{fake_id}/status")
        assert response.status_code == 404
