from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from redberry_webkit.auth import AuthManager
from redberry_webkit.config import ConfigManager
from redberry_webkit.metrics import MetricsStore

from app.core import web
from app.main import app

# Generic behaviour (login, /ui gate, /ui/config, rate limit, bearer tokens, branding) is tested in
# redberry-webkit (tests/test_bootstrap.py). Here: only that this project wired it up, plus its own routes.


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Context manager so the lifespan (metrics.init_db, background loops) runs.
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests must not touch the project's real data/ or .env.
    env_file = tmp_path / ".env"
    env_file.write_text("RATE_LIMIT=20/minute" + chr(10), encoding="utf-8")
    monkeypatch.setattr(
        web,
        "config",
        ConfigManager(defaults=web.config._defaults, secret_keys=web.config._secret_keys, env_path=env_file),
    )
    monkeypatch.setattr(web, "metrics", MetricsStore(db_path=tmp_path / "metrics.db"))
    monkeypatch.setattr(
        web,
        "auth",
        AuthManager(auth_file=tmp_path / "auth.json", cookie_name=web.auth.cookie_name, token_ttl=web.auth.token_ttl),
    )
    web.limiter.reset()


def _login(client: TestClient) -> None:
    web.auth.set_password("test-password-123")
    client.post("/auth/login", data={"password": "test-password-123"}, follow_redirects=False)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard_requires_login(client: TestClient) -> None:
    response = client.get("/ui/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_and_dashboard(client: TestClient) -> None:
    _login(client)
    page = client.get("/ui/")
    assert page.status_code == 200
    assert "Richieste totali" in page.text
    assert "Aggiornato:" in page.text
    fragment = client.get("/ui/fragment/live")
    assert fragment.status_code == 200
    assert "Richieste ok" in fragment.text


def test_live_fragment_requires_login(client: TestClient) -> None:
    assert client.get("/ui/fragment/live", follow_redirects=False).status_code == 302


def test_shared_assets_and_project_css(client: TestClient) -> None:
    for path in ("/login", "/ui/_assets/app.css", "/ui/_assets/app.js", "/ui/_static/app.css"):
        assert client.get(path).status_code == 200, path


def test_example_endpoint_ok(client: TestClient) -> None:
    response = client.get("/api/v1/example", params={"name": "Danilo"})
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Danilo!"}


def test_example_endpoint_records_metrics_and_shows_on_dashboard(client: TestClient) -> None:
    client.get("/api/v1/example")
    _login(client)
    assert "<td>" in client.get("/ui/fragment/live").text


def test_example_endpoint_rate_limited(client: TestClient) -> None:
    web.config.update_many({"RATE_LIMIT": "2/minute"})
    for _ in range(2):
        assert client.get("/api/v1/example").status_code == 200
    assert client.get("/api/v1/example").status_code == 429


def test_example_endpoint_requires_token_when_configured(client: TestClient) -> None:
    web.config.update_many({"API_TOKENS": "abc123"})
    assert client.get("/api/v1/example").status_code == 401
    assert client.get("/api/v1/example", headers={"Authorization": "Bearer abc123"}).status_code == 200
