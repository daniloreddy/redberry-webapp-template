"""Verify that the template scaffolds a working app. Exit 1 on any deviation.

    python tools/check_template.py            # scaffold, invariants, the scaffold's own tests
    python tools/check_template.py --fast     # skip the scaffold's own tests (ruff + pytest)

Checks: the scaffold generates; .gitattributes / CRLF .bat / LF .sh / CI / AGENTS.md + one-line CLAUDE.md
pointer / README sections; the pinned redberry-webkit tag is the webkit's current version; every documented
`copier copy|update` carries --trust; the scaffold's ruff and pytest pass.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent
WEBKIT = TEMPLATE.parent / "redberry-webkit"
POINTER = "# CLAUDE.md\n\nSee [AGENTS.md](AGENTS.md) for project guidance.\n"
failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  FAIL {msg}")


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    exe = shutil.which(cmd[0]) or cmd[0]
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # git hooks export GIT_INDEX_FILE etc.
    return subprocess.run([exe, *cmd[1:]], cwd=cwd, env=env, capture_output=True, text=True, timeout=600)


def scaffold(dest: Path) -> bool:
    # Scaffold from a plain copy of the working tree: copier mishandles staged changes on paths with spaces.
    snapshot = dest.parent / "template"
    shutil.copytree(
        TEMPLATE, snapshot, ignore=shutil.ignore_patterns(".git", "venv", ".venv", "__pycache__", "node_modules")
    )
    r = run(["copier", "copy", "--trust", "--defaults", "-d", "app_name=Probe App", str(snapshot), str(dest)])
    if r.returncode != 0:
        fail(f"scaffold failed: {(r.stdout + r.stderr)[-300:]}")
        return False
    ok("scaffold generated")
    return True


def check_invariants(dest: Path) -> None:
    ga = (dest / ".gitattributes").read_text(encoding="utf-8") if (dest / ".gitattributes").exists() else ""
    for rule in ("* text=auto eol=lf", "*.bat text eol=crlf", "*.sh text eol=lf"):
        (ok if rule in ga else fail)(f".gitattributes has '{rule}'")
    for bat in dest.rglob("*.bat"):
        lf_only = re.search(rb"(?<!\r)\n", bat.read_bytes()) is not None
        (fail if lf_only else ok)(f"{bat.relative_to(dest)} CRLF")
    for sh in dest.rglob("*.sh"):
        (fail if b"\r\n" in sh.read_bytes() else ok)(f"{sh.relative_to(dest)} LF")
    workflows = dest / ".github" / "workflows"
    (ok if workflows.is_dir() and list(workflows.glob("*.y*ml")) else fail)("CI workflow present")
    readme = (dest / "README.md").read_text(encoding="utf-8") if (dest / "README.md").exists() else ""
    for heading in ("## Primo avvio (da zero)", "## Produzione"):
        (ok if heading in readme else fail)(f"README has '{heading}'")
    (ok if (dest / "AGENTS.md").exists() else fail)("AGENTS.md")
    claude = dest / "CLAUDE.md"
    pointer_ok = claude.exists() and claude.read_text(encoding="utf-8").replace("\r\n", "\n") == POINTER
    (ok if pointer_ok else fail)("CLAUDE.md pointer")


def check_pin() -> None:
    version = re.search(r'^version\s*=\s*"([^"]+)"', (WEBKIT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    pinned = re.search(r"redberry-webkit(?:\[[a-z]+\])? @ git\+\S+@v([\d.]+)", (TEMPLATE / "requirements.txt").read_text(encoding="utf-8"))
    want = version.group(1) if version else "?"
    got = pinned.group(1) if pinned else None
    (ok if got == want else fail)(f"template pins redberry-webkit {got}, webkit is {want}")


def check_trust() -> None:
    pat = re.compile(r"copier (copy|update)\b(?! --trust)(?!`)")
    bad = 0
    for f in [*TEMPLATE.rglob("*.md"), *TEMPLATE.rglob("*.jinja")]:
        if any(p in f.parts for p in ("venv", ".git", "tools")):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            s = line.strip()
            if s.startswith(("copier ", "`copier ", "$ copier ")) and pat.search(s.lstrip("`$ ")):
                fail(f"{f.relative_to(TEMPLATE)}:{i} copier without --trust")
                bad += 1
    if not bad:
        ok("all copier commands carry --trust")


def scaffold_tests(dest: Path) -> None:
    """Run ruff and pytest of the generated app in a venv cached across runs (keyed by requirements hash)."""
    reqs = (dest / "requirements.txt").read_bytes() + (dest / "requirements.dev.txt").read_bytes()
    stamp = hashlib.sha256(reqs).hexdigest()
    venv = Path(tempfile.gettempdir()) / "redberry-template-venv"
    exe = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    marker = venv / ".reqs-sha256"
    if not (exe.exists() and marker.exists() and marker.read_text() == stamp):
        shutil.rmtree(venv, ignore_errors=True)
        steps = [
            [sys.executable, "-m", "venv", str(venv)],
            [str(exe), "-m", "pip", "install", "-q", "-r", "requirements.txt", "-r", "requirements.dev.txt"],
        ]
        for cmd in steps:
            r = run(cmd, dest)
            if r.returncode != 0:
                fail("could not prepare the cached venv for the scaffold tests")
                print((r.stdout + r.stderr)[-800:])
                return
        marker.write_text(stamp)
    for cmd in ([str(exe), "-m", "ruff", "check", "."], [str(exe), "-m", "pytest", "-q"]):
        r = run(cmd, dest)
        if r.returncode != 0:
            fail(f"scaffold `{' '.join(cmd[1:])}` failed")
            print((r.stdout + r.stderr)[-800:])
            return
    ok("scaffold ruff + pytest pass")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fast", action="store_true", help="skip the scaffold's own ruff + pytest")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="template-") as tmp:
        dest = Path(tmp) / "app"
        if scaffold(dest):
            check_invariants(dest)
            if not args.fast:
                scaffold_tests(dest)
    check_pin()
    check_trust()
    print()
    if failures:
        print(f"{len(failures)} deviation(s)")
        return 1
    print("template: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
