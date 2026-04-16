"""
Database configuration and session management.
Supports SQLite (development) and PostgreSQL (production).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Database URL configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./ttc_chatbot.db"  # Default to SQLite in current directory
)

# SQLAlchemy engine configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific configuration for development
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Required for SQLite with threading
    )
else:
    # PostgreSQL or other database configuration for production
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Test connection before using
        pool_recycle=3600,   # Recycle connections after 1 hour
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI to inject database session.
    Usage in route: async def route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database.
    Create all tables if they don't exist.
    Call this at application startup.
    """
    Base.metadata.create_all(bind=engine)


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all tables (for testing/reset only)."""
    Base.metadata.drop_all(bind=engine)
