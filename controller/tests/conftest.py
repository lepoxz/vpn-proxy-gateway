"""Pytest fixtures for unit and integration testing."""

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Ensure test env defaults
TEST_MASTER_KEY = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="  # 44 chars valid Fernet base64
TEST_ADMIN_USER = "admin"
TEST_ADMIN_PASS = "testpassword123"
TEST_SESSION_SECRET = "test-session-secret-longer-than-32-chars-for-testing"

os.environ["VPG_MASTER_KEY"] = TEST_MASTER_KEY
os.environ["VPG_ADMIN_USERNAME"] = TEST_ADMIN_USER
os.environ["VPG_ADMIN_PASSWORD"] = TEST_ADMIN_PASS
os.environ["VPG_SESSION_SECRET"] = TEST_SESSION_SECRET
os.environ["VPG_SECURE_COOKIES"] = "false"
os.environ["VPG_ENABLE_SCHEDULER"] = "false"
os.environ["VPG_DATABASE_URL"] = "sqlite://"
os.environ["VPG_DATA_DIR"] = tempfile.gettempdir()

from app import db as db_module
from app.config import Settings, get_settings
from app.core.runtime import FakeRuntime
from app.main import create_app
from app.state import build_state

get_settings.cache_clear()


@pytest.fixture(name="settings")
def fixture_settings():
    return Settings(
        master_key=TEST_MASTER_KEY,
        admin_username=TEST_ADMIN_USER,
        admin_password=TEST_ADMIN_PASS,
        session_secret=TEST_SESSION_SECRET,
        secure_cookies=False,
        enable_scheduler=False,
        database_url="sqlite://",
        data_dir=tempfile.mkdtemp(),
        socks_port_range="11000-11009",
        http_port_range="12000-12009",
    )


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    db_module._engine = engine
    return engine


@pytest.fixture(name="session")
def fixture_session(engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture(name="fake_runtime")
def fixture_fake_runtime():
    return FakeRuntime()


@pytest.fixture(name="mock_ip_fetcher")
def fixture_mock_ip_fetcher():
    """Mock public IP fetcher that returns a fake public IP for proxies, and a host IP for direct."""

    def _fetcher(urls, timeout, proxy=None):
        if proxy is None:
            return "1.2.3.4"  # Simulated Host IP
        return "198.51.100.99"  # Simulated VPN Exit IP

    return _fetcher


@pytest.fixture(name="app_state")
def fixture_app_state(settings, engine, fake_runtime, mock_ip_fetcher):
    state = build_state(
        settings,
        fake_runtime,
        ip_fetcher=mock_ip_fetcher,
    )
    return state


@pytest.fixture(name="client")
def fixture_client(app_state):
    app = create_app()
    app.state.vpg = app_state
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(name="auth_client")
def fixture_auth_client(client):
    """Client already logged in with admin credentials."""
    res = client.post(
        "/api/auth/login",
        json={"username": TEST_ADMIN_USER, "password": TEST_ADMIN_PASS},
    )
    assert res.status_code == 200
    return client
