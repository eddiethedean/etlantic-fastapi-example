import os
from pathlib import Path

TEST_DATABASE = Path(__file__).parent / "test.db"
os.environ["ETLANTIC_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["ETLANTIC_JWT_SECRET"] = "tests-only-secret-that-is-long-enough-123456"


def pytest_sessionfinish() -> None:
    TEST_DATABASE.unlink(missing_ok=True)

