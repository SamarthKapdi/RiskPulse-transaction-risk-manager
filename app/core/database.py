"""
SQLAlchemy database setup (synchronous engine for Celery compatibility).

Provides engine, session factory, declarative base, and a FastAPI
dependency-injection generator.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_sessionmaker = None


def get_engine():
    """Lazily initialize and return the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def SessionLocal() -> Session:
    """Lazily initialize the sessionmaker and return a new Session."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _sessionmaker()


Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
