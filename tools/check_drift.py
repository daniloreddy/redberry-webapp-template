"""Detect drift between scaffolded projects and this template.

`copier update` only reports the pinned `_commit` as stale/current — it does not
verify that files meant to be copied verbatim (see fastapi-auth.md, uvicorn.md)
still match the template's actual rendered content. A project can hand-rewrite
one of those files entirely and `copier update` will happily 3-way-merge around
it without ever flagging the divergence. This script renders the template fresh
with each project's own answers and diffs the result against the real files.

Usage (from anywhere, template's own venv must have pyyaml — copier depends on it):
    python tools/check_drift.py [projects_root] [relative/path ...]

projects_root defaults to this template's parent directory (siblings under
C:/redberry/src/python). Extra positional args override the default verbatim
path list below.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PROJECTS_ROOT = _TEMPLATE_ROOT.parent

_VERBATIM_PATHS = [
    "static/login.html",
]


def _find_projects(root: Path) -> list[Path]:
    return sorted(
        p.parent
        for p in root.glob("*/.copier-answers.yml")
        if p.parent.resolve() != _TEMPLATE_ROOT.resolve()
    )


def _load_answers(project: Path) -> dict[str, str]:
    raw = yaml.safe_load((project / ".copier-answers.yml").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}


def _render(answers: dict[str, str], out_dir: Path) -> None:
    args = ["copier", "copy", "--trust", "--defaults", "--vcs-ref=HEAD"]
    for key, value in answers.items():
        args += ["--data", f"{key}={value}"]
    args += [str(_TEMPLATE_ROOT), str(out_dir)]
    subprocess.run(args, check=True, capture_output=True, text=True)


def check_project(project: Path, paths: list[str]) -> list[str]:
    answers = _load_answers(project)
    diffs = []
    with tempfile.TemporaryDirectory() as tmp:
        rendered = Path(tmp) / "rendered"
        _render(answers, rendered)
        for rel in paths:
            real, tpl = project / rel, rendered / rel
            if not real.exists() or not tpl.exists():
                diffs.append(f"{rel}: missing ({'project' if not real.exists() else 'template'})")
            elif real.read_text(encoding="utf-8") != tpl.read_text(encoding="utf-8"):
                diffs.append(rel)
    return diffs


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_PROJECTS_ROOT
    paths = sys.argv[2:] if len(sys.argv) > 2 else _VERBATIM_PATHS

    projects = _find_projects(root)
    if not projects:
        print(f"No scaffolded projects found under {root}")
        return

    any_drift = False
    for project in projects:
        try:
            diffs = check_project(project, paths)
        except subprocess.CalledProcessError as exc:
            print(f"{project.name}: RENDER FAILED - {exc.stderr.strip()[:200]}")
            any_drift = True
            continue
        if diffs:
            any_drift = True
            print(f"{project.name}: DRIFT - {', '.join(diffs)}")
        else:
            print(f"{project.name}: ok")

    sys.exit(1 if any_drift else 0)


if __name__ == "__main__":
    main()
