"""Command-line entry point for Context Maintainer.

This layer is deliberately mechanical: it detects state, scaffolds files, gathers
evidence, validates structure, and moves the manifest checkpoint. It never writes
prose and never decides what a change *means* — that judgment belongs to the
context-maintainer skill running inside Claude Code or Codex.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import __version__, briefing, contract, doctor, gitutil, manifest as manifest_mod
from . import contextlog, decisionindex, drift
from . import installer as installer_mod
from . import mcp_companion, repomix as repomix_mod, repository, scaffold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-maintainer",
        description="Maintain durable, evidence-based project context for Claude Code and Codex.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init", help="Initialize the context contract in this repository."
    )
    init_parser.add_argument(
        "--mode",
        choices=["auto", "blank", "existing"],
        default="auto",
        help="Override blank/existing detection (default: auto).",
    )
    init_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser(
        "status", help="Print a fast, read-only briefing of the current project context."
    )
    status_parser.add_argument("--json", action="store_true")

    sync_parser = subparsers.add_parser(
        "sync", help="Report evidence of change since the last checkpoint."
    )
    sync_parser.add_argument(
        "--finalize",
        nargs="?",
        const=True,
        default=False,
        metavar="COMMIT",
        help="Advance the manifest checkpoint (to HEAD, or to COMMIT if given).",
    )
    sync_parser.add_argument(
        "--note",
        default=None,
        help="One line on why context changed, recorded in the context log.",
    )
    sync_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor", help="Validate the context contract deterministically."
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument(
        "--strict", action="store_true", help="Treat WARN results as failing."
    )
    doctor_parser.add_argument(
        "--verify",
        action="store_true",
        help="Also check documented claims against repository evidence.",
    )

    review_parser = subparsers.add_parser(
        "review",
        help="List documented claims whose evidence has moved, for adjudication.",
    )
    review_parser.add_argument("--json", action="store_true")

    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help="Back up the current context so it can be regenerated from fresh evidence.",
    )
    rebuild_parser.add_argument(
        "--prepare",
        action="store_true",
        help="Back up every context file and report what needs regenerating.",
    )
    rebuild_parser.add_argument(
        "--finalize",
        nargs="?",
        const=True,
        default=False,
        metavar="COMMIT",
        help="Advance the manifest checkpoint after regeneration.",
    )
    rebuild_parser.add_argument(
        "--note",
        default=None,
        help="One line on why context was rebuilt, recorded in the context log.",
    )
    rebuild_parser.add_argument("--json", action="store_true")

    audit_parser = subparsers.add_parser(
        "audit",
        help="Gather raw repository evidence into the ignored cache (never edits context).",
    )
    audit_mode = audit_parser.add_mutually_exclusive_group()
    audit_mode.add_argument(
        "--structure-only",
        action="store_true",
        help="Cheap metadata/structure pass only (default).",
    )
    audit_mode.add_argument(
        "--full",
        action="store_true",
        help="Fuller pass including compressed sources, git logs, and diffs.",
    )
    audit_parser.add_argument(
        "--no-logs", action="store_true", help="Omit git logs from a full pass."
    )
    audit_parser.add_argument(
        "--no-diffs", action="store_true", help="Omit git diffs from a full pass."
    )
    audit_parser.add_argument(
        "--log-count",
        type=int,
        default=repomix_mod.DEFAULT_LOG_COUNT,
        help=f"Commits of log to include (default: {repomix_mod.DEFAULT_LOG_COUNT}).",
    )
    audit_parser.add_argument("--json", action="store_true")

    hook_parser = subparsers.add_parser(
        "hook",
        help="Emit agent-facing notices for host hooks (internal; always exits 0).",
    )
    hook_sub = hook_parser.add_subparsers(dest="hook_event")
    session_start = hook_sub.add_parser(
        "session-start",
        help="Report stale or incomplete context when a project is opened.",
    )
    session_start.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    pre_compact = hook_sub.add_parser(
        "pre-compact",
        help="Remind the agent to record what this session learned, before "
        "the context window is compacted away.",
    )
    pre_compact.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    skill_parser = subparsers.add_parser(
        "skill", help="Manage the global skill installation for Claude Code and Codex."
    )
    skill_sub = skill_parser.add_subparsers(dest="skill_command")
    for name, helptext in (
        ("install", "Symlink the canonical skill into both hosts."),
        ("uninstall", "Remove the skill symlinks."),
        ("status", "Report installation state without changing anything."),
    ):
        sub = skill_sub.add_parser(name, help=helptext)
        sub.add_argument("--json", action="store_true")
        sub.add_argument("--home", default=None, help=argparse.SUPPRESS)
        sub.add_argument("--canonical", default=None, help=argparse.SUPPRESS)
        sub.add_argument(
            "--claude",
            dest="hosts",
            action="append_const",
            const="claude",
            help="Act on Claude Code only (default: both hosts).",
        )
        sub.add_argument(
            "--codex",
            dest="hosts",
            action="append_const",
            const="codex",
            help="Act on Codex only (default: both hosts).",
        )
        if name != "status":
            sub.add_argument(
                "--force",
                action="store_true",
                help="Replace unrelated content at a target path (backs it up first).",
            )
            sub.add_argument(
                "--dry-run",
                action="store_true",
                help="Report what would happen and change nothing.",
            )

    return parser


def _emit(payload: Dict[str, Any], text: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(text)


def _resolve_root() -> Path:
    return repository.find_repo_root(Path.cwd())


def cmd_init(args: argparse.Namespace) -> int:
    root = _resolve_root()

    if repository.is_initialized(root):
        payload = {
            "ok": False,
            "reason": "already_initialized",
            "manifest": contract.MANIFEST_PATH,
        }
        _emit(
            payload,
            "Context Maintainer is already initialized here.\n"
            "  → Use `context-maintainer sync` to update context after changes.\n"
            "  → Use `context-maintainer rebuild` for a full re-audit after a major pivot.",
            args.json,
        )
        return 1

    classification = repository.classify(root, mode=args.mode)
    repo = repository.describe_repo(root)
    existing_agent_files = scaffold.detect_existing_agent_files(root)

    result = scaffold.write_contract_files(root, project_name=root.name)

    loaded = manifest_mod.default_manifest(
        mode=classification.mode,
        commit=repo.head_commit,
        repomix_version=repomix_mod.get_repomix_version(),
    )
    loaded.mcp_language_server_configured = mcp_companion.detect(root).configured
    manifest_mod.save_manifest(loaded, root / contract.MANIFEST_PATH)

    payload = {
        "ok": True,
        "mode": classification.mode,
        "mode_overridden": classification.overridden,
        "evidence": classification.evidence,
        "created": result.created,
        "preserved": result.preserved,
        "existing_agent_files": [
            {
                "path": f.relative_path,
                "lines": f.line_count,
                "bytes": f.size_bytes,
            }
            for f in existing_agent_files
        ],
        "head_commit": repo.head_commit,
        "needs_semantic_population": True,
    }

    lines = [
        f"Initialized Context Maintainer ({classification.mode} project).",
        "",
        "Detection evidence:",
    ]
    lines.extend(f"  - {item}" for item in classification.evidence)
    if result.created:
        lines.append("")
        lines.append("Created:")
        lines.extend(f"  + {path}" for path in result.created)
    if result.preserved:
        lines.append("")
        lines.append("Preserved (already existed — not overwritten):")
        lines.extend(f"  = {path}" for path in result.preserved)
    if existing_agent_files:
        lines.append("")
        lines.append("Existing agent instructions found (merge these, do not discard):")
        lines.extend(
            f"  ! {f.relative_path} ({f.line_count} lines)" for f in existing_agent_files
        )
    lines.append("")
    lines.append(
        "Structure is in place, but the context documents still hold placeholders.\n"
        "The context-maintainer skill should now populate them from real evidence."
    )
    _emit(payload, "\n".join(lines), args.json)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = _resolve_root()
    report = briefing.build_status_report(root)
    _emit(report.to_dict(), briefing.render_text(report), args.json)
    return 0


def _require_manifest(root: Path, as_json: bool) -> Optional[manifest_mod.Manifest]:
    path = root / contract.MANIFEST_PATH
    try:
        return manifest_mod.load_manifest(path)
    except manifest_mod.ManifestError as exc:
        _emit(
            {"ok": False, "reason": "manifest_unavailable", "detail": str(exc)},
            f"Cannot continue: {exc}\n  → Run `context-maintainer init` first.",
            as_json,
        )
        return None


def _changed_context_files(root: Path, since: Optional[str]) -> List[str]:
    """Which context documents changed since the old checkpoint.

    Mechanical, so the CLI can supply it; the *reason* for the change is the
    agent's job and arrives via --note.
    """
    if not since or not gitutil.is_git_repo(root):
        return []
    if not gitutil.commit_exists(root, since):
        return []
    owned = {cf.relative_path for cf in contract.CONTRACT_FILES}
    changed = [path for _, path in gitutil.get_changed_files_since(root, since)]
    return sorted(p for p in changed if p in owned)


def _finalize_checkpoint(
    root: Path,
    loaded: manifest_mod.Manifest,
    requested: Any,
    as_json: bool,
    note: Optional[str] = None,
) -> int:
    if not gitutil.is_git_repo(root):
        _emit(
            {"ok": False, "reason": "not_a_git_repo"},
            "Cannot finalize a checkpoint outside a git repository.",
            as_json,
        )
        return 1

    target = gitutil.get_head_commit(root) if requested is True else str(requested)
    if target is None:
        _emit(
            {"ok": False, "reason": "no_commits"},
            "Cannot finalize a checkpoint: this repository has no commits yet.",
            as_json,
        )
        return 1
    if requested is not True and not gitutil.commit_exists(root, target):
        _emit(
            {"ok": False, "reason": "unknown_commit", "commit": target},
            f"Cannot finalize: commit {target} does not exist in this repository.",
            as_json,
        )
        return 1

    # Capture what changed before the checkpoint moves past it.
    updated = _changed_context_files(root, loaded.last_verified_commit)

    manifest_mod.update_checkpoint(loaded, target)
    if any(p.endswith("STATE.md") for p in updated) or note:
        # Confirming intent is what makes STATE trustworthy; record when.
        loaded.state_confirmed_at = manifest_mod.utc_now()
    manifest_mod.save_manifest(loaded, root / contract.MANIFEST_PATH)

    # Regenerate the DECISIONS index before attesting, so the baseline covers
    # the text as it will actually stand. It is derived from the headings, so
    # this is scaffolding rather than writing prose — the CLI/skill boundary
    # holds: nothing here decides what a decision *means*.
    decisionindex.refresh(root / "docs/context/DECISIONS.md")

    # Re-stamp what each document now rests on. Read from the current prose
    # rather than carried forward, so the baseline always describes the claims
    # as they now stand. This clears *staleness* only — a dangling citation or
    # a version contradiction still fails `doctor`, so finalizing can never
    # launder a defect into a clean report.
    drift.record_attestation(root, target, loaded.last_synced_at or manifest_mod.utc_now())
    remaining = drift.analyse(root)

    logged = contextlog.append_entry(root, commit=target, files=updated, note=note)

    payload = {
        "ok": True,
        "last_verified_commit": loaded.last_verified_commit,
        "last_synced_at": loaded.last_synced_at,
        "context_files_updated": updated,
        "logged": str(logged) if logged else None,
        "unresolved_defects": [f.to_dict() for f in remaining.defects],
    }
    lines = [f"Checkpoint advanced to {target[:8]} at {loaded.last_synced_at}."]
    if updated:
        lines.append("Context files updated: " + ", ".join(updated))
    if remaining.defects:
        lines.append(
            f"WARNING: {len(remaining.defects)} unresolved context defect(s) "
            "remain — attesting does not fix them. Run "
            "`context-maintainer review`."
        )
    if logged:
        lines.append(f"Recorded in {contextlog.LOG_RELPATH}.")
    elif not note:
        lines.append(
            "Nothing recorded in the log (no context files changed). Pass "
            "--note to record why a sync happened anyway."
        )
    _emit(payload, "\n".join(lines), as_json)
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    root = _resolve_root()
    loaded = _require_manifest(root, args.json)
    if loaded is None:
        return 1

    if args.finalize is not False:
        return _finalize_checkpoint(
            root, loaded, args.finalize, args.json, note=args.note
        )

    if not gitutil.is_git_repo(root):
        _emit(
            {"ok": True, "changed_files": [], "commits": [], "note": "not a git repository"},
            "Not a git repository — no change evidence available.",
            args.json,
        )
        return 0

    head = gitutil.get_head_commit(root)
    checkpoint = loaded.last_verified_commit
    commits: List[Any] = []
    changed: List[Any] = []
    note = ""

    if head is None:
        note = "repository has no commits yet"
    elif checkpoint is None:
        note = "no checkpoint recorded; treating all history as unreviewed"
        commits = gitutil.get_log(root, 50)
    elif not gitutil.commit_exists(root, checkpoint):
        note = f"checkpoint {checkpoint[:8]} no longer exists (history rewritten?)"
        commits = gitutil.get_log(root, 50)
    elif checkpoint == head:
        note = "checkpoint matches HEAD"
    else:
        commits = gitutil.get_commits_since(root, checkpoint)
        changed = gitutil.get_changed_files_since(root, checkpoint)

    working = gitutil.get_working_tree_changes(root)

    # Drift rides along with the change evidence rather than waiting to be
    # asked for. `sync` is the one command an agent always runs before deciding
    # what to update, and a signal that needs a separate command to discover is
    # a signal that gets skipped.
    drift_report = drift.analyse(root)
    drift_counts = drift.summarise(drift_report.findings)

    payload = {
        "ok": True,
        "checkpoint": checkpoint,
        "head": head,
        "note": note,
        "claims_to_adjudicate": drift_counts,
        "commits": [{"sha": sha, "subject": subject} for sha, subject in commits],
        "changed_files": [{"status": status, "path": path} for status, path in changed],
        "working_tree_changes": [
            {"status": status, "path": path} for status, path in working
        ],
    }

    lines = [
        f"Checkpoint: {checkpoint[:8] if checkpoint else '(none)'}"
        f"   HEAD: {head[:8] if head else '(none)'}"
    ]
    if note:
        lines.append(f"Note: {note}")
    if commits:
        lines.append("")
        lines.append(f"Commits since checkpoint ({len(commits)}):")
        lines.extend(f"  {sha} {subject}" for sha, subject in commits[:20])
        if len(commits) > 20:
            lines.append(f"  … and {len(commits) - 20} more")
    if changed:
        lines.append("")
        lines.append(f"Files changed since checkpoint ({len(changed)}):")
        lines.extend(f"  {status:<4} {path}" for status, path in changed[:40])
        if len(changed) > 40:
            lines.append(f"  … and {len(changed) - 40} more")
    if working:
        lines.append("")
        lines.append(f"Uncommitted working-tree changes ({len(working)}):")
        lines.extend(f"  {status:<3} {path}" for status, path in working[:20])
    actionable = drift_counts[drift.DEFECT] + drift_counts[drift.WARN]
    if actionable:
        lines.append("")
        lines.append(
            f"Claims needing adjudication: {actionable} "
            f"({drift_counts[drift.DEFECT]} defect(s)). "
            "Run `context-maintainer review` — these are claims that may have "
            "stopped being true without any commit contradicting them."
        )

    if not commits and not changed and not working:
        lines.append("")
        lines.append("No changes to review.")
    else:
        lines.append("")
        lines.append(
            "Review these against docs/context/, update only what actually changed,\n"
            "then run `context-maintainer sync --finalize` to advance the checkpoint."
        )
    _emit(payload, "\n".join(lines), args.json)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _resolve_root()
    report = doctor.run_all_checks(root, verify=args.verify)
    _emit(report.to_dict(), doctor.render_text(report), args.json)
    return 1 if report.failed(strict=args.strict) else 0


def cmd_review(args: argparse.Namespace) -> int:
    """The adjudication worklist: which claims need a human or agent ruling.

    Separate from `doctor` on purpose. `doctor` asserts defects; this asks
    questions, and the answer to most of them is "still true". Mixing the two
    would either turn honest uncertainty into build failures or bury real
    defects in a list of things to think about.
    """
    root = _resolve_root()
    report = drift.analyse(root)
    _emit(report.to_dict(), drift.render_text(report), args.json)
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    root = _resolve_root()
    loaded = _require_manifest(root, args.json)
    if loaded is None:
        return 1

    if args.finalize is not False:
        return _finalize_checkpoint(
            root, loaded, args.finalize, args.json, note=args.note
        )

    if not args.prepare:
        _emit(
            {"ok": False, "reason": "no_action"},
            "Specify what to do:\n"
            "  --prepare   back up current context before regenerating it\n"
            "  --finalize  advance the checkpoint once regeneration is done",
            args.json,
        )
        return 1

    backed_up = scaffold.backup_context_documents(root)
    payload = {
        "ok": True,
        "backed_up": backed_up,
        "backup_dir": contract.BACKUP_DIR,
        "preserve_decisions": True,
    }
    lines = [
        f"Backed up {len(backed_up)} context file(s) under {contract.BACKUP_DIR}/.",
    ]
    lines.extend(f"  ~ {path}" for path in backed_up)
    lines.append("")
    lines.append(
        "Now re-audit the repository and regenerate the context documents.\n"
        "Preserve every meaningful decision from DECISIONS.md — mark superseded\n"
        "entries rather than deleting them."
    )
    _emit(payload, "\n".join(lines), args.json)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Gather raw evidence for the skill to read. Writes only to the cache."""
    root = _resolve_root()
    scaffold.ensure_cache_gitignore(root)

    if args.full:
        result = repomix_mod.run_full_pass(
            root,
            include_logs=not args.no_logs,
            log_count=args.log_count,
            include_diffs=not args.no_diffs,
        )
    else:
        result = repomix_mod.run_structure_pass(root)

    companion = mcp_companion.detect(root)
    payload = {
        "ok": True,
        "repomix": result.to_dict(),
        "mcp_language_server": companion.to_dict(),
        "degraded_mode": result.degraded_mode,
    }

    lines = [f"Audit pass: {result.mode}"]
    if result.succeeded:
        lines.append(f"Evidence written to {result.output_path}")
        if result.version:
            lines.append(f"Repomix version: {result.version}")
    else:
        lines.append("DEGRADED MODE — structural evidence is incomplete.")
        if result.note:
            lines.append("")
            lines.append(result.note)
        if result.stderr:
            lines.append("")
            lines.append(f"Repomix stderr: {result.stderr[:800]}")

    lines.append("")
    if companion.configured:
        lines.append(
            "mcp-language-server is configured — use its tools "
            f"({', '.join(mcp_companion.COMPANION_TOOLS)}) to confirm "
            "call-graph and import claims."
        )
    else:
        lines.append(
            "mcp-language-server is not configured (optional); structural "
            "claims rest on Repomix, Git, and direct reading."
        )
    if result.degraded_mode:
        lines.append("")
        lines.append(
            "Do not describe the audit as complete. Record reduced confidence "
            "in ARCHITECTURE.md's 'Evidence Level' section."
        )

    _emit(payload, "\n".join(lines), args.json)
    return 0


#: Keep hook output short: Codex truncates injected context at 2500 chars by
#: default, and a session-start notice competes with everything else for
#: attention.
MAX_HOOK_NOTICE_CHARS = 900


def session_start_notice(root: Path) -> Optional[str]:
    """The notice to inject when a project is opened, or None to stay silent.

    Deliberately silent unless the project has *adopted* Context Maintainer and
    something needs doing. Announcing itself in every unrelated repository
    would be nagging, and a hook that cries wolf gets ignored.
    """
    if not repository.is_initialized(root):
        return None

    report = briefing.build_status_report(root)
    problems = []

    if report.staleness.is_stale:
        problems.append(report.staleness.reason)
    if report.placeholder_files:
        count = len(report.placeholder_files)
        problems.append(
            f"{count} context file{'s' if count != 1 else ''} still contain "
            "unfilled template placeholders"
        )

    # Claim drift is the failure mode a commit count cannot see: nothing may
    # have changed for weeks and the documents can still have stopped being
    # true. Reported here because this is the only moment an agent is told
    # anything without having asked.
    try:
        drift_report = drift.analyse(root)
        needing = len(drift_report.defects) + len(
            [f for f in drift_report.findings if f.kind == drift.STALE_EVIDENCE]
        )
        if needing:
            problems.append(
                f"{needing} documented claim{'s' if needing != 1 else ''} "
                "rest on evidence that has since changed"
            )
    except Exception:
        pass

    if not problems:
        return None

    # Deliberately terse. This competes for attention with everything else at
    # the start of a session, and a wall of text gets skimmed even when true.
    # The goal/architecture summary is left out on purpose: the notice points
    # at the documents rather than trying to replace them.
    notice = (
        "Context Maintainer: this project's recorded context may be out of "
        "date — " + "; ".join(problems) + ". Read docs/context/PROJECT.md and "
        "docs/context/STATE.md before substantial work, run "
        "`context-maintainer review` to see which specific claims need "
        "re-checking, and run the context-maintainer sync workflow if what "
        "they say is no longer true."
    )
    if len(notice) > MAX_HOOK_NOTICE_CHARS:
        notice = notice[: MAX_HOOK_NOTICE_CHARS - 1].rstrip() + "…"
    return notice


#: Source paths whose movement is worth mentioning before compaction. Context
#: documents and the tool's own bookkeeping are excluded: an agent that has
#: just edited `docs/context/` does not need telling that context changed.
_BOOKKEEPING_PREFIXES = ("docs/context/", ".context-maintainer/")


def _substantive(paths) -> int:
    """How many changed paths are project work rather than context bookkeeping."""
    return len(
        [p for p in paths if not any(p.startswith(x) for x in _BOOKKEEPING_PREFIXES)]
    )


def pre_compact_notice(root: Path) -> Optional[str]:
    """The notice to inject just before the context window is compacted.

    Compaction is the failure this project was built for: understanding assembled
    over a long session is about to be summarised away, and whatever nobody wrote
    down is precisely what does not survive. `SessionStart` catches context that
    went stale between sessions; nothing caught the moment a session's own
    knowledge was about to be lost. This does.

    It never writes, and that is not an implementation detail. DEC-004 rejected a
    `post-commit` hook running `sync --finalize` because it "would mark context as
    reviewed when nobody reviewed it, and silently wrong documentation is worse
    than visibly stale documentation". The reasoning binds harder here: the agent
    is mid-task, nothing is settled, and an automatic re-stamp would attest to
    prose no human has seen. This informs; the agent decides.
    """
    if not repository.is_initialized(root) or not gitutil.is_git_repo(root):
        return None

    outstanding = []

    working = [path for _status, path in gitutil.get_working_tree_changes(root)]
    uncommitted = _substantive(working)
    if uncommitted:
        outstanding.append(
            f"{uncommitted} uncommitted file{'s' if uncommitted != 1 else ''}"
        )

    try:
        checkpoint = manifest_mod.load_manifest(
            root / contract.MANIFEST_PATH
        ).last_verified_commit
    except Exception:
        checkpoint = None
    if checkpoint and gitutil.commit_exists(root, checkpoint):
        committed = _substantive(
            path for _status, path in gitutil.get_changed_files_since(root, checkpoint)
        )
        if committed:
            outstanding.append(
                f"{committed} file{'s' if committed != 1 else ''} changed since "
                "the context checkpoint"
            )

    try:
        report = drift.analyse(root)
        needing = len(report.defects) + len(
            [f for f in report.findings if f.kind == drift.STALE_EVIDENCE]
        )
        if needing:
            outstanding.append(
                f"{needing} documented claim{'s' if needing != 1 else ''} resting "
                "on evidence that has since changed"
            )
    except Exception:
        pass

    # Silence is the common case and has to stay that way. A notice that fires
    # on every compaction is a notice that gets skimmed on the one where it
    # mattered — the same reasoning that kept a per-turn `Stop` hook out of
    # DEC-004.
    if not outstanding:
        return None

    notice = (
        "Context Maintainer: this session is about to be compacted, and "
        + "; ".join(outstanding)
        + ". Anything you have learned that is not written down will not "
        "survive. Before continuing, decide whether this work changed project "
        "reality — if it did, run the context-maintainer sync workflow now; if "
        "it did not, say so and carry on. Record any approach you tried and "
        "abandoned in docs/context/DECISIONS.md while you still remember why."
    )
    if len(notice) > MAX_HOOK_NOTICE_CHARS:
        notice = notice[: MAX_HOOK_NOTICE_CHARS - 1].rstrip() + "…"
    return notice

def cmd_hook(args: argparse.Namespace) -> int:
    """Host-hook entry point. Never fails, never writes, never blocks."""
    try:
        builder = {
            "session-start": session_start_notice,
            "pre-compact": pre_compact_notice,
        }.get(args.hook_event)
        if builder is None:
            return 0
        notice = builder(_resolve_root())
        if notice:
            print(notice)
    except Exception:
        # A hook must never disrupt a session, whatever goes wrong.
        pass
    return 0


def cmd_skill(args: argparse.Namespace) -> int:
    """Manage the global skill installation. Never touches project files."""
    if not args.skill_command:
        print(
            "Specify a subcommand:\n"
            "  context-maintainer skill install     symlink into Claude Code and Codex\n"
            "  context-maintainer skill uninstall   remove those symlinks\n"
            "  context-maintainer skill status      report current state"
        )
        return 1

    try:
        if args.skill_command == "status":
            report = installer_mod.status(
                home=args.home, canonical=args.canonical, hosts=args.hosts
            )
            verb = "Status"
        elif args.skill_command == "install":
            report = installer_mod.install(
                home=args.home,
                canonical=args.canonical,
                force=args.force,
                dry_run=args.dry_run,
                hosts=args.hosts,
            )
            verb = "Install"
        else:
            report = installer_mod.uninstall(
                home=args.home,
                canonical=args.canonical,
                force=args.force,
                dry_run=args.dry_run,
                hosts=args.hosts,
            )
            verb = "Uninstall"
    except installer_mod.InstallerError as exc:
        _emit({"ok": False, "error": str(exc)}, f"Error: {exc}", args.json)
        return 1

    _emit(report.to_dict(), installer_mod.render_text(report, verb), args.json)
    return 0 if report.ok else 1


_HANDLERS = {
    "init": cmd_init,
    "status": cmd_status,
    "sync": cmd_sync,
    "review": cmd_review,
    "doctor": cmd_doctor,
    "rebuild": cmd_rebuild,
    "audit": cmd_audit,
    "skill": cmd_skill,
    "hook": cmd_hook,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return _HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
