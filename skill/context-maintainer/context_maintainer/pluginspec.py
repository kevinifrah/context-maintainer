"""Expected content of the two plugin manifests, as data.

One canonical skill directory is a valid plugin for both hosts, because each
host only reads its own manifest name. Keeping the expected content here lets
tests assert that what is on disk stays in sync with the package version.

Field sets are not invented: the Claude manifest uses the documented
name/version/description/author fields (only `name` is required), and the Codex
manifest mirrors the fields present in all 180 plugins of the public
`openai/plugins` marketplace.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import __version__

PLUGIN_NAME = "context-maintainer"
DISPLAY_NAME = "Context Maintainer"

#: The marketplace is a container, named after its owner rather than its
#: contents, so `context-maintainer@kevinifrah` reads cleanly and further
#: plugins can be added as cross-repo entries instead of new marketplaces.
#: Marketplace names are unique per user, not globally, and there is no
#: rename-migration mechanism — so this should stay stable.
MARKETPLACE_NAME = "kevinifrah"
MARKETPLACE_DISPLAY_NAME = "Kevin Ifrah"

CLAUDE_MANIFEST_RELPATH = ".claude-plugin/plugin.json"
CODEX_MANIFEST_RELPATH = ".codex-plugin/plugin.json"

#: Marketplace manifests live at the *repository* root, so one repo can both
#: publish the marketplace and contain the plugin.
CLAUDE_MARKETPLACE_RELPATH = ".claude-plugin/marketplace.json"
CODEX_MARKETPLACE_RELPATH = ".agents/plugins/marketplace.json"

#: Where the plugin sits relative to the repository root.
PLUGIN_SOURCE_PATH = "./skill/context-maintainer"

#: Codex's demonstrated layout for a bundled skill (0 of 180 real plugins use a
#: root SKILL.md, so this nesting is the only safe form).
CODEX_SKILLS_DIR = "skills"
CODEX_SKILLS_FIELD = "./skills/"

SHORT_DESCRIPTION = "Durable project context for Claude Code and Codex"

DESCRIPTION = (
    "Create and maintain durable project context in the repository itself so "
    "any coding agent can quickly understand a project."
)

LONG_DESCRIPTION = (
    "Context Maintainer keeps a compact, evidence-based record of a project — "
    "its purpose, architecture, workflows, current state, and decisions — in "
    "version-controlled Markdown under docs/context/. Claude Code and Codex "
    "both read the same files, so understanding survives new sessions, context "
    "compaction, and switching between agents. Supports init, status, sync, "
    "doctor, and rebuild."
)

AUTHOR_NAME = "Context Maintainer Contributors"
LICENSE = "MIT"

KEYWORDS = [
    "context",
    "documentation",
    "onboarding",
    "architecture",
    "agents",
]


def claude_manifest(version: str = __version__) -> Dict[str, Any]:
    """Claude Code plugin manifest. Only `name` is strictly required."""
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": DESCRIPTION,
        "author": {"name": AUTHOR_NAME},
    }


def codex_manifest(version: str = __version__) -> Dict[str, Any]:
    """Codex plugin manifest, mirroring the marketplace's universal field set."""
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": DESCRIPTION,
        "author": {"name": AUTHOR_NAME},
        "license": LICENSE,
        "keywords": list(KEYWORDS),
        "skills": CODEX_SKILLS_FIELD,
        "interface": {
            "displayName": DISPLAY_NAME,
            "shortDescription": SHORT_DESCRIPTION,
            "longDescription": LONG_DESCRIPTION,
            "developerName": AUTHOR_NAME,
            "category": "Developer Tools",
            "capabilities": ["Interactive", "Read", "Write"],
            "defaultPrompt": [
                "Initialize durable project context for this repository",
                "Give me a status briefing on this project",
                "Sync the project context after my recent changes",
            ],
            "screenshots": [],
        },
    }


def claude_marketplace(version: str = __version__) -> Dict[str, Any]:
    """Claude Code marketplace manifest (repo root `.claude-plugin/`).

    Lets a user run `/plugin marketplace add kevinifrah/context-maintainer`
    followed by `/plugin install context-maintainer@kevinifrah`.
    """
    return {
        "name": MARKETPLACE_NAME,
        "owner": {"name": AUTHOR_NAME},
        "description": DESCRIPTION,
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": PLUGIN_SOURCE_PATH,
                "displayName": DISPLAY_NAME,
                "description": DESCRIPTION,
                "version": version,
                "license": LICENSE,
                "keywords": list(KEYWORDS),
                "category": "Developer Tools",
            }
        ],
    }


def codex_marketplace() -> Dict[str, Any]:
    """Codex marketplace manifest (repo root `.agents/plugins/`).

    Field shape mirrors the public `openai/plugins` marketplace, where every
    entry uses a local source path relative to the marketplace root.
    """
    return {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": MARKETPLACE_DISPLAY_NAME},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": PLUGIN_SOURCE_PATH},
                "policy": {
                    "installation": "AVAILABLE",
                    # Nothing to authenticate: the tool is entirely local.
                    "authentication": "ON_USE",
                },
                "category": "Developer Tools",
            }
        ],
    }


def render(manifest: Dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def validate_marketplaces(repo_root: Path, version: str = __version__) -> List[str]:
    """Check both marketplace manifests at the repository root."""
    problems: List[str] = []
    repo_root = Path(repo_root)

    for relpath, expected in (
        (CLAUDE_MARKETPLACE_RELPATH, claude_marketplace(version)),
        (CODEX_MARKETPLACE_RELPATH, codex_marketplace()),
    ):
        path = repo_root / relpath
        if not path.is_file():
            problems.append(f"missing marketplace manifest: {relpath}")
            continue
        try:
            data = _load(path)
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"{relpath} is not valid JSON: {exc}")
            continue
        if data != expected:
            problems.append(f"{relpath} does not match pluginspec")
            continue

        plugin_dir = repo_root / PLUGIN_SOURCE_PATH
        if not (plugin_dir / "SKILL.md").is_file():
            problems.append(
                f"{relpath}: source path {PLUGIN_SOURCE_PATH} has no SKILL.md"
            )
        # Both hosts copy only the plugin directory on install, so the CLI has
        # to be inside it or a plugin install would ship a broken skill.
        if not (plugin_dir / "context_maintainer" / "cli.py").is_file():
            problems.append(
                f"{relpath}: the Python package must live inside "
                f"{PLUGIN_SOURCE_PATH} for plugin installs to work"
            )

    return problems


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(skill_root: Path, version: str = __version__) -> List[str]:
    """Check both manifests on disk. Returns human-readable problems."""
    problems: List[str] = []
    skill_root = Path(skill_root)

    for relpath, expected_builder, required in (
        (CLAUDE_MANIFEST_RELPATH, claude_manifest, ("name",)),
        (
            CODEX_MANIFEST_RELPATH,
            codex_manifest,
            ("name", "version", "description", "author", "interface"),
        ),
    ):
        path = skill_root / relpath
        if not path.is_file():
            problems.append(f"missing manifest: {relpath}")
            continue
        try:
            data = _load(path)
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"{relpath} is not valid JSON: {exc}")
            continue

        for field in required:
            if field not in data:
                problems.append(f"{relpath}: missing required field {field!r}")

        if data.get("name") != PLUGIN_NAME:
            problems.append(
                f"{relpath}: name is {data.get('name')!r}, expected {PLUGIN_NAME!r}"
            )
        if "version" in data and data["version"] != version:
            problems.append(
                f"{relpath}: version {data['version']!r} does not match package "
                f"version {version!r}"
            )
        if relpath == CODEX_MANIFEST_RELPATH:
            interface = data.get("interface") or {}
            for field in (
                "displayName",
                "shortDescription",
                "longDescription",
                "developerName",
                "category",
                "capabilities",
                "defaultPrompt",
            ):
                if field not in interface:
                    problems.append(f"{relpath}: interface missing {field!r}")

    return problems
