"""Small helpers for driving the real CLI inside a fixture repository."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple


@contextlib.contextmanager
def in_dir(path: Path) -> Iterator[Path]:
    """Temporarily chdir, since the CLI resolves the repo from the cwd."""
    previous = Path.cwd()
    os.chdir(str(path))
    try:
        yield Path(path)
    finally:
        os.chdir(str(previous))


def run_cli(root: Path, argv: Sequence[str]) -> Tuple[int, str]:
    """Invoke the real CLI in-process, capturing stdout."""
    from context_maintainer import cli

    buffer = io.StringIO()
    with in_dir(root), contextlib.redirect_stdout(buffer):
        code = cli.main(list(argv))
    return code, buffer.getvalue()


def cli_json(root: Path, argv: Sequence[str]) -> Tuple[int, dict]:
    code, out = run_cli(root, list(argv) + ["--json"])
    return code, json.loads(out)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "fixture@example.com")
    git(root, "config", "user.name", "Context Maintainer Fixture")
    git(root, "config", "commit.gpgsign", "false")
    return root


def write(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def log_subjects(root: Path) -> List[str]:
    return git(root, "log", "--pretty=format:%s").splitlines()
