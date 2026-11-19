from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        admin_password_hash=hash_password("correct-password", salt="test-salt"),
        session_secret="test-session-secret-with-enough-length",
        database_path=tmp_path / "pingcheck-test.db",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
