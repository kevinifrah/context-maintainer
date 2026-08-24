"""Thin, dependency-free wrapper around the `git` executable.

Git is the authoritative source for change tracking, so every call here shells
out to the real thing rather than reimplementing any of it.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


class GitError(Exception):
    """Base class for git problems."""


class GitNotAvailableError(GitError):
    """The `git` executable could not be found on PATH."""


class NotAGitRepoError(GitError):
    """The given directory is not inside a git working tree."""


def is_git_available() -> bool:
    return shutil.which("git") is not None


def _run(root: Path, *args: str, check: bool = True) -> "subprocess.CompletedProcess[str]":
    if not is_git_available():
        raise GitNotAvailableError("git executable not found on PATH")
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "not a git repository" in stderr.lower():
            raise NotAGitRepoError(stderr)
        raise GitError(f"git {' '.join(args)} failed: {stderr}")
    return result


def get_repo_root(start: Path) -> Optional[Path]:
    """The top level of the git working tree containing `start`, or None."""
    if not is_git_available():
        return None
    result = _run(start, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        return None
    top = result.stdout.strip()
    return Path(top) if top else None


def is_git_repo(root: Path) -> bool:
    return get_repo_root(root) is not None


def get_head_commit(root: Path) -> Optional[str]:
    """Full SHA of HEAD, or None when the repository has no commits yet."""
    result = _run(root, "rev-parse", "HEAD", check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def get_current_branch(root: Path) -> Optional[str]:
    result = _run(root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def get_commit_count(root: Path) -> int:
    result = _run(root, "rev-list", "--count", "HEAD", check=False)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def get_tracked_files(root: Path) -> List[str]:
    result = _run(root, "ls-files", check=False)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def commit_exists(root: Path, commit: str) -> bool:
    result = _run(root, "cat-file", "-e", f"{commit}^{{commit}}", check=False)
    return result.returncode == 0


def is_ancestor(root: Path, commit: str) -> bool:
    """True if `commit` is an ancestor of (or equal to) HEAD."""
    result = _run(root, "merge-base", "--is-ancestor", commit, "HEAD", check=False)
    return result.returncode == 0


def get_log(root: Path, count: int = 20) -> List[Tuple[str, str]]:
    """Recent commits as (short sha, subject) pairs, newest first."""
    result = _run(
        root, "log", f"-{count}", "--no-merges", "--pretty=format:%h%x1f%s", check=False
    )
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            commits.append((sha, subject))
    return commits


def get_commits_since(root: Path, commit: str) -> List[Tuple[str, str]]:
    """Commits reachable from HEAD but not from `commit`, newest first."""
    result = _run(
        root, "log", f"{commit}..HEAD", "--pretty=format:%h%x1f%s", check=False
    )
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            commits.append((sha, subject))
    return commits


def get_changed_files_since(root: Path, commit: str) -> List[Tuple[str, str]]:
    """Committed changes between `commit` and HEAD as (status, path) pairs."""
    result = _run(root, "diff", "--name-status", commit, "HEAD", check=False)
    if result.returncode != 0:
        return []
    changes = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            # Renames report `R100\told\tnew`; report the destination path.
            changes.append((parts[0], parts[-1]))
    return changes


def get_working_tree_changes(root: Path) -> List[Tuple[str, str]]:
    """Uncommitted changes as (porcelain status, path) pairs."""
    result = _run(root, "status", "--porcelain", check=False)
    if result.returncode != 0:
        return []
    changes = []
    for line in result.stdout.splitlines():
        if len(line) > 3:
            changes.append((line[:2].strip(), line[3:].strip()))
    return changes


def is_path_dirty(root: Path, relative_path: str) -> bool:
    """True if a tracked path has uncommitted modifications."""
    result = _run(root, "status", "--porcelain", "--", relative_path, check=False)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def get_tags(root: Path) -> List[str]:
    """Tags, newest version first.

    `--sort=-v:refname` orders `v0.10.0` above `v0.9.0`, which plain lexical
    sorting gets wrong — and a released-version claim compared against the
    wrong "latest" tag is worse than no comparison at all.
    """
    result = _run(root, "tag", "--sort=-v:refname", check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_last_commit_touching(root: Path, relative_path: str) -> Optional[str]:
    """Short SHA of the most recent commit that changed `relative_path`.

    This is the per-file baseline that makes evidence drift precise: a claim
    citing `doctor.py` goes stale when `doctor.py` moves, and stays untouched
    when some unrelated file does. Comparing against the checkpoint instead
    would flag every claim on every commit.
    """
    result = _run(
        root, "log", "-1", "--pretty=format:%h", "--", relative_path, check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
