"""
Celery application and task definitions.

Uses Redis as both broker and result backend.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pipeline",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="process_job", bind=True, max_retries=0)
def process_job_task(self, job_id: str) -> None:  # noqa: ANN001
    """
    Celery task wrapper that delegates to the processing service.

    Using a deferred import so the heavy service module is only loaded
    inside the worker process.
    """
    from app.services.processing_service import process_job

    process_job(job_id)
