"""The PreCompact hook: the last chance to write down what a session learned.

Compaction is the failure this project exists for. `SessionStart` catches
context that went stale between sessions; nothing caught the moment a session's
own understanding was about to be summarised away.

The same three properties as the SessionStart hook decide whether this is safe
to run in every project, and one more that matters more here:

1. It never disrupts a session — always exit 0, whatever is broken.
2. It never writes anything. DEC-004 rejected mechanical re-stamping because it
   marks context reviewed when nobody reviewed it; mid-task that is worse, not
   better, because nothing is settled yet.
3. It stays silent unless there is something worth acting on.
4. It does not mistake its own bookkeeping for project work.
"""
import hashlib
import json
import os
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
HOOK_SCRIPT = PLUGIN_DIR / "hooks" / "pre-compact.sh"


def _settled(tmp_path: Path) -> Path:
    """A repository whose context is filled in, committed, and attested."""
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
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
    return repo


# --- the hooks.json contract ---------------------------------------------


def test_pre_compact_is_registered():
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    assert "PreCompact" in data["hooks"]


def test_hook_command_uses_the_plugin_root_variable():
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    command = data["hooks"]["PreCompact"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in command
    assert "pre-compact.sh" in command


def test_hook_declares_a_timeout_so_a_huge_repo_cannot_stall_compaction():
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    entry = data["hooks"]["PreCompact"][0]["hooks"][0]
    assert 0 < entry["timeout"] <= 60


def test_hook_script_is_executable():
    assert os.access(HOOK_SCRIPT, os.X_OK)


# --- the notice itself ---------------------------------------------------


def test_silent_when_project_has_not_adopted_context_maintainer(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    assert cli.pre_compact_notice(repo) is None


def test_silent_when_nothing_is_unrecorded(tmp_path: Path):
    """The common case. A notice at every compaction is a notice nobody reads."""
    assert cli.pre_compact_notice(_settled(tmp_path)) is None


def test_its_own_bookkeeping_does_not_count_as_unrecorded_work(tmp_path: Path):
    """`sync --finalize` leaves .context-maintainer/ dirty. That is not drift."""
    repo = _settled(tmp_path)
    assert (repo / ".context-maintainer" / "log.md").exists()
    assert cli.pre_compact_notice(repo) is None


def test_speaks_when_source_work_is_uncommitted(tmp_path: Path):
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")

    notice = cli.pre_compact_notice(repo)
    assert notice is not None
    assert "uncommitted" in notice


def test_speaks_when_commits_have_outrun_the_checkpoint(tmp_path: Path):
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")
    commit(repo, "Add a parser")

    notice = cli.pre_compact_notice(repo)
    assert notice is not None
    assert "checkpoint" in notice


def test_notice_names_the_sync_workflow_and_the_decisions_log(tmp_path: Path):
    """It has to say what to do; 'context may be stale' is not an instruction."""
    notice = cli.pre_compact_notice(make_existing_repo_with_stale_doc(tmp_path).root)
    assert notice is not None
    assert "sync" in notice
    assert "DECISIONS.md" in notice


def test_notice_stays_short_enough_for_both_hosts(tmp_path: Path):
    notice = cli.pre_compact_notice(make_existing_repo_with_stale_doc(tmp_path).root)
    assert len(notice) <= cli.MAX_HOOK_NOTICE_CHARS
    assert len(notice) < 2500


def test_notice_is_a_single_paragraph(tmp_path: Path):
    notice = cli.pre_compact_notice(make_existing_repo_with_stale_doc(tmp_path).root)
    assert "\n" not in notice


# --- the never-disrupt-a-session contract --------------------------------


def _fingerprint(root: Path) -> dict:
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_hook_writes_nothing(tmp_path: Path):
    """The property DEC-004 turns on: it informs, it never attests."""
    fixture = make_existing_repo_with_stale_doc(tmp_path)
    before = _fingerprint(fixture.root)
    run_cli(fixture.root, ["hook", "pre-compact"])
    assert _fingerprint(fixture.root) == before


def test_hook_command_exits_zero_even_when_uninitialized(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    code, out = run_cli(repo, ["hook", "pre-compact"])
    assert code == 0
    assert out == ""


def test_hook_command_exits_zero_on_a_corrupt_manifest(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    (repo / contract.MANIFEST_PATH).write_text("{broken", encoding="utf-8")
    code, _ = run_cli(repo, ["hook", "pre-compact"])
    assert code == 0


def test_hook_command_exits_zero_outside_a_git_repository(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    code, _ = run_cli(plain, ["hook", "pre-compact"])
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
    result = subprocess.run(
        ["/bin/sh", str(HOOK_SCRIPT)],
        capture_output=True,
        text=True,
        env={"PATH": "/nonexistent"},
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
