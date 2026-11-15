from __future__ import annotations

from redberry_webkit.bootstrap import run

from app.core import web

# Launcher kept apart from app/main.py: uvicorn imports "app.main" by name, so a `python -m app.main` launcher
# would execute main.py twice (as __main__, then as app.main), registering routers and background tasks twice.
if __name__ == "__main__":
    run("app.main:app", web)
