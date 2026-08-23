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
from app.api.risk import router as risk_router
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
    title="RiskPulse — Explainable AI Transaction Risk Manager",
    description=(
        "Defense-only AI risk detection system for payment transactions. "
        "Detects suspicious behavior, produces calibrated risk scores, "
        "gathers evidence, explains decisions, and routes through bounded policy. "
        "Built for Razorpay AI Buildathon 2026 — Track 02: AI Risk Manager."
    ),
    version="2.0.0",
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
app.include_router(risk_router)


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
