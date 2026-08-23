"""Build the `status` briefing: a fast, read-only orientation.

Entirely deterministic — it extracts what the context documents already say and
reports Git reality alongside. Any judgment about whether that content is
*correct* belongs to the skill, not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import contract, gitutil, manifest as manifest_mod, mdsections, repository

_PLACEHOLDER_ITALIC = re.compile(r"^_.*not yet documented.*_$", re.IGNORECASE)
_MAX_SUMMARY_CHARS = 400

#: Ways people write "there is nothing here" — treated as an empty section so
#: `Blockers: None` is not reported back as a blocker. Deliberately excludes
#: "unknown" and "TBD", which are real signals rather than emptiness.
_EMPTY_EQUIVALENTS = frozenset(
    {
        "none",
        "n/a",
        "na",
        "nothing",
        "no blockers",
        "no known blockers",
        "nothing blocking",
        "-",
        "—",
    }
)


@dataclass
class StalenessInfo:
    is_stale: bool = False
    commits_behind: int = 0
    files_changed: int = 0
    checkpoint: Optional[str] = None
    head: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_stale": self.is_stale,
            "commits_behind": self.commits_behind,
            "files_changed": self.files_changed,
            "checkpoint": self.checkpoint,
            "head": self.head,
            "reason": self.reason,
        }


@dataclass
class StatusReport:
    initialized: bool = False
    root: str = ""
    branch: Optional[str] = None
    goal: Optional[str] = None
    phase: Optional[str] = None
    objective: Optional[str] = None
    architecture_summary: Optional[str] = None
    blockers: Optional[str] = None
    next_actions_documented: Optional[str] = None
    recent_changes: List[str] = field(default_factory=list)
    staleness: StalenessInfo = field(default_factory=StalenessInfo)
    placeholder_files: List[str] = field(default_factory=list)
    suggested_next_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initialized": self.initialized,
            "root": self.root,
            "branch": self.branch,
            "goal": self.goal,
            "phase": self.phase,
            "objective": self.objective,
            "architecture_summary": self.architecture_summary,
            "blockers": self.blockers,
            "next_actions_documented": self.next_actions_documented,
            "recent_changes": self.recent_changes,
            "staleness": self.staleness.to_dict(),
            "placeholder_files": self.placeholder_files,
            "suggested_next_actions": self.suggested_next_actions,
        }


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _clean_section(body: Optional[str]) -> Optional[str]:
    """Strip placeholder noise; return None when a section says nothing."""
    if not body:
        return None
    kept: List[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--"):
            continue
        if _PLACEHOLDER_ITALIC.match(stripped):
            continue
        kept.append(stripped)
    if not kept:
        return None
    text = " ".join(kept)
    if text.strip().strip(".").strip().lower() in _EMPTY_EQUIVALENTS:
        return None
    if len(text) > _MAX_SUMMARY_CHARS:
        text = text[: _MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    return text


def _section(root: Path, relative_path: str, heading: str) -> Optional[str]:
    text = _read(root / relative_path)
    if text is None:
        return None
    return _clean_section(mdsections.get_section(text, heading))


def _is_context_owned(relative_path: str) -> bool:
    """True for files Context Maintainer maintains itself.

    Changes confined to these are the *result* of a sync, not evidence that a
    sync is needed.
    """
    if relative_path in ("AGENTS.md", "CLAUDE.md"):
        return True
    return relative_path.startswith(
        (contract.CONTEXT_DIR + "/", ".context-maintainer/")
    )


def _compute_staleness(root: Path, loaded: Optional[manifest_mod.Manifest]) -> StalenessInfo:
    info = StalenessInfo()
    if loaded is None:
        info.reason = "not initialized"
        return info
    if not gitutil.is_git_repo(root):
        info.reason = "not a git repository"
        return info

    head = gitutil.get_head_commit(root)
    info.head = head
    info.checkpoint = loaded.last_verified_commit

    if head is None:
        info.reason = "repository has no commits yet"
        return info
    if loaded.last_verified_commit is None:
        info.is_stale = True
        info.reason = "no checkpoint recorded"
        return info
    if loaded.last_verified_commit == head:
        info.reason = "checkpoint matches HEAD"
        return info
    if not gitutil.commit_exists(root, loaded.last_verified_commit):
        info.is_stale = True
        info.reason = "checkpoint commit no longer exists in history"
        return info

    info.commits_behind = len(gitutil.get_commits_since(root, loaded.last_verified_commit))
    changed = [
        path
        for _, path in gitutil.get_changed_files_since(root, loaded.last_verified_commit)
    ]

    # Finalizing a sync writes the manifest, and committing that write lands
    # *after* the checkpoint it just recorded. Counting our own bookkeeping as
    # drift would make the tool report itself stale immediately after every
    # sync — a false positive that teaches people to ignore the warning.
    substantive = [p for p in changed if not _is_context_owned(p)]
    info.files_changed = len(substantive)

    if not substantive:
        info.reason = (
            f"{info.commits_behind} commit(s) since the checkpoint, all of them "
            "confined to context files — no code drift"
        )
        return info

    info.is_stale = True
    info.reason = (
        f"{info.commits_behind} commit(s) and {len(substantive)} file(s) "
        "changed since the last checkpoint"
    )
    return info


def _placeholder_files(root: Path) -> List[str]:
    stale = []
    for contract_file in contract.CONTRACT_FILES:
        text = _read(root / contract_file.relative_path)
        if text and contract.PLACEHOLDER_SENTINEL in text:
            stale.append(contract_file.relative_path)
    return stale


def build_status_report(root: Path) -> StatusReport:
    root = Path(root)
    report = StatusReport(root=str(root))

    manifest_path = root / contract.MANIFEST_PATH
    loaded: Optional[manifest_mod.Manifest] = None
    if manifest_path.exists():
        try:
            loaded = manifest_mod.load_manifest(manifest_path)
            report.initialized = True
        except manifest_mod.ManifestError:
            report.initialized = False

    if gitutil.is_git_repo(root):
        report.branch = gitutil.get_current_branch(root)
        report.recent_changes = [
            f"{sha} {subject}" for sha, subject in gitutil.get_log(root, 5)
        ]

    report.goal = _section(root, "docs/context/PROJECT.md", "Goal")
    report.phase = _section(root, "docs/context/STATE.md", "Phase")
    report.objective = _section(root, "docs/context/STATE.md", "Objective")
    report.architecture_summary = _section(
        root, "docs/context/ARCHITECTURE.md", "Overview"
    )
    report.blockers = _section(root, "docs/context/STATE.md", "Blockers")
    report.next_actions_documented = _section(root, "docs/context/STATE.md", "Next")

    report.staleness = _compute_staleness(root, loaded)
    report.placeholder_files = _placeholder_files(root)
    report.suggested_next_actions = _suggest_actions(root, report)
    return report


def _suggest_actions(root: Path, report: StatusReport) -> List[str]:
    actions: List[str] = []

    if not report.initialized:
        classification = repository.classify(root)
        actions.append(
            f"Run `context-maintainer init` (detected mode: {classification.mode})."
        )
        return actions

    if report.staleness.is_stale:
        actions.append(
            "Run `context-maintainer sync` — " + report.staleness.reason + "."
        )
    if report.placeholder_files:
        actions.append(
            "Populate placeholder sections in: " + ", ".join(report.placeholder_files) + "."
        )
    if report.blockers:
        actions.append("Address the blockers recorded in STATE.md.")
    if report.next_actions_documented:
        actions.append("Documented next step: " + report.next_actions_documented)
    if not actions:
        actions.append("Context appears current; no maintenance needed.")
    return actions


def render_text(report: StatusReport) -> str:
    def line(label: str, value: Optional[str]) -> str:
        return f"{label:<14} {value if value else '(not documented)'}"

    lines = [f"Context Maintainer status — {report.root}"]
    if not report.initialized:
        lines.append("")
        lines.append("Not initialized (no valid .context-maintainer/manifest.json).")
        for action in report.suggested_next_actions:
            lines.append(f"  → {action}")
        return "\n".join(lines)

    lines.append("")
    lines.append(line("Branch:", report.branch))
    lines.append(line("Goal:", report.goal))
    lines.append(line("Phase:", report.phase))
    lines.append(line("Objective:", report.objective))
    lines.append(line("Architecture:", report.architecture_summary))
    lines.append(line("Blockers:", report.blockers))
    lines.append("")
    lines.append(
        f"Context freshness: {'STALE' if report.staleness.is_stale else 'current'}"
        f" ({report.staleness.reason})"
    )
    if report.recent_changes:
        lines.append("")
        lines.append("Recent commits:")
        for change in report.recent_changes:
            lines.append(f"  {change}")
    lines.append("")
    lines.append("Suggested next actions:")
    for action in report.suggested_next_actions:
        lines.append(f"  → {action}")
    return "\n".join(lines)
