"""Create the contract's files on disk, safely.

Two safety rules matter more than convenience here: an existing file is never
silently overwritten, and anything we do replace is backed up first.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import contract, gitutil

TEMPLATES_DIR = Path(__file__).parent / "templates"

_CACHE_GITIGNORE_BODY = "*\n!.gitignore\n"

#: Files that carry agent instructions and may already exist in a repository.
_AGENT_FILENAMES = frozenset({"AGENTS.md", "CLAUDE.md", "GEMINI.md"})
_AGENT_EXTRA_PATHS = (
    ".cursorrules",
    ".windsurfrules",
    ".github/copilot-instructions.md",
)


@dataclass
class ScaffoldResult:
    created: List[str] = field(default_factory=list)
    preserved: List[str] = field(default_factory=list)
    backed_up: List[str] = field(default_factory=list)

    @property
    def wrote_anything(self) -> bool:
        return bool(self.created)


@dataclass
class AgentFile:
    """An instruction file that already existed before we ran."""

    relative_path: str
    line_count: int
    size_bytes: int


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"template not found: {name}")
    return path.read_text(encoding="utf-8")


def render_template(name: str, variables: Optional[Dict[str, str]] = None) -> str:
    """Render a template by literal `{key}` substitution.

    Deliberately not `str.format`: templates contain Markdown and JSON braces
    that must survive untouched.
    """
    text = load_template(name)
    for key, value in (variables or {}).items():
        text = text.replace("{" + key + "}", value)
    return text


def timestamp_slug(now: Optional[datetime] = None) -> str:
    moment = now or datetime.now(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def backup_file(root: Path, relative_path: str, slug: Optional[str] = None) -> Path:
    """Copy a file into the ignored backup cache, preserving its relative path."""
    root = Path(root)
    source = root / relative_path
    destination = (
        root / contract.BACKUP_DIR / (slug or timestamp_slug()) / relative_path
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def ensure_cache_gitignore(root: Path) -> Path:
    """Make the cache directory exist and ignore its own contents."""
    cache_dir = Path(root) / contract.CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    gitignore = cache_dir / ".gitignore"
    current = gitignore.read_text(encoding="utf-8") if gitignore.exists() else None
    if current != _CACHE_GITIGNORE_BODY:
        gitignore.write_text(_CACHE_GITIGNORE_BODY, encoding="utf-8")
    return gitignore


def is_path_git_dirty(root: Path, relative_path: str) -> bool:
    """True when a tracked file has uncommitted edits we would destroy."""
    if not gitutil.is_git_repo(Path(root)):
        return False
    return gitutil.is_path_dirty(Path(root), relative_path)


def write_contract_files(
    root: Path,
    project_name: str,
    force: bool = False,
) -> ScaffoldResult:
    """Write every contract file that is missing.

    Existing files are preserved untouched unless `force` is set, in which case
    they are backed up first. A tracked file with uncommitted changes is never
    overwritten, even with `force`.
    """
    root = Path(root)
    result = ScaffoldResult()
    variables = {"project_name": project_name}
    slug = timestamp_slug()

    for contract_file in contract.CONTRACT_FILES:
        target = root / contract_file.relative_path
        rendered = render_template(contract_file.template_name, variables)

        if target.exists():
            if not force:
                result.preserved.append(contract_file.relative_path)
                continue
            if is_path_git_dirty(root, contract_file.relative_path):
                result.preserved.append(contract_file.relative_path)
                continue
            backup_file(root, contract_file.relative_path, slug)
            result.backed_up.append(contract_file.relative_path)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        result.created.append(contract_file.relative_path)

    ensure_cache_gitignore(root)
    return result


def detect_existing_agent_files(root: Path) -> List[AgentFile]:
    """Find instruction files that already exist, at any depth.

    `init` uses this so the skill can merge rather than clobber whatever
    instructions a repository already carries.
    """
    from . import repository  # local import to avoid a cycle

    root = Path(root)
    found: List[AgentFile] = []
    seen = set()

    for relative in repository.iter_candidate_files(root):
        name = Path(relative).name
        if name in _AGENT_FILENAMES or relative in _AGENT_EXTRA_PATHS:
            seen.add(relative)

    # iter_candidate_files skips our own AGENTS.md/CLAUDE.md, so check the root
    # pair explicitly — those are exactly the files migration cares about.
    for candidate in ("AGENTS.md", "CLAUDE.md"):
        if (root / candidate).exists():
            seen.add(candidate)

    for relative in sorted(seen):
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover - defensive
            continue
        found.append(
            AgentFile(
                relative_path=relative,
                line_count=len(text.splitlines()),
                size_bytes=path.stat().st_size,
            )
        )
    return found


def backup_context_documents(root: Path) -> List[str]:
    """Back up every existing contract file; used before a rebuild."""
    root = Path(root)
    slug = timestamp_slug()
    backed_up: List[str] = []
    for contract_file in contract.CONTRACT_FILES:
        if (root / contract_file.relative_path).exists():
            backup_file(root, contract_file.relative_path, slug)
            backed_up.append(contract_file.relative_path)
    return backed_up
