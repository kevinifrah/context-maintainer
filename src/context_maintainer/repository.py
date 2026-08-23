"""Repository discovery and the blank-vs-existing classification heuristic.

The heuristic deliberately ignores files that say nothing about whether a real
project exists: git plumbing, an empty README, a license, editor cruft, and
Context Maintainer's own output.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import contract, gitutil

#: Directories never worth walking when sizing up a project.
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "bower_components",
        "vendor",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "site-packages",
        "dist",
        "build",
        "out",
        "target",
        ".next",
        ".nuxt",
        ".cache",
        ".gradle",
        ".terraform",
        ".idea",
        ".DS_Store",
        ".context-maintainer",
    }
)

#: Filenames that a brand-new, empty repository routinely already has.
TRIVIAL_FILENAMES = frozenset(
    {
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme",
        "license",
        "license.md",
        "license.txt",
        "licence",
        "copying",
        "notice",
        "changelog.md",
        "contributing.md",
        "code_of_conduct.md",
        ".gitignore",
        ".gitattributes",
        ".gitkeep",
        ".keep",
        ".editorconfig",
        ".ds_store",
        "thumbs.db",
    }
)

#: Presence of any of these is strong evidence of a real project.
SIGNIFICANT_MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "pipfile",
        "poetry.lock",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "gemfile",
        "composer.json",
        "makefile",
        "cmakelists.txt",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "build.sbt",
        "mix.exs",
        "pubspec.yaml",
        "deno.json",
        "tsconfig.json",
        "gradle.properties",
        "project.clj",
        "stack.yaml",
        "cabal.project",
        "*.csproj",
        "*.sln",
    }
)

SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".mjs",
        ".cjs",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".kts",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".cxx",
        ".hpp",
        ".cs",
        ".swift",
        ".m",
        ".mm",
        ".scala",
        ".ex",
        ".exs",
        ".erl",
        ".clj",
        ".cljs",
        ".hs",
        ".lua",
        ".pl",
        ".pm",
        ".r",
        ".dart",
        ".vue",
        ".svelte",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
    }
)

#: Paths Context Maintainer itself creates — never evidence of a pre-existing project.
_OWNED_FILES = frozenset({"AGENTS.md", "CLAUDE.md"})
_OWNED_PREFIXES = (contract.CONTEXT_DIR + "/", ".context-maintainer/")

MODE_BLANK = "blank"
MODE_EXISTING = "existing"

#: Secondary threshold: a docs/config-only repository still counts as existing
#: once it has both real content and real history.
_NON_TRIVIAL_FILE_FLOOR = 3
_COMMIT_FLOOR = 3


@dataclass
class RepoContext:
    """Everything deterministic we know about where we are."""

    root: Path
    is_git_repo: bool
    head_commit: Optional[str] = None
    branch: Optional[str] = None
    commit_count: int = 0

    @property
    def has_commits(self) -> bool:
        return self.head_commit is not None


@dataclass
class ProjectClassification:
    mode: str
    evidence: List[str] = field(default_factory=list)
    non_trivial_file_count: int = 0
    commit_count: int = 0
    overridden: bool = False

    @property
    def is_existing(self) -> bool:
        return self.mode == MODE_EXISTING


def find_repo_root(start: Path) -> Path:
    """The git top level if there is one, else `start` itself."""
    start = Path(start).resolve()
    git_root = gitutil.get_repo_root(start)
    return git_root.resolve() if git_root else start


def describe_repo(root: Path) -> RepoContext:
    root = Path(root)
    if not gitutil.is_git_available() or not gitutil.is_git_repo(root):
        return RepoContext(root=root, is_git_repo=False)
    return RepoContext(
        root=root,
        is_git_repo=True,
        head_commit=gitutil.get_head_commit(root),
        branch=gitutil.get_current_branch(root),
        commit_count=gitutil.get_commit_count(root),
    )


def _is_owned_by_context_maintainer(relative_path: str) -> bool:
    if relative_path in _OWNED_FILES:
        return True
    return any(relative_path.startswith(prefix) for prefix in _OWNED_PREFIXES)


def iter_candidate_files(root: Path) -> List[str]:
    """Repo-relative paths worth considering, excluding noise and our own output."""
    root = Path(root)
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for filename in sorted(filenames):
            absolute = Path(dirpath) / filename
            try:
                relative = absolute.relative_to(root).as_posix()
            except ValueError:  # pragma: no cover - defensive
                continue
            if _is_owned_by_context_maintainer(relative):
                continue
            found.append(relative)
    return found


def _is_manifest(filename: str) -> bool:
    lowered = filename.lower()
    if lowered in SIGNIFICANT_MANIFEST_NAMES:
        return True
    return lowered.endswith((".csproj", ".sln"))


def classify(root: Path, mode: str = "auto") -> ProjectClassification:
    """Decide whether this repository is effectively blank or already a project."""
    root = Path(root)
    candidates = iter_candidate_files(root)
    commit_count = gitutil.get_commit_count(root) if gitutil.is_git_repo(root) else 0

    manifests: List[str] = []
    sources: List[str] = []
    non_trivial: List[str] = []

    for relative in candidates:
        filename = Path(relative).name
        if _is_manifest(filename):
            manifests.append(relative)
        if Path(relative).suffix.lower() in SOURCE_EXTENSIONS:
            sources.append(relative)
        if filename.lower() not in TRIVIAL_FILENAMES:
            non_trivial.append(relative)

    evidence: List[str] = []
    if manifests:
        evidence.append(
            "manifest(s): " + ", ".join(sorted(manifests)[:5])
        )
    if sources:
        evidence.append(
            f"{len(sources)} source file(s), e.g. " + ", ".join(sorted(sources)[:5])
        )
    if non_trivial:
        evidence.append(f"{len(non_trivial)} non-trivial file(s)")
    if commit_count:
        evidence.append(f"{commit_count} commit(s)")

    if mode in (MODE_BLANK, MODE_EXISTING):
        return ProjectClassification(
            mode=mode,
            evidence=[f"mode override: --mode {mode}"] + evidence,
            non_trivial_file_count=len(non_trivial),
            commit_count=commit_count,
            overridden=True,
        )

    detected = MODE_BLANK
    if manifests or sources:
        detected = MODE_EXISTING
    elif len(non_trivial) >= _NON_TRIVIAL_FILE_FLOOR and commit_count >= _COMMIT_FLOOR:
        detected = MODE_EXISTING
        evidence.append(
            f"no manifest or source files, but >= {_NON_TRIVIAL_FILE_FLOOR} "
            f"non-trivial files and >= {_COMMIT_FLOOR} commits"
        )

    if detected == MODE_BLANK:
        evidence.append("no manifests, no source files, insufficient other material")

    return ProjectClassification(
        mode=detected,
        evidence=evidence,
        non_trivial_file_count=len(non_trivial),
        commit_count=commit_count,
    )


def is_initialized(root: Path) -> bool:
    return (Path(root) / contract.MANIFEST_PATH).exists()
