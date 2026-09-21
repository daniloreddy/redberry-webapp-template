# Redberry Webapp Template

Reusable base for Python web applications: FastAPI/uvicorn + NiceGUI
dashboard, cookie/JWT auth, hot-reloadable runtime config, rate limiting,
metrics persisted to SQLite. Not a product — it's the starting point for a
new project.

Shared functionality (auth, config, env resolution, log redaction,
timezone, metrics) comes from
[`redberry-webkit`](https://github.com/daniloreddy/redberry-webkit), a pip
package. This repo only adds the **application wiring** around that
package: `main.py`, routing, NiceGUI pages, Docker, scripts.

## Included features

- **Dashboard auth** (`/ui/*`) — cookie/JWT, login/logout, anti-bruteforce rate limiting.
- **Runtime config** (`/ui/config`) — switches/fields tied to `.env`, hot-reload without a restart.
- **Rate limiting** (`slowapi`) on API endpoints, runtime-configurable limit.
- **Metrics** — request history persisted to SQLite (`app/metrics.py`), shown in the dashboard.
- **Docker** — two compose files (prod/dev), bind-mounted data, ready-made GHCR workflow.

## Starting a new project from this scaffold

This repo is a [Copier](https://copier.readthedocs.io/) template — it isn't
copied by hand. Copier keeps track (in `.copier-answers.yml`, generated in
the derived project) of which version of the scaffold was used, so a later
fix here can be reapplied to already-created projects (`copier update`),
instead of staying stuck at the initial copy.

1. Install Copier once (a CLI tool, not a project dependency):
   ```bash
   pipx install copier   # or: pip install --user copier
   ```
2. Generate the new project:
   ```bash
   copier copy https://github.com/daniloreddy/redberry-webapp-template.git path/to/new-project
   # or, from a local checkout of the scaffold:
   copier copy C:/redberry/src/python/redberry-webapp-template path/to/new-project
   ```
   Copier asks for `app_name` (e.g. "Mail Manager"), `app_slug` (default
   auto-derived, used for cookies/Docker) and `github_owner`. The values
   replace every hardcoded reference (`APP_NAME`, `cookie_name`, Docker
   service/image name, `FastAPI(title=...)`, `static/login.html`) — no
   manual renaming needed.
3. `cd path/to/new-project && git init` (the template doesn't include `.git`).
4. Delete `app/libs/example.py` (and its test) and add the project's real
   logic there — pure modules, no FastAPI/NiceGUI import, testable without
   `TestClient`.
5. Extend `app/config.py`: add the project's runtime-editable keys to
   `_DEFAULTS`/`_SECRET_KEYS` (no subclassing needed — see the comment in
   the file). Add the corresponding fields to the Config page
   (`app/ui/pages.py`, `config_page()`), following the same existing
   pattern.
6. Replace `GET /api/v1/example` in `app/main.py` with the real endpoints,
   keeping the `@limiter.limit(...)` + `metrics.record(...)` pattern.
7. Update `requirements.txt` with the project's specific dependencies.
8. Copy `.env.example` to `.env`, set the password: `python scripts/set_password.py`.

### Updating a derived project when the scaffold changes

From the derived project's directory (requires a committed
`.copier-answers.yml`, generated automatically at step 2):

```bash
copier update
```

Copier computes the diff between the scaffold version used at creation and
the current one, and reapplies it to the project — like a git merge.
Conflicts on customized files (e.g. `app/main.py` if you added endpoints)
need manual resolution, marked with `.rej`/conflict markers in the file,
same flow as a merge.

## Quick start (local)

```bash
# Windows
scripts\run.bat --dev

# Linux / Mac
scripts/run.sh --dev
```

The first run creates the virtual environment and installs dependencies.
Copy `.env.example` to `.env` before the first run and set the password:

```bash
python scripts/set_password.py
```

Server at `http://127.0.0.1:8000`. Dashboard at `http://127.0.0.1:8000/ui` (requires login).

## Configuration (`.env`)

See `.env.example` for the full list. Main variables:

| Variable | Default | Notes |
|---|---|---|
| `HOST` | `127.0.0.1` | Local bind. |
| `PORT` | `8000` | |
| `DEV` | `false` | `true` enables uvicorn `--reload` and re-enables `/docs`/`/redoc`. |
| `TZ` | `UTC` | IANA timezone for timestamps shown in the dashboard. |
| `TRUSTED_PROXIES` | `127.0.0.1` | IPs of trusted reverse proxies, used to resolve the real client IP. |
| `AUTH_SECURE_COOKIE` | `0` | `1` forces the `Secure` flag on the cookie even without `X-Forwarded-Proto: https`. |
| `API_TOKENS` | *(empty)* | Comma-separated Bearer tokens for any API endpoints outside `/ui`. |
| `RATE_LIMIT` | `20/minute` | Limit (slowapi syntax) on API endpoints — hot-reload, editable from `/ui/config`. |
| `REFRESH_ENABLED` / `REFRESH_INTERVAL` | `true` / `5` | Dashboard auto-refresh — hot-reload, editable from `/ui/config`. |
| `NICEGUI_STORAGE_PATH` | *(empty)* | Docker only: `/app/data/.nicegui` to persist the dark/light theme across restarts. |

## Docker

```bash
# development (local build)
docker compose -f docker-compose-dev.yml up --build

# production (image from GHCR)
docker compose up -d
```

By default `docker-compose.yml` publishes only on `127.0.0.1`; set
`HOST=0.0.0.0` in `.env` to expose it on a LAN/behind a reverse proxy.

## Development

```bash
# Windows
scripts\checks.bat

# Linux / Mac
scripts/checks.sh
```

Runs `ruff check`, `mypy app` (strict) and `pytest` in sequence.

For whoever maintains the scaffold (not needed in derived projects):

```bash
python tools/check_drift.py                                   # check drift across derived projects
python scripts/align_to_template.py <project-path> --app-name "Project name"  # alignment report
```

## Project structure

```
app/
├── main.py         # FastAPI + lifespan (config reload, auth purge, metrics init) + auth gate +
│                   # rate limiting + /health + NiceGUI mount + example endpoint
├── config.py       # ConfigManager (redberry_webkit) with the scaffold's runtime-editable defaults
├── metrics.py      # MetricsStore (redberry_webkit) bound to data/metrics.db
├── libs/           # project-specific pure logic — example.py is a placeholder to replace
└── ui/
    ├── router.py   # /login /auth/login /auth/logout (AuthManager)
    └── pages.py    # dashboard (metrics + history) + Config page
static/login.html   # self-contained login page
scripts/            # run/checks (bat+sh), set_password.py
data/               # auth.json, metrics.db, logs/ — gitignored
```

## License

MIT — see [LICENSE](LICENSE).
