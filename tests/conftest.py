"""
Pytest configuration and shared fixtures.

Provides a TestClient backed by an in-memory SQLite database so tests
run without an external Postgres instance.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite engine for tests
# ---------------------------------------------------------------------------
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Register a SQLite function for gen_random_uuid() used in migrations
@event.listens_for(test_engine, "connect")
def _register_uuid_function(dbapi_conn, connection_record):
    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    """Yield a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the FastAPI dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them afterwards."""
    # Import all models to ensure they are registered with Base.metadata
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client():
    """Return a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """Return a raw SQLAlchemy session for direct DB manipulation in tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
