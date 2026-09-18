"""Shared test fixtures — SQLite in-memory database for fast, isolated tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.base import Base

# Import all models so they register with Base.metadata
import app.models  # noqa: F401


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh SQLite in-memory engine per test function."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Session:
    """Create a fresh DB session per test, rolled back after each test."""
    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSession()
    yield session
    session.rollback()
    session.close()
