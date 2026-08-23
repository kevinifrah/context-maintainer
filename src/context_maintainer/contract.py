"""The context contract: which files must exist and which sections they must contain.

This module is the single source of truth for the contract. `scaffold.py` writes
files from it, `doctor.py` validates against it, and the skill's
`references/context-contract.md` is tested for agreement with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

#: Marker left in generated templates wherever real content is still missing.
PLACEHOLDER_SENTINEL = "<!-- CONTEXT-MAINTAINER: PLACEHOLDER -->"

MANIFEST_PATH = ".context-maintainer/manifest.json"
CACHE_DIR = ".context-maintainer/cache"
BACKUP_DIR = ".context-maintainer/cache/backups"
CONTEXT_DIR = "docs/context"

#: Context documents larger than this are almost certainly accumulating churn
#: rather than staying a compact briefing.
MAX_CONTEXT_FILE_BYTES = 32_768


@dataclass(frozen=True)
class ContractFile:
    """One file required by the context contract."""

    relative_path: str
    template_name: str
    required_sections: Tuple[str, ...] = field(default=())
    #: True for files whose body is a list of `## DEC-NNN: ...` entries rather
    #: than a fixed set of headings.
    requires_decision_entries: bool = False
    #: True for files that must begin by importing AGENTS.md.
    requires_agents_import: bool = False


CONTRACT_FILES: Tuple[ContractFile, ...] = (
    ContractFile(
        relative_path="AGENTS.md",
        template_name="AGENTS.md.tmpl",
        required_sections=("Project context", "Rules for coding agents"),
    ),
    ContractFile(
        relative_path="CLAUDE.md",
        template_name="CLAUDE.md.tmpl",
        requires_agents_import=True,
    ),
    ContractFile(
        relative_path="docs/context/PROJECT.md",
        template_name="PROJECT.md.tmpl",
        required_sections=(
            "Goal",
            "Problem",
            "Users",
            "Success Criteria",
            "Scope",
            "Non-Goals",
            "Constraints",
        ),
    ),
    ContractFile(
        relative_path="docs/context/ARCHITECTURE.md",
        template_name="ARCHITECTURE.md.tmpl",
        required_sections=(
            "Overview",
            "Components",
            "Data Flow",
            "Persistence",
            "Integrations",
            "Entry Points",
            "Evidence Level",
        ),
    ),
    ContractFile(
        relative_path="docs/context/WORKFLOWS.md",
        template_name="WORKFLOWS.md.tmpl",
        required_sections=("Development", "Testing", "Build", "Deploy", "Notes"),
    ),
    ContractFile(
        relative_path="docs/context/STATE.md",
        template_name="STATE.md.tmpl",
        required_sections=(
            "Phase",
            "Objective",
            "Implemented",
            "In Progress",
            "Blockers",
            "Next",
        ),
    ),
    ContractFile(
        relative_path="docs/context/DECISIONS.md",
        template_name="DECISIONS.md.tmpl",
        requires_decision_entries=True,
    ),
)


def all_required_paths(root: Path) -> List[Path]:
    """Absolute paths of every file the contract requires, including the manifest."""
    paths = [root / cf.relative_path for cf in CONTRACT_FILES]
    paths.append(root / MANIFEST_PATH)
    return paths


def get_contract_file(relative_path: str) -> ContractFile:
    for cf in CONTRACT_FILES:
        if cf.relative_path == relative_path:
            return cf
    raise KeyError(relative_path)


def context_document_paths(root: Path) -> List[Path]:
    """The five durable knowledge documents under docs/context/."""
    return [
        root / cf.relative_path
        for cf in CONTRACT_FILES
        if cf.relative_path.startswith(CONTEXT_DIR + "/")
    ]
