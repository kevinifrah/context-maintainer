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
    sync_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor", help="Validate the context contract deterministically."
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument(
        "--strict", action="store_true", help="Treat WARN results as failing."
    )

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


def _finalize_checkpoint(
    root: Path, loaded: manifest_mod.Manifest, requested: Any, as_json: bool
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

    manifest_mod.update_checkpoint(loaded, target)
    manifest_mod.save_manifest(loaded, root / contract.MANIFEST_PATH)
    _emit(
        {
            "ok": True,
            "last_verified_commit": loaded.last_verified_commit,
            "last_synced_at": loaded.last_synced_at,
        },
        f"Checkpoint advanced to {target[:8]} at {loaded.last_synced_at}.",
        as_json,
    )
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    root = _resolve_root()
    loaded = _require_manifest(root, args.json)
    if loaded is None:
        return 1

    if args.finalize is not False:
        return _finalize_checkpoint(root, loaded, args.finalize, args.json)

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

    payload = {
        "ok": True,
        "checkpoint": checkpoint,
        "head": head,
        "note": note,
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
    report = doctor.run_all_checks(root)
    _emit(report.to_dict(), doctor.render_text(report), args.json)
    return 1 if report.failed(strict=args.strict) else 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    root = _resolve_root()
    loaded = _require_manifest(root, args.json)
    if loaded is None:
        return 1

    if args.finalize is not False:
        return _finalize_checkpoint(root, loaded, args.finalize, args.json)

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
    "doctor": cmd_doctor,
    "rebuild": cmd_rebuild,
    "audit": cmd_audit,
    "skill": cmd_skill,
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
