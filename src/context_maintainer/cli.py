"""Command-line entry point for Context Maintainer.

This module owns argument parsing and dispatch only. Every subcommand's real
behavior is implemented in a dedicated module (repository, manifest, doctor,
scaffold, briefing, repomix, installer) and wired in as each phase lands.
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-maintainer",
        description="Maintain durable, evidence-based project context for Claude Code and Codex.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

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
        "rebuild", help="Back up and regenerate the context contract from fresh evidence."
    )
    rebuild_parser.add_argument("--prepare", action="store_true")
    rebuild_parser.add_argument(
        "--finalize", nargs="?", const=True, default=False, metavar="COMMIT"
    )
    rebuild_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    print(f"'{args.command}' is not yet implemented.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
