"""Install the canonical skill into Claude Code and Codex by symlink.

One source of truth: both hosts point at the same directory in this checkout,
so editing the skill updates both immediately and there is never a stale copy.

Safety rules, in order of importance:
1. Never delete or overwrite something that is not ours without `--force`.
2. Always back up before replacing real content.
3. `--dry-run` changes nothing at all.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

CANONICAL_SKILL_DIRNAME = "context-maintainer"

#: Personal skill directories, verified against each host's documentation.
HOST_SKILL_DIRS = (
    ("claude", ".claude/skills"),
    ("codex", ".agents/skills"),
)

# Conflict classifications.
ABSENT = "absent"
CORRECT_SYMLINK = "correct_symlink"
WRONG_SYMLINK = "wrong_symlink"
BROKEN_SYMLINK = "broken_symlink"
REAL_DIRECTORY = "real_directory"
REAL_FILE = "real_file"

# Actions an install/uninstall can take.
CREATED = "created"
ALREADY_INSTALLED = "already_installed"
REPAIRED = "repaired"
REPLACED = "replaced"
REMOVED = "removed"
REMOVED_BROKEN = "removed_broken"
NOT_INSTALLED = "not_installed"
CONFLICT = "conflict"
WOULD_CREATE = "would_create"
WOULD_REPAIR = "would_repair"
WOULD_REPLACE = "would_replace"
WOULD_REMOVE = "would_remove"

_BLOCKED_ACTIONS = frozenset({CONFLICT})


class InstallerError(Exception):
    """The canonical skill source could not be located."""


@dataclass
class Target:
    host: str
    path: Path


@dataclass
class ConflictInfo:
    kind: str
    detail: str = ""

    @property
    def is_ours(self) -> bool:
        return self.kind in (CORRECT_SYMLINK, ABSENT)

    @property
    def needs_force(self) -> bool:
        return self.kind in (WRONG_SYMLINK, REAL_DIRECTORY, REAL_FILE)


@dataclass
class Action:
    host: str
    path: str
    action: str
    detail: str = ""
    backup: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "path": self.path,
            "action": self.action,
            "detail": self.detail,
            "backup": self.backup,
        }


@dataclass
class Report:
    canonical: str = ""
    dry_run: bool = False
    actions: List[Action] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(a.action in _BLOCKED_ACTIONS for a in self.actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "canonical": self.canonical,
            "dry_run": self.dry_run,
            "actions": [a.to_dict() for a in self.actions],
        }


def find_canonical_skill_source(start: Optional[Path] = None) -> Path:
    """Locate `skill/context-maintainer/` in this checkout.

    The git checkout is canonical on purpose: symlinking into a pip
    site-packages path would break on every upgrade.
    """
    origin = Path(start) if start else Path(__file__).resolve()
    for candidate in [origin, *origin.parents]:
        skill = candidate / "skill" / CANONICAL_SKILL_DIRNAME
        if (skill / "SKILL.md").is_file():
            return skill.resolve()
    raise InstallerError(
        "Could not find skill/context-maintainer/SKILL.md. Run the installer "
        "from a Context Maintainer git checkout — the checkout is the canonical "
        "source, so symlinks keep working across upgrades."
    )


def target_paths(home: Path, hosts: Optional[Sequence[str]] = None) -> List[Target]:
    """Install targets, optionally narrowed to specific hosts.

    Installing for one host only is a first-class case: plenty of people use
    just Claude Code or just Codex.
    """
    home = Path(home)
    selected = set(hosts) if hosts else None
    if selected:
        known = {host for host, _ in HOST_SKILL_DIRS}
        unknown = selected - known
        if unknown:
            raise InstallerError(
                f"Unknown host(s): {', '.join(sorted(unknown))}. "
                f"Choose from: {', '.join(sorted(known))}."
            )
    return [
        Target(host=host, path=home / reldir / CANONICAL_SKILL_DIRNAME)
        for host, reldir in HOST_SKILL_DIRS
        if selected is None or host in selected
    ]


def detect_conflict(path: Path, canonical: Path) -> ConflictInfo:
    path = Path(path)
    if path.is_symlink():
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            return ConflictInfo(
                BROKEN_SYMLINK, f"dangling symlink -> {_readlink(path)}"
            )
        if resolved == Path(canonical).resolve():
            return ConflictInfo(CORRECT_SYMLINK, f"-> {resolved}")
        return ConflictInfo(WRONG_SYMLINK, f"-> {resolved}")
    if not path.exists():
        return ConflictInfo(ABSENT)
    if path.is_dir():
        entries = sorted(p.name for p in path.iterdir())
        return ConflictInfo(
            REAL_DIRECTORY,
            f"real directory containing {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
        )
    return ConflictInfo(REAL_FILE, "real file")


def _readlink(path: Path) -> str:
    try:
        import os

        return os.readlink(str(path))
    except OSError:  # pragma: no cover - defensive
        return "?"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_conflicting_target(path: Path) -> Path:
    """Move existing content aside rather than destroying it."""
    path = Path(path)
    destination = path.with_name(f"{path.name}.cm-backup-{_timestamp()}")
    shutil.move(str(path), str(destination))
    return destination


def install(
    home: Optional[Path] = None,
    canonical: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
    hosts: Optional[Sequence[str]] = None,
) -> Report:
    home = Path(home) if home is not None else Path.home()
    canonical_path = (
        Path(canonical).resolve() if canonical else find_canonical_skill_source()
    )
    report = Report(canonical=str(canonical_path), dry_run=dry_run)

    for target in target_paths(home, hosts):
        conflict = detect_conflict(target.path, canonical_path)

        if conflict.kind == CORRECT_SYMLINK:
            report.actions.append(
                Action(target.host, str(target.path), ALREADY_INSTALLED, conflict.detail)
            )
            continue

        if conflict.kind == ABSENT:
            action = WOULD_CREATE if dry_run else CREATED
            if not dry_run:
                target.path.parent.mkdir(parents=True, exist_ok=True)
                target.path.symlink_to(canonical_path, target_is_directory=True)
            report.actions.append(Action(target.host, str(target.path), action))
            continue

        if conflict.kind == BROKEN_SYMLINK:
            action = WOULD_REPAIR if dry_run else REPAIRED
            if not dry_run:
                target.path.unlink()
                target.path.parent.mkdir(parents=True, exist_ok=True)
                target.path.symlink_to(canonical_path, target_is_directory=True)
            report.actions.append(
                Action(target.host, str(target.path), action, conflict.detail)
            )
            continue

        # Something real and not ours is in the way.
        if not force:
            report.actions.append(
                Action(
                    target.host,
                    str(target.path),
                    CONFLICT,
                    f"{conflict.kind}: {conflict.detail}. Re-run with --force to "
                    "back it up and replace it.",
                )
            )
            continue

        if dry_run:
            report.actions.append(
                Action(
                    target.host,
                    str(target.path),
                    WOULD_REPLACE,
                    f"{conflict.kind}: {conflict.detail}",
                )
            )
            continue

        backup = None
        if conflict.kind in (REAL_DIRECTORY, REAL_FILE):
            backup = str(backup_conflicting_target(target.path))
        else:  # a symlink has no content worth preserving
            target.path.unlink()
        target.path.parent.mkdir(parents=True, exist_ok=True)
        target.path.symlink_to(canonical_path, target_is_directory=True)
        report.actions.append(
            Action(
                target.host,
                str(target.path),
                REPLACED,
                f"{conflict.kind}: {conflict.detail}",
                backup=backup,
            )
        )

    return report


def uninstall(
    home: Optional[Path] = None,
    canonical: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
    hosts: Optional[Sequence[str]] = None,
) -> Report:
    home = Path(home) if home is not None else Path.home()
    try:
        canonical_path = (
            Path(canonical).resolve() if canonical else find_canonical_skill_source()
        )
    except InstallerError:
        # Uninstalling should still work from outside a checkout.
        canonical_path = Path("/nonexistent-canonical")
    report = Report(canonical=str(canonical_path), dry_run=dry_run)

    for target in target_paths(home, hosts):
        conflict = detect_conflict(target.path, canonical_path)

        if conflict.kind == ABSENT:
            report.actions.append(
                Action(target.host, str(target.path), NOT_INSTALLED)
            )
            continue

        if conflict.kind == CORRECT_SYMLINK:
            action = WOULD_REMOVE if dry_run else REMOVED
            if not dry_run:
                target.path.unlink()
            report.actions.append(Action(target.host, str(target.path), action))
            continue

        if conflict.kind == BROKEN_SYMLINK:
            action = WOULD_REMOVE if dry_run else REMOVED_BROKEN
            if not dry_run:
                target.path.unlink()
            report.actions.append(
                Action(target.host, str(target.path), action, conflict.detail)
            )
            continue

        if not force:
            report.actions.append(
                Action(
                    target.host,
                    str(target.path),
                    CONFLICT,
                    f"{conflict.kind}: {conflict.detail}. This is not our "
                    "symlink; refusing to remove it without --force.",
                )
            )
            continue

        if dry_run:
            report.actions.append(
                Action(
                    target.host,
                    str(target.path),
                    WOULD_REMOVE,
                    f"{conflict.kind}: {conflict.detail}",
                )
            )
            continue

        backup = None
        if conflict.kind in (REAL_DIRECTORY, REAL_FILE):
            backup = str(backup_conflicting_target(target.path))
        else:
            target.path.unlink()
        report.actions.append(
            Action(
                target.host,
                str(target.path),
                REMOVED,
                f"{conflict.kind}: {conflict.detail}",
                backup=backup,
            )
        )

    return report


def status(
    home: Optional[Path] = None,
    canonical: Optional[Path] = None,
    hosts: Optional[Sequence[str]] = None,
) -> Report:
    """Report installation state without touching anything."""
    home = Path(home) if home is not None else Path.home()
    try:
        canonical_path = (
            Path(canonical).resolve() if canonical else find_canonical_skill_source()
        )
    except InstallerError:
        canonical_path = Path("/nonexistent-canonical")
    report = Report(canonical=str(canonical_path), dry_run=True)
    for target in target_paths(home, hosts):
        conflict = detect_conflict(target.path, canonical_path)
        report.actions.append(
            Action(target.host, str(target.path), conflict.kind, conflict.detail)
        )
    return report


def render_text(report: Report, verb: str) -> str:
    lines = [f"Canonical skill: {report.canonical}"]
    if report.dry_run:
        lines.append("(dry run — nothing was changed)")
    lines.append("")
    for action in report.actions:
        marker = "!" if action.action in _BLOCKED_ACTIONS else "-"
        lines.append(f"{marker} {action.host:<7} {action.action:<18} {action.path}")
        if action.detail:
            lines.append(f"          {action.detail}")
        if action.backup:
            lines.append(f"          backed up to: {action.backup}")
    lines.append("")
    if report.ok:
        lines.append(f"{verb} completed.")
    else:
        lines.append(
            f"{verb} incomplete — resolve the conflicts above, or re-run with --force."
        )
    return "\n".join(lines)


# --- bootstrap entry points (usable straight from a bare clone) ------------


def _build_bootstrap_parser(action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"context-maintainer-{action}",
        description=f"{action.capitalize()} the context-maintainer skill for "
        "Claude Code and Codex.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace unrelated content at a target path (backs it up first).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen and change nothing.",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Override the home directory (for testing).",
    )
    parser.add_argument(
        "--canonical",
        default=None,
        help="Override the canonical skill directory (for testing).",
    )
    parser.add_argument(
        "--claude",
        dest="hosts",
        action="append_const",
        const="claude",
        help="Act on Claude Code only (default: both hosts).",
    )
    parser.add_argument(
        "--codex",
        dest="hosts",
        action="append_const",
        const="codex",
        help="Act on Codex only (default: both hosts).",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _run_bootstrap(action: str, argv: Optional[Sequence[str]]) -> int:
    import json as json_mod

    args = _build_bootstrap_parser(action).parse_args(argv)
    runner = install if action == "install" else uninstall
    try:
        report = runner(
            home=args.home,
            canonical=args.canonical,
            force=args.force,
            dry_run=args.dry_run,
            hosts=args.hosts,
        )
    except InstallerError as exc:
        if args.json:
            print(json_mod.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json_mod.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report, action.capitalize()))
    return 0 if report.ok else 1


def main_install(argv: Optional[Sequence[str]] = None) -> int:
    return _run_bootstrap("install", argv)


def main_uninstall(argv: Optional[Sequence[str]] = None) -> int:
    return _run_bootstrap("uninstall", argv)
