"""Integration test for registration against the configured MySQL database."""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.database import DATABASE_URL, SessionLocal
from backend.models import User
from main import app


@pytest.mark.integration
def test_register_creates_user_in_mysql_database():
    """Register a user through the API and verify it is persisted in MySQL."""
    if not DATABASE_URL.startswith("mysql"):
        pytest.skip(f"Expected MySQL DATABASE_URL, got: {DATABASE_URL}")

    suffix = uuid.uuid4().hex[:10]
    payload = {
        "username": f"register_test_{suffix}",
        "email": f"register_test_{suffix}@example.com",
        "password": "StrongPass1!",
        "full_name": "Register Test User",
    }

    db = SessionLocal()
    created_user = None

    try:
        with TestClient(app) as client:
            register_response = client.post("/api/auth/register", json=payload)
            assert register_response.status_code == 201, register_response.text

            login_response = client.post(
                "/api/auth/login",
                json={"username": payload["username"], "password": payload["password"]},
            )
            assert login_response.status_code == 200, login_response.text

        created_user = db.query(User).filter(User.username == payload["username"]).first()
        assert created_user is not None
        assert created_user.email == payload["email"]
        assert created_user.full_name == payload["full_name"]
        assert created_user.role.value == "user"
    finally:
        if created_user is None:
            created_user = db.query(User).filter(User.username == payload["username"]).first()

        if created_user is not None:
            db.delete(created_user)
            db.commit()

        db.close()
