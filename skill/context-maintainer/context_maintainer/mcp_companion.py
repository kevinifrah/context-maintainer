"""Detect the optional `mcp-language-server` MCP companion.

Context Maintainer ships no structural-analysis backend of its own. When the
user has configured `isaacphi/mcp-language-server` in Claude Code or Codex, the
skill can call its tools (definition, references, hover, diagnostics) directly
through the host's own MCP client to confirm call-graph and import claims.

This module only *reports* whether that is configured. It never installs,
launches, or edits any configuration — and its absence is never an error.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

#: The upstream binary name, as it appears in an MCP server `command`.
COMPANION_COMMAND = "mcp-language-server"

#: Tools the companion exposes, for the skill to look for in its own toolset.
COMPANION_TOOLS = (
    "definition",
    "references",
    "diagnostics",
    "hover",
    "rename_symbol",
)

INSTALL_HINT = (
    "Optional: `mcp-language-server` gives compiler-grade symbol and "
    "call-graph answers via real language servers.\n"
    "  go install github.com/isaacphi/mcp-language-server@latest\n"
    "  plus the language server for your stack (gopls, pyright, "
    "typescript-language-server, rust-analyzer, ...)\n"
    "Register it with Claude Code (.mcp.json) or Codex "
    "(`codex mcp add`). One instance binds to one language server.\n"
    "Note: upstream is BSD-3-Clause but has seen no merged commits since "
    "2025-06; verify it still suits you before relying on it."
)


@dataclass
class CompanionStatus:
    configured: bool = False
    locations: List[str] = field(default_factory=list)
    server_names: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "configured": self.configured,
            "locations": self.locations,
            "server_names": self.server_names,
            "tools": list(COMPANION_TOOLS),
        }


def _candidate_config_paths(root: Path, home: Path) -> List[Path]:
    """Config files that may register MCP servers, project scope first."""
    return [
        root / ".mcp.json",
        root / ".codex" / "config.toml",
        home / ".claude.json",
        home / ".codex" / "config.toml",
    ]


def _server_names_from_json(text: str) -> List[str]:
    """Names of any mcpServers entry whose command mentions the companion."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    names: List[str] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            servers = node.get("mcpServers")
            if isinstance(servers, dict):
                for name, config in servers.items():
                    if not isinstance(config, dict):
                        continue
                    blob = json.dumps(config)
                    if COMPANION_COMMAND in blob:
                        names.append(str(name))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(data)
    return names


def detect(root: Path, home: Optional[Path] = None) -> CompanionStatus:
    """Best-effort scan of known MCP config locations.

    TOML is matched textually rather than parsed: `tomllib` only exists on
    Python 3.11+, and this check is informational, so a substring match is a
    fair trade for keeping the CLI stdlib-only on 3.9.
    """
    root = Path(root)
    home = Path(home) if home is not None else Path.home()

    status = CompanionStatus()
    for path in _candidate_config_paths(root, home):
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if COMPANION_COMMAND not in text:
            continue

        status.configured = True
        status.locations.append(str(path))
        if path.suffix == ".json":
            status.server_names.extend(_server_names_from_json(text))

    # De-duplicate while keeping discovery order.
    status.server_names = list(dict.fromkeys(status.server_names))
    return status
