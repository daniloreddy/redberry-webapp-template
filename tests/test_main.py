from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from redberry_webkit.auth import AuthManager
from redberry_webkit.metrics import MetricsStore

import app.main as main_module
import app.ui.router as router_module
from app.config import config

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
async def _isolated_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests must not write to the project's real data/metrics.db. Also: TestClient()
    # without a `with` block never runs the app's lifespan, so the table would
    # otherwise not exist yet either way.
    store = MetricsStore(db_path=tmp_path / "metrics.db")
    await store.init_db()
    monkeypatch.setattr(main_module, "metrics", store)


@pytest.fixture
def isolated_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthManager:
    auth = AuthManager(
        auth_file=tmp_path / "auth.json",
        cookie_name=router_module.auth.cookie_name,
        token_ttl=router_module.auth.token_ttl,
    )
    monkeypatch.setattr(main_module, "auth", auth)
    monkeypatch.setattr(router_module, "auth", auth)
    return auth


@pytest.fixture(autouse=True)
def _default_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # tests must not depend on whatever RATE_LIMIT happens to be set in the real .env
    monkeypatch.setitem(config._cache, "RATE_LIMIT", "20/minute")
    # the limiter's in-memory hit counts persist across tests (same "testclient" key) —
    # reset before each test so one test's requests can't push another into a 429
    main_module.limiter.reset()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_ui() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_dashboard_requires_auth_redirects_to_login() -> None:
    response = client.get("/ui/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_docs_disabled_when_not_dev() -> None:
    assert main_module.DEV is False
    response = client.get("/docs")
    assert response.status_code == 404


def test_login_flow(isolated_auth: AuthManager) -> None:
    isolated_auth.set_password("test-password-123")
    response = client.post("/auth/login", data={"password": "test-password-123"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/ui/"
    assert isolated_auth.cookie_name in response.cookies


def test_login_flow_wrong_password(isolated_auth: AuthManager) -> None:
    isolated_auth.set_password("test-password-123")
    response = client.post("/auth/login", data={"password": "wrong"}, follow_redirects=False)
    assert response.status_code == 303
    assert "error=invalid" in response.headers["location"]


def test_example_endpoint_ok() -> None:
    response = client.get("/api/v1/example", params={"name": "Danilo"})
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Danilo!"}


def test_example_endpoint_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(config._cache, "RATE_LIMIT", "2/minute")
    for _ in range(2):
        assert client.get("/api/v1/example").status_code == 200
    response = client.get("/api/v1/example")
    assert response.status_code == 429
