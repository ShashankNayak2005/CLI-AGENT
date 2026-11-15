"""
Database engine, session factory, and initialization management.
Connects to SQLite using SQLAlchemy with thread-safe connection pooling.
"""

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import BASE_DIR, get_settings

logger = logging.getLogger("cli_agent.database")

settings = get_settings()

# Normalize SQLite database URL so it resolves to backend/cli_agent.db
db_url = settings.database_url
if db_url.startswith("sqlite:///./"):
    relative_path = db_url.replace("sqlite:///./", "")
    db_file = BASE_DIR / relative_path
    db_url = f"sqlite:///{db_file.as_posix()}"

# Connect args specific to SQLite to allow multi-threaded FastAPI execution
connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a clean database session per request.
    Ensures safe rollback on exception and automatic session cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        logger.error("Database session error: %s", str(exc))
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initializes database schema tables automatically upon application startup.
    """
    try:
        logger.info("Initializing database tables via SQLAlchemy Base metadata...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", str(exc), exc_info=True)
        raise
