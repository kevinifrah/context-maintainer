"""Marketplace publishing and self-contained-plugin guarantees.

Both Claude Code and Codex copy ONLY the plugin subdirectory when installing a
plugin from a marketplace. That single fact drives the repository layout: the
Python package lives inside the plugin directory, because a package outside it
would simply be absent on the user's machine.

These tests protect that property — if someone moves the package back out, a
marketplace install would ship a skill that cannot run, and the failure would
only show up for end users.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from context_maintainer import __version__, pluginspec

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "skill" / "context-maintainer"
CLAUDE_MARKETPLACE = REPO_ROOT / pluginspec.CLAUDE_MARKETPLACE_RELPATH
CODEX_MARKETPLACE = REPO_ROOT / pluginspec.CODEX_MARKETPLACE_RELPATH


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- marketplace manifests ------------------------------------------------


def test_both_marketplace_manifests_exist_at_repo_root():
    assert CLAUDE_MARKETPLACE.is_file()
    assert CODEX_MARKETPLACE.is_file()


def test_claude_marketplace_has_required_schema_fields():
    data = _load(CLAUDE_MARKETPLACE)
    assert data["name"]
    assert data["owner"]["name"]
    assert isinstance(data["plugins"], list) and data["plugins"]
    entry = data["plugins"][0]
    assert entry["name"] == "context-maintainer"
    assert entry["source"] == "./skill/context-maintainer"


def test_codex_marketplace_has_required_schema_fields():
    data = _load(CODEX_MARKETPLACE)
    assert data["name"]
    assert isinstance(data["plugins"], list) and data["plugins"]
    entry = data["plugins"][0]
    assert entry["source"] == {"source": "local", "path": "./skill/context-maintainer"}
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] in ("ON_INSTALL", "ON_USE")
    assert entry["category"]


def test_marketplace_name_differs_from_plugin_name():
    """Avoids the `plugin@marketplace` stutter.

    A marketplace is a container that can hold many plugins (real ones hold
    hundreds, sourced from other repositories), so naming it after its single
    current plugin would both read badly and mislead about its scope.
    """
    for path in (CLAUDE_MARKETPLACE, CODEX_MARKETPLACE):
        data = _load(path)
        assert data["name"] != data["plugins"][0]["name"], path


def test_both_marketplaces_agree_on_the_marketplace_name():
    assert _load(CLAUDE_MARKETPLACE)["name"] == _load(CODEX_MARKETPLACE)["name"]
    assert _load(CLAUDE_MARKETPLACE)["name"] == pluginspec.MARKETPLACE_NAME


def test_marketplace_name_is_a_valid_identifier():
    """Kebab-case-ish: letters, digits, dot, underscore, hyphen; ≤128 chars."""
    import re

    name = pluginspec.MARKETPLACE_NAME
    assert 0 < len(name) <= 128
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name), name


def test_marketplace_name_is_not_reserved():
    """Impersonating an official marketplace is rejected by the validator."""
    reserved = {
        "claude-plugins-official",
        "claude-community",
        "anthropic-plugins",
        "official-claude-plugins",
        "org",
        "org-provisioned",
        "unknown",
    }
    assert pluginspec.MARKETPLACE_NAME.lower() not in reserved


def test_documented_install_string_matches_the_manifests():
    """The README must not tell users to type a name that does not exist."""
    expected = f"{pluginspec.PLUGIN_NAME}@{pluginspec.MARKETPLACE_NAME}"
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    install_doc = (REPO_ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    assert expected in readme
    assert expected in install_doc


def test_marketplace_source_paths_are_relative_and_never_escape_the_repo():
    """`../` is forbidden in a plugin source path."""
    claude_source = _load(CLAUDE_MARKETPLACE)["plugins"][0]["source"]
    codex_source = _load(CODEX_MARKETPLACE)["plugins"][0]["source"]["path"]
    for source in (claude_source, codex_source):
        assert source.startswith("./")
        assert ".." not in source


def test_marketplace_source_paths_point_at_the_real_plugin():
    for source in (
        _load(CLAUDE_MARKETPLACE)["plugins"][0]["source"],
        _load(CODEX_MARKETPLACE)["plugins"][0]["source"]["path"],
    ):
        assert (REPO_ROOT / source / "SKILL.md").is_file()


def test_marketplace_manifests_match_pluginspec():
    assert _load(CLAUDE_MARKETPLACE) == pluginspec.claude_marketplace()
    assert _load(CODEX_MARKETPLACE) == pluginspec.codex_marketplace()


def test_claude_marketplace_version_tracks_the_package():
    assert _load(CLAUDE_MARKETPLACE)["plugins"][0]["version"] == __version__


def test_validate_marketplaces_passes_for_the_shipped_repo():
    assert pluginspec.validate_marketplaces(REPO_ROOT) == []


def test_validate_marketplaces_reports_missing_manifests(tmp_path: Path):
    problems = pluginspec.validate_marketplaces(tmp_path)
    assert any("missing marketplace manifest" in p for p in problems)


# --- the self-contained-plugin guarantee ---------------------------------


def test_python_package_lives_inside_the_plugin_directory():
    """The load-bearing layout fact. Do not move this package out."""
    assert (PLUGIN_DIR / "context_maintainer" / "cli.py").is_file()


def test_no_python_package_outside_the_plugin_directory():
    """A stale copy at src/ would drift and silently win on sys.path."""
    assert not (REPO_ROOT / "src" / "context_maintainer").exists()


def test_plugin_directory_carries_everything_the_skill_needs():
    required = (
        "SKILL.md",
        "references/context-contract.md",
        "references/evidence-policy.md",
        "references/audit-protocol.md",
        "references/sync-policy.md",
        "references/mcp-companion.md",
        "scripts/cm.sh",
        "hooks/hooks.json",
        "hooks/session-start.sh",
        "context_maintainer/cli.py",
        "context_maintainer/templates/PROJECT.md.tmpl",
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
    )
    for relpath in required:
        assert (PLUGIN_DIR / relpath).exists(), relpath


def test_launcher_is_executable():
    assert os.access(PLUGIN_DIR / "scripts" / "cm.sh", os.X_OK)


@pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required")
def test_copied_plugin_runs_with_no_pip_install_and_no_pythonpath(tmp_path: Path):
    """The end-to-end proof of a zero-setup plugin install.

    Copies only the plugin directory — exactly what a marketplace install
    does — then runs it in a scrubbed environment with no console script, no
    PYTHONPATH, and no site-packages install.
    """
    copied = tmp_path / "context-maintainer"
    shutil.copytree(
        PLUGIN_DIR,
        copied,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        symlinks=True,
    )

    python_dir = Path(sys.executable).parent
    env = {
        "HOME": str(tmp_path),
        # Deliberately minimal: only a real python, nothing of ours.
        "PATH": f"/usr/bin:/bin:{python_dir}",
    }
    result = subprocess.run(
        [str(copied / "scripts" / "cm.sh"), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"
    assert __version__ in result.stdout


@pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required")
def test_copied_plugin_can_initialize_a_repository(tmp_path: Path):
    copied = tmp_path / "context-maintainer"
    shutil.copytree(
        PLUGIN_DIR,
        copied,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        symlinks=True,
    )
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(project), check=True)
    (project / "README.md").write_text("# demo\n", encoding="utf-8")

    python_dir = Path(sys.executable).parent
    result = subprocess.run(
        [str(copied / "scripts" / "cm.sh"), "init", "--json"],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": f"/usr/bin:/bin:{python_dir}"},
        cwd=str(project),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert json.loads(result.stdout)["ok"] is True
    assert (project / "docs/context/PROJECT.md").is_file()


def test_launcher_fails_clearly_when_no_interpreter_is_usable(tmp_path: Path):
    """A broken environment must explain itself, not fail cryptically."""
    copied = tmp_path / "context-maintainer"
    shutil.copytree(
        PLUGIN_DIR,
        copied,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        symlinks=True,
    )
    empty_bin = tmp_path / "empty"
    empty_bin.mkdir()
    result = subprocess.run(
        [str(copied / "scripts" / "cm.sh"), "--version"],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": str(empty_bin)},
        cwd=str(tmp_path),
    )
    assert result.returncode == 127
    assert "could not be run" in result.stderr
    assert "pip install -e ." in result.stderr
