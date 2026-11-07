"""Install the git hooks that enforce the checks in redberry-webapp-template and redberry-webkit.

    python tools/install_hooks.py

Template: pre-commit runs `tools/check_template.py --fast`, pre-push the full check.
Webkit: pre-push runs ruff, mypy and pytest. Hooks live in .git/hooks (not versioned): rerun after a fresh clone.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent
WEBKIT = TEMPLATE.parent / "redberry-webkit"
MARK = "# managed by redberry-webapp-template/tools/install_hooks.py"
OLD_MARK = "# managed by redberry-webkit-ui/scripts/install_hooks.py"


def write(repo: Path, name: str, body: str) -> bool:
    path = repo / ".git" / "hooks" / name
    if not path.parent.is_dir():
        print(f"skip {repo.name}/{name}: no .git/hooks")
        return False
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if MARK not in text and OLD_MARK not in text:
            print(f"skip {repo.name}/{name}: foreign hook present")
            return False
    path.write_bytes(f"#!/bin/sh\n{MARK}\n{body}\n".encode())
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"ok   {repo.name}/{name}")
    return True


def remove_old(repo: Path) -> None:
    for name in ("pre-commit", "pre-push"):
        path = repo / ".git" / "hooks" / name
        if path.exists() and OLD_MARK in path.read_text(encoding="utf-8", errors="ignore"):
            path.unlink()
            print(f"removed old {repo.name}/{name}")


def main() -> int:
    check = (TEMPLATE / "tools" / "check_template.py").as_posix()
    ok = write(TEMPLATE, "pre-commit", f'exec python "{check}" --fast')
    ok &= write(TEMPLATE, "pre-push", f'exec python "{check}"')
    py = "venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python"
    checks = f'{py} -m ruff check . && {py} -m mypy redberry_webkit && {py} -m pytest -q'
    ok &= write(WEBKIT, "pre-push", f'cd "{WEBKIT.as_posix()}" && {checks}')
    for name in ("redberry-webkit-ui", "redberry-webkit", "redberry-webkit-go", "redberry-webkit-j", "redberry-webapp-template-go", "redberry-webapp-template-j"):
        remove_old(TEMPLATE.parent / name)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
