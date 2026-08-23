"""Deterministic validation of the context contract.

Every check here is mechanical — no judgment, no prose generation. `doctor`
reports and never repairs unless explicitly asked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import contract, gitutil, manifest as manifest_mod, mcp_companion, mdsections
from . import repomix as repomix_mod

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

#: How far the checkpoint may fall behind HEAD before it is worth flagging.
_STALE_COMMIT_THRESHOLD = 10

_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    remediation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass
class DoctorReport:
    results: List[CheckResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if any(r.status == FAIL for r in self.results):
            return FAIL
        if any(r.status == WARN for r in self.results):
            return WARN
        return PASS

    def failed(self, strict: bool = False) -> bool:
        if self.overall == FAIL:
            return True
        return strict and self.overall == WARN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "results": [r.to_dict() for r in self.results],
        }


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check_manifest_exists_and_parses(root: Path) -> CheckResult:
    path = root / contract.MANIFEST_PATH
    if not path.exists():
        return CheckResult(
            "manifest_present",
            FAIL,
            f"{contract.MANIFEST_PATH} is missing — this repository is not initialized.",
            "Run `context-maintainer init`.",
        )
    try:
        manifest_mod.load_manifest(path)
    except manifest_mod.ManifestError as exc:
        return CheckResult(
            "manifest_present",
            FAIL,
            f"{contract.MANIFEST_PATH} could not be loaded: {exc}",
            "Repair the JSON by hand, or run `context-maintainer rebuild`.",
        )
    return CheckResult("manifest_present", PASS, "Manifest present and parseable.")


def check_manifest_schema_valid(root: Path) -> CheckResult:
    path = root / contract.MANIFEST_PATH
    text = _read(path)
    if text is None:
        return CheckResult(
            "manifest_schema", FAIL, "Manifest unreadable.", "Run `context-maintainer init`."
        )
    import json

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return CheckResult(
            "manifest_schema", FAIL, f"Manifest is not valid JSON: {exc}", "Fix the JSON syntax."
        )
    problems = manifest_mod.validate_manifest_dict(data)
    if problems:
        return CheckResult(
            "manifest_schema",
            FAIL,
            "Manifest schema problems: " + "; ".join(problems),
            "Remove unexpected keys; the manifest holds metadata only.",
        )
    return CheckResult("manifest_schema", PASS, "Manifest schema is valid.")


def check_required_files_present(root: Path) -> CheckResult:
    missing = [
        cf.relative_path
        for cf in contract.CONTRACT_FILES
        if not (root / cf.relative_path).exists()
    ]
    if missing:
        return CheckResult(
            "required_files",
            FAIL,
            "Missing required context files: " + ", ".join(missing),
            "Run `context-maintainer init` (or `rebuild` if already initialized).",
        )
    return CheckResult(
        "required_files", PASS, f"All {len(contract.CONTRACT_FILES)} contract files present."
    )


def check_claude_md_imports_agents_md(root: Path) -> CheckResult:
    path = root / "CLAUDE.md"
    text = _read(path)
    if text is None:
        return CheckResult(
            "claude_agents_bridge",
            FAIL,
            "CLAUDE.md is missing.",
            "Run `context-maintainer init`.",
        )
    first_meaningful = next(
        (line.strip() for line in text.splitlines() if line.strip()), ""
    )
    if first_meaningful != "@AGENTS.md":
        return CheckResult(
            "claude_agents_bridge",
            FAIL,
            f"CLAUDE.md must begin with `@AGENTS.md` (found: {first_meaningful!r}).",
            "Make `@AGENTS.md` the first non-empty line of CLAUDE.md.",
        )
    return CheckResult(
        "claude_agents_bridge", PASS, "CLAUDE.md imports AGENTS.md correctly."
    )


def check_required_sections_present(root: Path) -> CheckResult:
    problems: List[str] = []
    for contract_file in contract.CONTRACT_FILES:
        if not contract_file.required_sections:
            continue
        text = _read(root / contract_file.relative_path)
        if text is None:
            problems.append(f"{contract_file.relative_path}: unreadable")
            continue
        present = set(mdsections.list_headings(text))
        missing = [s for s in contract_file.required_sections if s not in present]
        if missing:
            problems.append(
                f"{contract_file.relative_path}: missing {', '.join(missing)}"
            )
    if problems:
        return CheckResult(
            "required_sections",
            FAIL,
            "Required sections missing — " + "; ".join(problems),
            "Restore the missing `## ` headings; the contract depends on them.",
        )
    return CheckResult(
        "required_sections", PASS, "All required sections present in every context document."
    )


def check_decisions_has_entries(root: Path) -> CheckResult:
    text = _read(root / "docs/context/DECISIONS.md")
    if text is None:
        return CheckResult(
            "decisions_entries", FAIL, "DECISIONS.md is missing.", "Run `context-maintainer init`."
        )
    entries = [h for h in mdsections.list_headings(text) if h.upper().startswith("DEC-")]
    if not entries:
        return CheckResult(
            "decisions_entries",
            WARN,
            "DECISIONS.md contains no `## DEC-NNN: ...` entries.",
            "Record at least the decision to adopt this context contract.",
        )
    return CheckResult(
        "decisions_entries", PASS, f"DECISIONS.md contains {len(entries)} decision entry/entries."
    )


def check_no_template_placeholders_remaining(root: Path) -> CheckResult:
    stale: List[str] = []
    for contract_file in contract.CONTRACT_FILES:
        text = _read(root / contract_file.relative_path)
        if text and contract.PLACEHOLDER_SENTINEL in text:
            count = text.count(contract.PLACEHOLDER_SENTINEL)
            stale.append(f"{contract_file.relative_path} ({count})")
    if stale:
        return CheckResult(
            "no_placeholders",
            WARN,
            "Template placeholders still present in: " + ", ".join(stale),
            "Populate these sections with real, evidence-based content.",
        )
    return CheckResult("no_placeholders", PASS, "No template placeholders remain.")


def check_git_checkpoint_valid(root: Path) -> CheckResult:
    path = root / contract.MANIFEST_PATH
    if not path.exists():
        return CheckResult(
            "checkpoint_valid", FAIL, "No manifest, so no checkpoint.", "Run `context-maintainer init`."
        )
    try:
        loaded = manifest_mod.load_manifest(path)
    except manifest_mod.ManifestError as exc:
        return CheckResult("checkpoint_valid", FAIL, str(exc), "Repair the manifest.")

    commit = loaded.last_verified_commit
    if commit is None:
        return CheckResult(
            "checkpoint_valid",
            PASS,
            "No checkpoint recorded yet (expected for a repository with no commits).",
        )
    if not gitutil.is_git_repo(root):
        return CheckResult(
            "checkpoint_valid",
            WARN,
            f"Checkpoint {commit[:8]} recorded but this is not a git repository.",
            "Re-run `context-maintainer sync --finalize` inside a git repository.",
        )
    if not gitutil.commit_exists(root, commit):
        return CheckResult(
            "checkpoint_valid",
            FAIL,
            f"Checkpoint commit {commit[:8]} does not exist in this repository "
            "(history rewritten, or the manifest came from elsewhere).",
            "Run `context-maintainer sync --finalize` to reset the checkpoint to HEAD.",
        )
    return CheckResult(
        "checkpoint_valid", PASS, f"Checkpoint {commit[:8]} exists in history."
    )


def check_git_checkpoint_not_far_behind_head(root: Path) -> CheckResult:
    path = root / contract.MANIFEST_PATH
    if not path.exists() or not gitutil.is_git_repo(root):
        return CheckResult(
            "checkpoint_freshness", PASS, "Not applicable (no manifest or not a git repository)."
        )
    try:
        loaded = manifest_mod.load_manifest(path)
    except manifest_mod.ManifestError:
        return CheckResult("checkpoint_freshness", PASS, "Not applicable (manifest invalid).")

    commit = loaded.last_verified_commit
    head = gitutil.get_head_commit(root)
    if commit is None or head is None:
        return CheckResult("checkpoint_freshness", PASS, "No checkpoint to compare yet.")
    if commit == head:
        return CheckResult("checkpoint_freshness", PASS, "Context checkpoint matches HEAD.")
    if not gitutil.commit_exists(root, commit):
        return CheckResult(
            "checkpoint_freshness", PASS, "Not applicable (checkpoint commit missing)."
        )

    commits = gitutil.get_commits_since(root, commit)
    changed = gitutil.get_changed_files_since(root, commit)
    behind = len(commits)
    status = WARN if behind >= _STALE_COMMIT_THRESHOLD else PASS
    message = (
        f"Context is {behind} commit(s) behind HEAD "
        f"({len(changed)} file(s) changed since {commit[:8]})."
    )
    return CheckResult(
        "checkpoint_freshness",
        status,
        message,
        "Run `context-maintainer sync` to review what changed." if status == WARN else None,
    )


def check_cache_gitignored(root: Path) -> CheckResult:
    cache_ignore = root / contract.CACHE_DIR / ".gitignore"
    if cache_ignore.exists() and "*" in (_read(cache_ignore) or ""):
        return CheckResult("cache_ignored", PASS, "Cache directory ignores its own contents.")

    root_ignore = _read(root / ".gitignore") or ""
    if ".context-maintainer/cache" in root_ignore:
        return CheckResult(
            "cache_ignored", PASS, "Cache directory ignored via the root .gitignore."
        )
    return CheckResult(
        "cache_ignored",
        WARN,
        f"{contract.CACHE_DIR} is not ignored; raw audit artifacts could be committed.",
        f"Create {contract.CACHE_DIR}/.gitignore containing `*`.",
    )


def check_context_files_not_oversized(root: Path) -> CheckResult:
    oversized: List[str] = []
    for path in contract.context_document_paths(root):
        if path.exists() and path.stat().st_size > contract.MAX_CONTEXT_FILE_BYTES:
            oversized.append(f"{path.name} ({path.stat().st_size // 1024} KiB)")
    if oversized:
        return CheckResult(
            "context_size",
            WARN,
            "Context documents are unusually large: " + ", ".join(oversized),
            "These should stay compact briefings; move history to Git and "
            "durable rationale to DECISIONS.md.",
        )
    return CheckResult("context_size", PASS, "Context documents are a reasonable size.")


def check_no_duplicated_instructions(root: Path) -> CheckResult:
    """AGENTS.md should route to docs/context/, not restate it."""
    agents_text = _read(root / "AGENTS.md")
    if agents_text is None:
        return CheckResult("no_duplication", PASS, "Not applicable (no AGENTS.md).")

    agents_lines = {
        line.strip()
        for line in agents_text.splitlines()
        if len(line.strip()) >= 80 and not line.strip().startswith(("-", "*", ">", "#"))
    }
    if not agents_lines:
        return CheckResult(
            "no_duplication", PASS, "AGENTS.md contains no long prose blocks to duplicate."
        )

    duplicates: List[str] = []
    for path in contract.context_document_paths(root):
        text = _read(path)
        if not text:
            continue
        for line in agents_lines:
            if line in text:
                duplicates.append(f"{path.name}")
                break
    if duplicates:
        return CheckResult(
            "no_duplication",
            WARN,
            "AGENTS.md appears to restate content from: " + ", ".join(sorted(set(duplicates))),
            "Keep AGENTS.md a thin router — link to docs/context/ instead of copying it.",
        )
    return CheckResult("no_duplication", PASS, "AGENTS.md does not duplicate context documents.")


def check_referenced_paths_exist(root: Path) -> CheckResult:
    """Relative links inside the contract should point at real files."""
    broken: List[str] = []
    targets = [root / "AGENTS.md"] + contract.context_document_paths(root)
    for path in targets:
        text = _read(path)
        if not text:
            continue
        for link in _LINK_PATTERN.findall(text):
            target = link.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{path.name} -> {target}")
    if broken:
        return CheckResult(
            "referenced_paths",
            WARN,
            "Broken relative links: " + ", ".join(broken[:10]),
            "Fix or remove links to paths that no longer exist.",
        )
    return CheckResult("referenced_paths", PASS, "All relative links resolve.")


def check_repomix_available(root: Path) -> CheckResult:
    """Repomix powers the audit passes; missing it degrades, never breaks."""
    version = repomix_mod.get_repomix_version()
    if version:
        return CheckResult(
            "repomix_available", PASS, f"Repomix {version} is available."
        )
    if repomix_mod.is_repomix_available():
        return CheckResult(
            "repomix_available",
            WARN,
            "Repomix is on PATH but did not report a version.",
            "Check that `repomix --version` works.",
        )
    return CheckResult(
        "repomix_available",
        WARN,
        "Repomix is not installed — repository audits run in degraded mode.",
        repomix_mod.INSTALL_HINT,
    )


def check_mcp_language_server_configured(root: Path) -> CheckResult:
    """Informational only: the companion is optional by design."""
    status = mcp_companion.detect(root)
    if status.configured:
        where = ", ".join(status.locations)
        names = ", ".join(status.server_names) if status.server_names else "unnamed"
        return CheckResult(
            "mcp_language_server",
            PASS,
            f"mcp-language-server configured ({names}) via {where}.",
        )
    return CheckResult(
        "mcp_language_server",
        PASS,
        "mcp-language-server is not configured (optional). Structural analysis "
        "will rely on Repomix, Git, and direct file reading.",
    )


#: Ordered so the most fundamental failures are reported first.
CHECKS: List[Callable[[Path], CheckResult]] = [
    check_manifest_exists_and_parses,
    check_manifest_schema_valid,
    check_required_files_present,
    check_claude_md_imports_agents_md,
    check_required_sections_present,
    check_decisions_has_entries,
    check_no_template_placeholders_remaining,
    check_git_checkpoint_valid,
    check_git_checkpoint_not_far_behind_head,
    check_cache_gitignored,
    check_context_files_not_oversized,
    check_no_duplicated_instructions,
    check_referenced_paths_exist,
    check_repomix_available,
    check_mcp_language_server_configured,
]


def run_all_checks(root: Path) -> DoctorReport:
    root = Path(root)
    return DoctorReport(results=[check(root) for check in CHECKS])


def render_text(report: DoctorReport) -> str:
    lines = []
    for result in report.results:
        lines.append(f"[{result.status}] {result.name}: {result.message}")
        if result.remediation and result.status != PASS:
            lines.append(f"         → {result.remediation}")
    lines.append("")
    lines.append(f"Overall: {report.overall}")
    return "\n".join(lines)
