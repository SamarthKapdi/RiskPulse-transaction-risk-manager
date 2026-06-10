"""
FastAPI application entry point.

Configures CORS, includes routers, and exposes a health-check endpoint.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jobs import router as jobs_router
from app.core.config import get_settings
from app.schemas.job import HealthResponse

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Upload directory ensured: %s", settings.UPLOAD_DIR)
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="AI-Powered Transaction Processing Pipeline",
    description=(
        "Upload CSV transaction files, clean them, detect anomalies, "
        "classify with Gemini LLM, and retrieve aggregated summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS middleware (permissive for development) ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(jobs_router)


# ── Health check ─────────────────────────────────────────────────────────────


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """Simple liveness probe."""
    return HealthResponse(status="healthy")
