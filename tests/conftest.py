from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Env must be set before the app (and its settings cache) is imported.
TEST_DATABASE = Path(__file__).parent / "test.db"
os.environ["ETLANTIC_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["ETLANTIC_JWT_SECRET"] = "tests-only-secret-that-is-long-enough-123456"
os.environ["ETLANTIC_TOKEN_ENCRYPTION_KEY"] = (
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
)

from etlantic_runner.api import app  # noqa: E402
from etlantic_runner.database import SessionLocal  # noqa: E402
from etlantic_runner.models import User  # noqa: E402
from tests.helpers import auth_headers_for  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient with lifespan (migrations, runner, scheduler)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def unique_email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


@pytest.fixture
def auth_headers(client: TestClient, unique_email: str) -> dict[str, str]:
    return auth_headers_for(client, unique_email)


@pytest.fixture
def other_auth_headers(client: TestClient) -> dict[str, str]:
    return auth_headers_for(client, f"other-{uuid.uuid4().hex}@example.com")


@pytest.fixture
def admin_auth_headers(client: TestClient) -> dict[str, str]:
    email = f"admin-{uuid.uuid4().hex}@example.com"
    headers = auth_headers_for(client, email, display_name="Admin")
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email.lower()))
        assert user is not None
        user.is_admin = True
        session.commit()
    return headers


def pytest_sessionfinish() -> None:
    TEST_DATABASE.unlink(missing_ok=True)
