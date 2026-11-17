"""Verify that the template scaffolds a working app. Exit 1 on any deviation.

    python tools/check_template.py            # scaffold, invariants, the scaffold's own tests
    python tools/check_template.py --fast     # skip the scaffold's own tests (ruff + pytest)

Checks: the scaffold generates; .gitattributes / CRLF .bat / LF .sh / CI / AGENTS.md + one-line CLAUDE.md
pointer / README sections; every documented
`copier copy|update` carries --trust; the scaffold's ruff and pytest pass; full mode (pre-push) also fails when a
file that reaches generated projects changed since the latest vX.Y.Z tag and HEAD is not tagged (copier generates
from the latest tag, so an untagged change would silently never reach new projects or `copier update`). A template pin older than the local
webkit version is only a warning: the webkit is released on its own, the template catches up when it wants.
"""

from __future__ import annotations

import argparse
import fnmatch
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


def _which(name: str) -> str:
    # Git hooks run from GUIs (VS Code) with a PATH that lacks copier: fall back to this repo's own venv.
    venv_bin = TEMPLATE / "venv" / ("Scripts" if os.name == "nt" else "bin")
    return shutil.which(name) or shutil.which(name, path=str(venv_bin)) or name


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    exe = _which(cmd[0])
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # git hooks export GIT_INDEX_FILE etc.
    return subprocess.run([exe, *cmd[1:]], cwd=cwd, env=env, capture_output=True, text=True, timeout=600)


def scaffold(dest: Path, *answers: str) -> bool:
    # Scaffold from a plain copy of the working tree: copier mishandles staged changes on paths with spaces.
    snapshot = dest.parent / "template"
    if not snapshot.exists():
        shutil.copytree(
            TEMPLATE, snapshot, ignore=shutil.ignore_patterns(".git", "venv", ".venv", "__pycache__", "node_modules")
        )
    data = [arg for answer in ("app_name=Probe App", *answers) for arg in ("-d", answer)]
    r = run(["copier", "copy", "--trust", "--defaults", *data, str(snapshot), str(dest)])
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


def check_no_api(dest: Path) -> None:
    """has_api=false: no token script, no API_TOKENS in .env.example, no mention in the docs."""
    leftovers = [p.name for p in (dest / "scripts").glob("generate_token.*")]
    (fail if leftovers else ok)(f"has_api=false: no generate_token script {leftovers or ''}".rstrip())
    for name in (".env.example", "README.md", "AGENTS.md"):
        text = (dest / name).read_text(encoding="utf-8")
        hit = "API_TOKENS=" in text or "generate_token" in text
        (fail if hit else ok)(f"has_api=false: {name} has no API_TOKENS/generate_token")


def check_pin() -> None:
    version = re.search(r'^version\s*=\s*"([^"]+)"', (WEBKIT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    pinned = re.search(
        r"redberry-webkit(?:\[[a-z]+\])? @ git\+\S+@v([\d.]+)",
        (TEMPLATE / "requirements.txt").read_text(encoding="utf-8"),
    )
    want = version.group(1) if version else "?"
    got = pinned.group(1) if pinned else None
    if got is None:
        fail("template requirements.txt has no redberry-webkit @ git+...@vX pin")
    elif got == want:
        ok(f"template pins redberry-webkit {got}")
    else:
        print(f"  WARN template pins redberry-webkit {got}, local webkit is {want} (bump when ready)")


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


def _git(*args: str) -> str:
    return run(["git", *args], TEMPLATE).stdout.strip()


def _copier_excludes() -> list[str]:
    """`_exclude` patterns of copier.yml: matching files never reach a generated project."""
    text = (TEMPLATE / "copier.yml").read_text(encoding="utf-8")
    block = re.search(r"^_exclude:[ \t]*\n((?:[ \t]+-.*\n?)+)", text, re.M)
    return re.findall(r"-\s*[\"']?([^\"'\n]+?)[\"']?\s*$", block.group(1), re.M) if block else []


def _reaches_projects(path: str, excludes: list[str]) -> bool:
    if path == "copier.yml":
        return True  # questions/defaults change what gets generated
    parts = path.split("/")
    prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    return not any(fnmatch.fnmatch(p, pat) for p in [*prefixes, *parts] for pat in excludes)


def check_release_tag() -> None:
    """Copier generates from the LATEST TAG, not HEAD: a pushed change that reaches projects must be tagged."""
    last = _git("describe", "--tags", "--abbrev=0", "--match", "v*")
    if not last:
        fail("no vX.Y.Z tag found: copier would generate from HEAD")
        return
    if _git("tag", "--points-at", "HEAD", "--list", "v*"):
        ok(f"HEAD is tagged ({last})")
        return
    excludes = _copier_excludes()
    changed = [p for p in _git("diff", "--name-only", f"{last}..HEAD").splitlines() if p]
    relevant = [p for p in changed if _reaches_projects(p, excludes)]
    if not relevant:
        ok(f"no generated-file change since {last}: no new tag needed")
        return
    major, minor, patch = (int(x) for x in last.lstrip("v").split("."))
    nxt = f"v{major}.{minor}.{patch + 1}"
    shown = ", ".join(relevant[:5]) + (", ..." if len(relevant) > 5 else "")
    fail(
        f"{len(relevant)} file(s) reaching projects changed since {last} ({shown}) but HEAD is not tagged: "
        f"copier would keep generating {last}. Run: git tag {nxt} && git push origin main {nxt}"
    )


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
    for cmd in (
        [str(exe), "-m", "ruff", "check", "."],
        [str(exe), "-m", "ruff", "format", "--check", "."],
        [str(exe), "-m", "pytest", "-q"],
    ):
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
        no_api = Path(tmp) / "app-no-api"
        if scaffold(no_api, "has_api=false"):
            check_no_api(no_api)
    check_pin()
    check_trust()
    if not args.fast:
        check_release_tag()
    print()
    if failures:
        print(f"{len(failures)} deviation(s)")
        return 1
    print("template: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
