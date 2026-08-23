import json
from pathlib import Path

from context_maintainer import mcp_companion

from conftest import write

CLAUDE_CONFIG = {
    "mcpServers": {
        "language-server": {
            "command": "mcp-language-server",
            "args": ["--workspace", "/tmp/project", "--lsp", "gopls"],
        }
    }
}

UNRELATED_CONFIG = {
    "mcpServers": {"something-else": {"command": "other-server", "args": []}}
}


def test_detect_returns_not_configured_on_clean_repo(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    status = mcp_companion.detect(root, home=home)
    assert not status.configured
    assert status.locations == []


def test_detect_finds_project_level_mcp_json(tmp_path: Path):
    root = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    write(root, ".mcp.json", json.dumps(CLAUDE_CONFIG))
    status = mcp_companion.detect(root, home=home)
    assert status.configured
    assert status.server_names == ["language-server"]
    assert any(".mcp.json" in loc for loc in status.locations)


def test_detect_finds_home_level_claude_json(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    write(home, ".claude.json", json.dumps(CLAUDE_CONFIG))
    status = mcp_companion.detect(root, home=home)
    assert status.configured


def test_detect_finds_companion_nested_under_project_keys(tmp_path: Path):
    """Claude Code nests per-project config; detection must still find it."""
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    nested = {"projects": {"/some/path": CLAUDE_CONFIG}}
    write(home, ".claude.json", json.dumps(nested))
    status = mcp_companion.detect(root, home=home)
    assert status.configured
    assert status.server_names == ["language-server"]


def test_detect_finds_codex_toml_config(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    write(
        home,
        ".codex/config.toml",
        '[mcp_servers.language-server]\n'
        'command = "mcp-language-server"\n'
        'args = ["--workspace", "/tmp", "--lsp", "pyright-langserver", "--", "--stdio"]\n',
    )
    status = mcp_companion.detect(root, home=home)
    assert status.configured
    assert any("config.toml" in loc for loc in status.locations)


def test_detect_ignores_unrelated_mcp_servers(tmp_path: Path):
    root = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    write(root, ".mcp.json", json.dumps(UNRELATED_CONFIG))
    status = mcp_companion.detect(root, home=home)
    assert not status.configured


def test_detect_survives_malformed_json(tmp_path: Path):
    root = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    write(root, ".mcp.json", "{ this is not json")
    status = mcp_companion.detect(root, home=home)
    # No crash; substring absent so nothing detected.
    assert not status.configured


def test_detect_reports_configured_for_malformed_json_mentioning_companion(tmp_path: Path):
    root = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    write(root, ".mcp.json", '{ "mcpServers": { broken "mcp-language-server" ')
    status = mcp_companion.detect(root, home=home)
    assert status.configured
    assert status.server_names == []


def test_detect_finds_multiple_locations(tmp_path: Path):
    root = tmp_path / "repo"
    home = tmp_path / "home"
    write(root, ".mcp.json", json.dumps(CLAUDE_CONFIG))
    write(home, ".codex/config.toml", 'command = "mcp-language-server"\n')
    status = mcp_companion.detect(root, home=home)
    assert len(status.locations) == 2


def test_to_dict_lists_expected_tools(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    payload = mcp_companion.detect(root, home=tmp_path).to_dict()
    assert "definition" in payload["tools"]
    assert "references" in payload["tools"]


def test_install_hint_discloses_maintenance_caveat():
    assert "2025-06" in mcp_companion.INSTALL_HINT
