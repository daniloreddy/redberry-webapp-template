from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from redberry_webkit.auth import AuthManager
from redberry_webkit.config import ConfigManager
from redberry_webkit.metrics import MetricsStore

import app.main as main_module
import app.ui.pages as pages_module
import app.ui.router as router_module
from app.config import _DEFAULTS, _SECRET_KEYS


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Must enter as a context manager, otherwise FastAPI's lifespan (metrics.init_db(),
    # background tasks) never runs.
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture(autouse=True)
async def _isolated_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests must not write to the project's real data/metrics.db. app/main.py and
    # app/ui/pages.py each do `from app.metrics import metrics` — two independent name
    # bindings captured at import time. Patching main_module alone leaves pages_module's
    # binding pointed at the original (uninitialized-in-tests) singleton, so any test that
    # renders a NiceGUI page hits the real metrics.db, or a fresh scaffold's db that has
    # no `requests` table yet.
    store = MetricsStore(db_path=tmp_path / "metrics.db")
    await store.init_db()
    monkeypatch.setattr(main_module, "metrics", store)
    monkeypatch.setattr(pages_module, "metrics", store)


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


@pytest.fixture
def set_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    # Builds a real ConfigManager pointed at a throwaway .env instead of poking the
    # private `config._cache` dict — stays on ConfigManager's public constructor/API.
    def _set(value: str) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(f"RATE_LIMIT={value}\n")
        test_config = ConfigManager(defaults=_DEFAULTS, secret_keys=_SECRET_KEYS, env_path=env_file)
        monkeypatch.setattr(main_module, "config", test_config)

    return _set


@pytest.fixture(autouse=True)
def _default_rate_limit(set_rate_limit: Callable[[str], None]) -> None:
    # tests must not depend on whatever RATE_LIMIT happens to be set in the real .env
    set_rate_limit("20/minute")
    # the limiter's in-memory hit counts persist across tests (same "testclient" key) —
    # reset before each test so one test's requests can't push another into a 429
    main_module.limiter.reset()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_ui(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_dashboard_requires_auth_redirects_to_login(client: TestClient) -> None:
    response = client.get("/ui/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_docs_disabled_when_not_dev(client: TestClient) -> None:
    assert main_module.DEV is False
    response = client.get("/docs")
    assert response.status_code == 404


def test_login_flow(client: TestClient, isolated_auth: AuthManager) -> None:
    isolated_auth.set_password("test-password-123")
    response = client.post("/auth/login", data={"password": "test-password-123"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/ui/"
    assert isolated_auth.cookie_name in response.cookies


def test_login_flow_wrong_password(client: TestClient, isolated_auth: AuthManager) -> None:
    isolated_auth.set_password("test-password-123")
    response = client.post("/auth/login", data={"password": "wrong"}, follow_redirects=False)
    assert response.status_code == 303
    assert "error=invalid" in response.headers["location"]


def test_example_endpoint_ok(client: TestClient) -> None:
    response = client.get("/api/v1/example", params={"name": "Danilo"})
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Danilo!"}


def test_example_endpoint_rate_limited(client: TestClient, set_rate_limit: Callable[[str], None]) -> None:
    set_rate_limit("2/minute")
    for _ in range(2):
        assert client.get("/api/v1/example").status_code == 200
    response = client.get("/api/v1/example")
    assert response.status_code == 429


def test_example_endpoint_rejects_non_ascii_bearer_token_with_401(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # secrets.compare_digest raises TypeError on non-ASCII str operands — verify_api_token
    # must turn that into a 401, not let it surface as an unhandled 500. A plain str header
    # value can't even reach the wire (httpx enforces ASCII client-side); raw bytes bypass
    # that check the way a real non-conforming client would, and ASGI decodes header bytes
    # as latin-1 server-side, so this reproduces the exact non-ASCII str verify_api_token sees.
    env_file = tmp_path / ".env"
    env_file.write_text("API_TOKENS=abc123\nRATE_LIMIT=20/minute\n")
    test_config = ConfigManager(defaults=_DEFAULTS, secret_keys=_SECRET_KEYS, env_path=env_file)
    monkeypatch.setattr(main_module, "config", test_config)

    headers = httpx.Headers([("Authorization", "Bearer café".encode())])
    response = client.get("/api/v1/example", headers=headers)
    assert response.status_code == 401


def test_login_semaphore_caps_concurrent_verify(client: TestClient, isolated_auth: AuthManager) -> None:
    # A burst of concurrent /auth/login requests must never run more than
    # _LOGIN_MAX_CONCURRENT scrypt verifications in parallel — that cap is what bounds
    # worst-case memory (N=131072 -> ~128MB/verify) under an unauthenticated flood.
    isolated_auth.set_password("test-password-123")
    lock = threading.Lock()
    concurrent = 0
    max_concurrent = 0

    def _slow_verify(password: str) -> bool:
        nonlocal concurrent, max_concurrent
        with lock:
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
        time.sleep(0.3)
        with lock:
            concurrent -= 1
        return True

    isolated_auth.verify_password = _slow_verify  # type: ignore[method-assign]

    workers = router_module._LOGIN_MAX_CONCURRENT + 4
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(client.post, "/auth/login", data={"password": "x"}, follow_redirects=False)
            for _ in range(workers)
        ]
        for future in futures:
            assert future.result().status_code == 303

    assert max_concurrent <= router_module._LOGIN_MAX_CONCURRENT


def test_login_verify_timeout_returns_503(
    client: TestClient, isolated_auth: AuthManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_auth.set_password("test-password-123")
    monkeypatch.setattr(router_module, "_LOGIN_VERIFY_TIMEOUT_S", 0.05)
    isolated_auth.verify_password = lambda password: time.sleep(0.3) or True  # type: ignore[method-assign]

    response = client.post("/auth/login", data={"password": "test-password-123"})
    assert response.status_code == 503
