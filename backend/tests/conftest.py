"""Pytest fixtures providing an isolated SQLite test database per test."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure test environment uses deterministic demo mode & mock adapters (never live tokens)
os.environ["APP_MODE"] = "demo"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_database_if_empty  # noqa: E402


@pytest.fixture(autouse=True)
def _force_mock_settings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "")
    get_settings.cache_clear()
    cfg = get_settings()
    cfg.telegram_bot_token = ""
    cfg.whatsapp_access_token = ""
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db_session(tmp_path):
    db_file = tmp_path / "test_kirana.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_database_if_empty(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
