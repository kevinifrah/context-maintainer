"""Reusable, hermetic repository fixtures.

No network, no Node, no real Repomix, and never the developer's real home.
"""
from .blank_repo import make_blank_repo
from .existing_repo import ExistingRepoFixture, make_existing_repo_with_stale_doc
from .helpers import cli_json, in_dir, run_cli

__all__ = [
    "make_blank_repo",
    "make_existing_repo_with_stale_doc",
    "ExistingRepoFixture",
    "in_dir",
    "run_cli",
    "cli_json",
]
