"""Database engine, session factory, and FastAPI dependency."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.models.base import Base


engine = create_engine(
    settings.database_url,
    # echo SQL in development for easy debugging
    echo=settings.app_debug,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency — yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables from ORM metadata.

    Suitable for a 6-hour assessment where Alembic migrations add
    unnecessary ceremony.  For production, switch to Alembic.
    """
    Base.metadata.create_all(bind=engine)
