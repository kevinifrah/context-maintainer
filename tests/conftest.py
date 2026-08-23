import subprocess
from pathlib import Path

import pytest


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def init_git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_git(root, "init", "-b", "main")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "config", "user.name", "Context Maintainer Tests")
    run_git(root, "config", "commit.gpgsign", "false")
    return root


def write(root: Path, relative_path: str, content: str = "placeholder\n") -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def commit_all(root: Path, message: str) -> str:
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", message)
    return run_git(root, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """An initialized but empty git repository."""
    return init_git_repo(tmp_path / "repo")


@pytest.fixture
def blank_repo(git_repo: Path) -> Path:
    """A repository with only the files a brand-new project already has."""
    write(git_repo, "README.md", "# demo\n")
    write(git_repo, "LICENSE", "MIT\n")
    write(git_repo, ".gitignore", "__pycache__/\n")
    commit_all(git_repo, "Initial commit")
    write(git_repo, "README.md", "# demo\n\nA description.\n")
    commit_all(git_repo, "Expand README")
    return git_repo


@pytest.fixture
def existing_repo(git_repo: Path) -> Path:
    """A small but real Python project with history."""
    write(git_repo, "README.md", "# app\n")
    write(git_repo, "pyproject.toml", '[project]\nname = "app"\nversion = "0.1.0"\n')
    commit_all(git_repo, "Add project manifest")
    write(git_repo, "src/app/__init__.py", "")
    write(git_repo, "src/app/main.py", "def main():\n    return 'hello'\n")
    commit_all(git_repo, "Add application entry point")
    write(
        git_repo,
        "tests/test_main.py",
        "from app.main import main\n\n\ndef test_main():\n    assert main() == 'hello'\n",
    )
    commit_all(git_repo, "Add tests")
    return git_repo
