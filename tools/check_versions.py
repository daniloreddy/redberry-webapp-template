"""Version uniformity across the Python projects: template tag and redberry-webkit pin vs the current ones.

    python tools/check_versions.py [projects_root]

Reads each sibling project's `.copier-answers.yml` (`_commit`) and `requirements.txt` (webkit pin) and compares them with
the latest template tag and the webkit's `pyproject.toml` version. Exit 1 if any project is behind. Read-only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent
PIN = re.compile(r"redberry-webkit(?:\[[a-z,]+\])? @ git\+\S+@v([\d.]+)")
COMMIT = re.compile(r"^_commit:\s*(\S+)", re.M)


def latest_tag() -> str:
    tags = subprocess.run(
        ["git", "tag", "--sort=-v:refname"], cwd=TEMPLATE, capture_output=True, text=True, check=True
    ).stdout.split()
    return tags[0].lstrip("v") if tags else "?"


def webkit_version(root: Path) -> str:
    text = (root / "redberry-webkit" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "?"


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else TEMPLATE.parent
    template, webkit = latest_tag(), webkit_version(root)
    print(f"current: template {template}, webkit {webkit}\n")
    behind = 0
    for answers in sorted(root.glob("*/.copier-answers.yml")):
        project = answers.parent
        requirements = project / "requirements.txt"
        if not requirements.exists():
            continue
        commit = COMMIT.search(answers.read_text(encoding="utf-8"))
        pin = PIN.search(requirements.read_text(encoding="utf-8"))
        tpl = commit.group(1).lstrip("v") if commit else "?"
        wk = pin.group(1) if pin else "-"
        if wk == "-":
            continue  # not a webkit (Python) project: a Go/Java template
        late = tpl != template or wk != webkit
        behind += late
        print(f"{'BEHIND' if late else 'ok    '}  {project.name:24} template {tpl:20} webkit {wk}")
    print(f"\n{behind} project(s) behind" if behind else "\nall aligned")
    return 1 if behind else 0


if __name__ == "__main__":
    sys.exit(main())
