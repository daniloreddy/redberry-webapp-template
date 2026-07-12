from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent

# Files the template owns outright (rules: "copiare verbatim" / "reference implementation").
# After alignment these must be byte-identical to the generated skeleton — any divergence
# here is a bug in the alignment, not a legitimate per-project customization.
TEMPLATE_OWNED_FILES = {
    "app/main.py",
    "app/ui/router.py",
    "app/ui/auth.py",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose-dev.yml",
    ".dockerignore",
    "static/login.html",
    "scripts/run.bat",
    "scripts/run.sh",
    "scripts/checks.bat",
    "scripts/checks.sh",
    "scripts/set_password.py",
}

# Directories that are never candidates for template alignment: build/venv artifacts,
# runtime data, and per-project working notes (.claude session state, debug dumps, docs
# drafts) that have no counterpart in the template and aren't business logic either.
EXCLUDE_DIRS = {
    ".git", "data", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".nicegui", "venv", ".venv", "node_modules", "tools",
    ".claude", "debug", "docs",
}

# Filenames excluded regardless of directory. ".env" specifically: never inspected per
# project rules (secrets), and it's always project-specific — never a template file.
EXCLUDE_FILENAMES = {".env"}


def _iter_files(root: Path) -> set[str]:
    files: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        for name in filenames:
            if name in EXCLUDE_FILENAMES:
                continue
            files.add((rel_dir / name).as_posix())
    return files


def _generate_skeleton(dest: Path, app_name: str, app_slug: str | None, github_owner: str) -> None:
    cmd = [
        "copier", "copy", str(TEMPLATE_ROOT), str(dest),
        "--data", f"app_name={app_name}",
        "--data", f"github_owner={github_owner}",
        "--defaults", "--force",
    ]
    if app_slug:
        cmd += ["--data", f"app_slug={app_slug}"]
    subprocess.run(cmd, check=True)


def _checklist(title: str, items: list[str], checkbox: bool) -> list[str]:
    lines = [f"\n## {title}\n"]
    if not items:
        lines.append("(nessuno)")
        return lines
    prefix = "- [ ] " if checkbox else "- "
    lines.extend(f"{prefix}`{item}`" for item in items)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Confronta un progetto esistente con lo skeleton generato dal template, "
        "per allinearlo senza lasciare pezzi divergenti."
    )
    parser.add_argument("target", type=Path, help="Path del progetto esistente da allineare")
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--app-slug", default=None)
    parser.add_argument("--github-owner", default="daniloreddy")
    parser.add_argument("--report", type=Path, default=None, help="Scrive il report anche su file (markdown)")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.is_dir():
        print(f"Target non trovato: {target}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="align_to_template_") as tmp:
        skeleton = Path(tmp) / "skeleton"
        _generate_skeleton(skeleton, args.app_name, args.app_slug, args.github_owner)

        skeleton_files = _iter_files(skeleton)
        target_files = _iter_files(target)
        common = sorted(skeleton_files & target_files)

        diverging_owned: list[str] = []
        diverging_other: list[str] = []
        identical: list[str] = []
        for rel in common:
            if (skeleton / rel).read_bytes() == (target / rel).read_bytes():
                identical.append(rel)
            elif rel in TEMPLATE_OWNED_FILES:
                diverging_owned.append(rel)
            else:
                diverging_other.append(rel)

        lines = [f"# Report allineamento — {target}\n", f"Skeleton generato da: {TEMPLATE_ROOT}\n"]
        lines += _checklist(
            "1. File owned dal template, DIVERGENTI — sostituzione integrale obbligatoria",
            diverging_owned, checkbox=True,
        )
        lines += _checklist(
            "2. File comuni non owned dal template — divergenza attesa, verificare comunque",
            diverging_other, checkbox=False,
        )
        lines += _checklist(
            "3. File SOLO nel progetto target — business logic da valutare/portare",
            sorted(target_files - skeleton_files), checkbox=True,
        )
        lines += _checklist(
            "4. File SOLO nello skeleton — mancanti nel progetto target",
            sorted(skeleton_files - target_files), checkbox=True,
        )
        lines.append(f"\n## 5. File identici: {len(identical)}\n")

        report = "\n".join(lines) + "\n"
        print(report)
        if args.report:
            args.report.write_text(report, encoding="utf-8")
            print(f"\nReport scritto in {args.report}")


if __name__ == "__main__":
    main()
