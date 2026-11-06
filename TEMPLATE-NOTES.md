# Redberry Webapp Template

Reusable scaffold, not a product. Starting point for new FastAPI + Jinja2/HTMX
projects.

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
   copier copy --trust https://github.com/daniloreddy/redberry-webapp-template.git path/to/new-project
   # or, from a local checkout of the scaffold:
   copier copy --trust C:/redberry/src/redberry-webapp-template path/to/new-project
   ```
   Copier asks for `app_name` (e.g. "Mail Manager"), `app_slug` (default
   auto-derived, used for cookies/Docker) and `github_owner`. The values
   replace every hardcoded reference (`APP_NAME`, `cookie_name`, Docker
   service/image name, `FastAPI(title=...)`, login page via `WebLayout.render_login`) — no
   manual renaming needed.
3. `cd path/to/new-project && git init` (the template doesn't include `.git`).
4. Delete `app/libs/example.py` (and its test) and add the project's real
   logic there — pure modules, no FastAPI/Jinja2 import, testable without
   `TestClient`.
5. Extend `app/config.py`: add the project's runtime-editable keys to
   `_DEFAULTS`/`_SECRET_KEYS` (no subclassing needed — see the comment in
   the file). Add the corresponding fields to the Config page
   (`CONFIG_FIELDS` in `app/ui/layout.py`), following the same existing
   pattern.
6. Replace `GET /api/v1/example` in `app/main.py` with the real endpoints,
   keeping the `@limiter.limit(...)` + `metrics.record(...)` pattern.
7. Update `requirements.txt` with the project's specific dependencies.
8. Copy `.env.example` to `.env`, set the password: `python scripts/set_password.py`.

### Updating a derived project when the scaffold changes

From the derived project's directory (requires a committed
`.copier-answers.yml`, generated automatically at step 2):

```bash
copier update --trust
```

Copier computes the diff between the scaffold version used at creation and
the current one, and reapplies it to the project — like a git merge.
Conflicts on customized files (e.g. `app/main.py` if you added endpoints)
need manual resolution, marked with `.rej`/conflict markers in the file,
same flow as a merge.

## Copier template — this repo isn't directly runnable

Since it was converted into a [Copier](https://copier.readthedocs.io/)
template, files that contain placeholders (`app/main.py.jinja`,
`app/ui/router.py.jinja`, `app/ui/pages.py.jinja`, `app/ui/layout.py.jinja`,
`docker-compose*.yml.jinja`) exist only with a `.jinja` suffix in the source
— Copier strips it at generation time. This means **`python -m app.main`,
`pytest`, `mypy app` do NOT work when run directly in this repo** (the real
`.py` files don't exist until you generate an instance).

**To modify/validate the scaffold**: generate a test instance with Copier
and work/test there, then port the verified changes back into the source
`.jinja` files:

```bash
copier copy --trust . /tmp/skeleton-smoke-test --data app_name="Smoke Test" --defaults
cd /tmp/skeleton-smoke-test && scripts/checks.bat   # or checks.sh
```

**Warning — uncommitted changes**: `copier copy --trust .` with a git repo as the
source path generates from the last commit (`HEAD`), **not** from the
working tree — uncommitted changes to `.jinja` files don't show up in the
generated instance, with no warning. To validate uncommitted changes, first
copy the tracked files into a temp directory with no `.git`, and point
Copier there:

```bash
mkdir -p /tmp/webapp-template-src && cp -r --parents $(git ls-files) /tmp/webapp-template-src
# then overwrite the uncommitted .jinja changes, e.g.:
cp app/main.py.jinja /tmp/webapp-template-src/app/main.py.jinja
copier copy --trust /tmp/webapp-template-src /tmp/skeleton-smoke-test --data app_name="Smoke Test" --defaults
```

`.github/workflows/docker-publish.yml` is the only file copied 1:1 without
rendering (it uses `${{ }}` for GitHub Actions expressions, which collides
with Jinja's default syntax — this is why the rendering mechanism is opt-in
per-file via the `.jinja` suffix, not global).

## Shared dependencies

`env_resolver`, `auth`, `config`, `logging_utils`, `timezone_utils`,
`metrics`, `request_view` (request-table view-model: `RequestRow`,
`request_rows_from_metrics()`, `REQUEST_TABLE_BASE_COLUMNS`,
`request_meta()`) and `web` (Jinja2 page chrome: `WebLayout`, `NavItem`,
`icon()`, `status_badge()`, `parse_config_form()`, favicon/logo via `WebLayout(favicon=, logo=)`, `STATIC_DIR`) all live in
[`redberry-webkit`](https://github.com/daniloreddy/redberry-webkit), a
shared pip package. Pin in `requirements.txt`:
`redberry-webkit @ git+https://github.com/daniloreddy/redberry-webkit.git@vX.Y.Z`.
`app/ui/pages.py.jinja` imports both — see it for the reference wiring.

Bugfix/feature in the package → new semver tag in the `redberry-webkit`
repo → manual pin bump here.

**The pin is on a Git tag (`@vX.Y.Z`), not a SHA — an accepted risk, not an
oversight.** A tag is mutable: anyone with push access to `redberry-webkit`
can make it point elsewhere without this pin changing. With `redberry-webkit`
public and under the sole owner's control, the only scenario where this
matters is a compromised GitHub account — at that point the problem is
already bigger than the pin. Switching to a commit SHA would eliminate the
risk but make every manual bump less readable (a SHA doesn't communicate the
version) for a marginal gain in this single-owner context — decided
2026-09-21, not to be revisited without an actual change in the threat model
(e.g. shared push access with third parties).

Before reimplementing one of these modules from scratch, check whether
`redberry-webkit` already covers it.

`AuthManager.verify_password()` (redberry-webkit ≥v0.2.0, scrypt N=131072)
is synchronous and costs ~150-250ms/~128MB per call — in
`app/ui/router.py.jinja` it must always be invoked via
`asyncio.to_thread(...)`, never inline in the async `/auth/login` handler
(would block the event loop). The call is also wrapped in
`_login_semaphore` (`_LOGIN_MAX_CONCURRENT = 4`) +
`asyncio.wait_for(..., timeout=_LOGIN_VERIFY_TIMEOUT_S)` → 503 on timeout:
without the cap, a burst of unauthenticated requests to `/auth/login` could
push N × ~128MB of RAM in parallel (no slowapi rate limit on this route, by
design — see `is_global_limited()`/SEC-02 above). Pattern already wired
into the template — keep it in every customization of the login flow.

## What goes in redberry-webkit vs what stays here

- **redberry-webkit**: identical regardless of the project — auth, config,
  metrics, credential redaction, tz (framework-free), plus the request-table
  view-model (`request_view`) and the Jinja2 page chrome (`web`, framework-free;
  the legacy NiceGUI `ui` module stays in the package until every consumer migrates).
- **This scaffold**: application wiring — routing, pages, `main.py` wiring,
  Docker, scripts. Every derived project customizes it. `app/ui/pages.py`
  keeps only the page *content* (dashboard cards/table, Config form fields);
  the chrome around it (`WebLayout`, `status_badge()`, `NavItem`, the shared
  `app.css`) is imported, not hand-written — a scaffolded project extends
  `NAV_ITEMS` and adds pages, it doesn't redefine header/footer.

## Extending `app/config.py`

`ConfigManager` (redberry-webkit) accepts `defaults`/`secret_keys` as
constructor dicts — no subclassing needed. A derived project extends both
dicts in `app/config.py` before constructing `config`, then adds the
corresponding fields to the Config page (`CONFIG_FIELDS` in `app/ui/layout.py`).

## Execution constraints

- **`workers=1` mandatory**: `ConfigManager`, `AuthManager` (in-process
  rate-limit dict), `MetricsStore`/SQLite are unshared state across
  workers.
- **`HOST` defaults to `127.0.0.1`**: don't expose beyond localhost without
  having evaluated `API_TOKENS`/rate limiting for the real project's API
  endpoints.

## Tests

`tests/test_main.py` covers health, the auth gate, the login flow, docs
disabled outside `DEV`, rate limiting, the login concurrency cap
(`test_login_semaphore_caps_concurrent_verify`, verifies that
`_login_semaphore` actually limits in-flight scrypt verifications) and
rejection of a non-ASCII Bearer token on the example API endpoint
(`test_example_endpoint_rejects_non_ascii_bearer_token_with_401`, covers the
`TypeError` from `hmac.compare_digest` on non-ASCII input, handled by
`redberry_webkit.auth.verify_api_token`). `tests/test_libs_example.py` is a
placeholder to replace along with `app/libs/example.py`.

## Scaffold maintenance tools (not for derived projects)

Two scripts live only in this template repo, never copied into a derived
project (`align_to_template.py` is in `EXCLUDE_DIRS`/its own logic, not a
Copier-"owned" file):

- **`tools/check_drift.py`** — `copier update` only reports the drift of
  the pinned commit in `.copier-answers.yml`; it doesn't verify that files
  meant to stay "copied verbatim" (`static/htmx.min.js`, and in general
  anything documented as a reference implementation in fastapi-auth.md/
  uvicorn.md) are still identical to the template's current render. A
  derived scaffold can rewrite one of these files by hand and `copier
  update` will happily 3-way-merge around the change without ever flagging
  the divergence. The script re-renders the template with each sibling
  project's `.copier-answers.yml` (under the same `projects_root`, default
  the template's parent directory) and diffs byte for byte. Usage:
  `python tools/check_drift.py [projects_root] [path...]`.
- **`scripts/align_to_template.py`** — generates a fresh skeleton from
  Copier and recursively compares every file against an existing target
  project, producing a 5-section report (owned files that diverge and must
  be fully replaced, common non-owned files with expected divergence, files
  only in the project, files only in the skeleton, identical-file count).
  `TEMPLATE_OWNED_FILES` in the script is the list of files that must stay
  byte-identical after an alignment — any divergence there is a bug in the
  alignment, not a legitimate customization. Usage:
  `python scripts/align_to_template.py <project-path> --app-name "Project
  name" [--report out.md]`.
