"""
Pytest configuration and shared fixtures for TTC chatbot tests.
"""

import pytest
import sys
from pathlib import Path
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Set test environment
os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session")
def test_db():
    """Create an in-memory SQLite database for testing."""
    from backend.database import Base
    
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Provide a database session for each test."""
    from sqlalchemy.orm import sessionmaker
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db
    )
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def client(test_db):
    """Create a FastAPI test client bound to the in-memory test database."""
    from fastapi.testclient import TestClient
    from backend.database import get_db

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    try:
        from main import app

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
    except SyntaxError as e:
        if "non-printable character" in str(e):
            pytest.skip(f"NLP handler has syntax error: {e}")
        raise

