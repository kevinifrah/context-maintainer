"""The SessionStart hook: what makes context maintenance semi-automatic.

Three properties matter more than the message itself, because this runs at the
start of every session in every project the user opens:

1. It never disrupts a session — always exit 0, whatever is broken.
2. It never writes anything.
3. It stays silent unless there is something worth acting on. A hook that
   speaks every time is a hook that gets ignored.
"""
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from context_maintainer import cli, contract

from fixtures import make_blank_repo, make_existing_repo_with_stale_doc, run_cli
from fixtures.helpers import commit, write

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "skill" / "context-maintainer"
HOOKS_JSON = PLUGIN_DIR / "hooks" / "hooks.json"
HOOK_SCRIPT = PLUGIN_DIR / "hooks" / "session-start.sh"


# --- the hooks.json contract ---------------------------------------------


def test_hooks_json_exists_at_the_documented_location():
    """Both hosts look for hooks/hooks.json in the plugin root."""
    assert HOOKS_JSON.is_file()


def test_hooks_json_is_valid_json_with_a_description():
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    assert data["description"]
    assert "hooks" in data


def test_hooks_json_registers_exactly_the_three_intended_events():
    """One of these blocks, and which one is a decision, not an accident.

    DEC-004 kept `Stop` out because it can only inform by blocking the turn, and
    a per-turn prompt whose own default answer is "nothing needed" trains
    agents to dismiss it. DEC-011 adds it under a narrower trigger — a commit
    past the checkpoint, not any edit — which is the enforcement path DEC-004
    explicitly left open. A fourth event appearing here should be argued for in
    DECISIONS.md before it is added.
    """
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    assert set(data["hooks"]) == {"SessionStart", "PreCompact", "Stop"}


def test_hook_command_uses_the_plugin_root_variable():
    """A bare relative path would resolve against the session cwd, not the plugin."""
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    command = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in command
    assert "session-start.sh" in command


def test_hook_declares_a_timeout_so_a_huge_repo_cannot_hang_startup():
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    entry = data["hooks"]["SessionStart"][0]["hooks"][0]
    assert 0 < entry["timeout"] <= 60


def test_hook_script_is_executable():
    assert os.access(HOOK_SCRIPT, os.X_OK)


# --- the notice itself ---------------------------------------------------


def test_silent_when_project_has_not_adopted_context_maintainer(tmp_path: Path):
    """Announcing itself in unrelated repositories would be nagging."""
    repo = make_blank_repo(tmp_path)
    assert cli.session_start_notice(repo) is None


def test_silent_when_context_is_current(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    # Fill placeholders and align the checkpoint: nothing left to report.
    for contract_file in contract.CONTRACT_FILES:
        path = repo / contract_file.relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                contract.PLACEHOLDER_SENTINEL, "documented"
            ),
            encoding="utf-8",
        )
    commit(repo, "Add context")
    run_cli(repo, ["sync", "--finalize"])
    assert cli.session_start_notice(repo) is None


def test_speaks_when_context_is_behind_the_code(tmp_path: Path):
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    notice = cli.session_start_notice(fixture.root)
    assert notice is not None
    assert "out of date" in notice
    assert "commit(s)" in notice


def test_speaks_when_placeholders_remain(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    notice = cli.session_start_notice(repo)
    assert notice is not None
    assert "placeholder" in notice


def test_notice_points_at_the_documents_and_the_workflow(tmp_path: Path):
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    notice = cli.session_start_notice(fixture.root)
    assert "docs/context/PROJECT.md" in notice
    assert "docs/context/STATE.md" in notice
    assert "sync" in notice


def test_notice_stays_short_enough_for_both_hosts(tmp_path: Path):
    """Codex truncates injected context at 2500 chars by default."""
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    notice = cli.session_start_notice(fixture.root)
    assert len(notice) <= cli.MAX_HOOK_NOTICE_CHARS
    assert len(notice) < 2500


def test_notice_is_a_single_paragraph(tmp_path: Path):
    """Multi-line walls of text get skimmed at session start."""
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    assert "\n" not in cli.session_start_notice(fixture.root)


# --- the never-disrupt-a-session contract --------------------------------


def _fingerprint(root: Path) -> dict:
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_hook_writes_nothing(tmp_path: Path):
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    before = _fingerprint(fixture.root)
    run_cli(fixture.root, ["hook", "session-start"])
    assert _fingerprint(fixture.root) == before


def test_hook_command_exits_zero_even_when_uninitialized(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    code, out = run_cli(repo, ["hook", "session-start"])
    assert code == 0
    assert out == ""


def test_hook_command_exits_zero_on_a_corrupt_manifest(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    (repo / contract.MANIFEST_PATH).write_text("{broken", encoding="utf-8")
    code, _ = run_cli(repo, ["hook", "session-start"])
    assert code == 0


def test_hook_command_exits_zero_outside_a_git_repository(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    code, _ = run_cli(plain, ["hook", "session-start"])
    assert code == 0


def test_hook_subcommand_with_no_event_exits_zero(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    code, _ = run_cli(repo, ["hook"])
    assert code == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell required")
def test_hook_script_exits_zero_when_the_launcher_is_missing(tmp_path: Path):
    result = subprocess.run(
        ["sh", str(HOOK_SCRIPT)],
        capture_output=True,
        text=True,
        env={"CLAUDE_PLUGIN_ROOT": str(tmp_path / "nonexistent"), "PATH": "/usr/bin:/bin"},
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell required")
def test_hook_script_exits_zero_with_a_broken_path(tmp_path: Path):
    """A hook must not disrupt a session even in a hostile environment."""
    result = subprocess.run(
        ["/bin/sh", str(HOOK_SCRIPT)],
        capture_output=True,
        text=True,
        env={"PATH": "/nonexistent"},
        cwd=str(tmp_path),
    )
    assert result.returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell required")
def test_hook_script_reports_a_stale_repository_end_to_end(tmp_path: Path):
    """The real path: script -> launcher -> bundled CLI -> notice on stdout."""
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    python_dir = Path(sys.executable).parent
    result = subprocess.run(
        ["sh", str(HOOK_SCRIPT)],
        capture_output=True,
        text=True,
        env={
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN_DIR),
            "PATH": f"/usr/bin:/bin:{python_dir}",
            "HOME": str(tmp_path),
        },
        cwd=str(fixture.root),
    )
    assert result.returncode == 0
    assert "Context Maintainer" in result.stdout
    assert "out of date" in result.stdout
