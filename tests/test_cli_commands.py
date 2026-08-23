import json
import os
from pathlib import Path

import pytest

from context_maintainer import cli, contract, gitutil

from conftest import commit_all, write


@pytest.fixture
def in_repo(monkeypatch):
    """Run CLI commands as if the user's shell were inside a given repository."""

    def _chdir(root: Path):
        monkeypatch.chdir(root)
        return root

    return _chdir


def _run(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out


def _run_json(argv, capsys):
    code, out = _run(argv + ["--json"], capsys)
    return code, json.loads(out)


def test_init_on_blank_repo_creates_contract(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    code, payload = _run_json(["init"], capsys)
    assert code == 0
    assert payload["mode"] == "blank"
    assert len(payload["created"]) == 7
    assert (blank_repo / contract.MANIFEST_PATH).exists()


def test_init_on_existing_repo_reports_existing_mode(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    code, payload = _run_json(["init"], capsys)
    assert code == 0
    assert payload["mode"] == "existing"
    assert payload["needs_semantic_population"] is True


def test_init_refuses_second_run_and_suggests_sync_or_rebuild(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    _run(["init"], capsys)
    code, out = _run(["init"], capsys)
    assert code == 1
    assert "already initialized" in out.lower()
    assert "sync" in out and "rebuild" in out


def test_init_records_head_commit_as_checkpoint(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _, payload = _run_json(["init"], capsys)
    assert payload["head_commit"] == gitutil.get_head_commit(existing_repo)


def test_init_preserves_and_reports_existing_agent_files(existing_repo: Path, in_repo, capsys):
    write(existing_repo, "AGENTS.md", "# House rules\n\nAlways run make test.\n")
    commit_all(existing_repo, "Add agent instructions")
    in_repo(existing_repo)
    code, payload = _run_json(["init"], capsys)
    assert code == 0
    assert "AGENTS.md" in payload["preserved"]
    assert any(f["path"] == "AGENTS.md" for f in payload["existing_agent_files"])
    assert "Always run make test." in (existing_repo / "AGENTS.md").read_text(encoding="utf-8")


def test_init_mode_override_forces_existing_path_on_blank_looking_repo(
    blank_repo: Path, in_repo, capsys
):
    in_repo(blank_repo)
    code, payload = _run_json(["init", "--mode", "existing"], capsys)
    assert code == 0
    assert payload["mode"] == "existing"
    assert payload["mode_overridden"] is True


def test_init_works_in_a_directory_without_git(tmp_path: Path, in_repo, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    write(plain, "app.py", "x = 1\n")
    in_repo(plain)
    code, payload = _run_json(["init"], capsys)
    assert code == 0
    assert payload["head_commit"] is None


def test_init_from_subdirectory_targets_repo_root(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo / "src" / "app")
    code, _ = _run_json(["init"], capsys)
    assert code == 0
    assert (existing_repo / contract.MANIFEST_PATH).exists()


def test_status_does_not_modify_files(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    before = {
        path: path.read_text(encoding="utf-8")
        for path in contract.all_required_paths(existing_repo)
    }
    code, _ = _run(["status"], capsys)
    assert code == 0
    for path, text in before.items():
        assert path.read_text(encoding="utf-8") == text


def test_status_on_uninitialized_repo_suggests_init(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    code, payload = _run_json(["status"], capsys)
    assert code == 0
    assert payload["initialized"] is False


def test_sync_evidence_lists_files_changed_since_checkpoint(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    commit_all(existing_repo, "Add auth service")

    code, payload = _run_json(["sync"], capsys)
    assert code == 0
    paths = [entry["path"] for entry in payload["changed_files"]]
    assert "src/app/auth.py" in paths
    assert len(payload["commits"]) == 1


def test_sync_does_not_include_files_changed_before_checkpoint(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    commit_all(existing_repo, "Add auth service")
    code, payload = _run_json(["sync"], capsys)
    paths = [entry["path"] for entry in payload["changed_files"]]
    assert "src/app/main.py" not in paths


def test_sync_reports_no_changes_when_current(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    code, payload = _run_json(["sync"], capsys)
    assert payload["note"] == "checkpoint matches HEAD"
    assert payload["changed_files"] == []


def test_sync_reports_uncommitted_working_tree_changes(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    write(existing_repo, "src/app/main.py", "def main():\n    return 'edited'\n")
    code, payload = _run_json(["sync"], capsys)
    assert any(
        entry["path"] == "src/app/main.py" for entry in payload["working_tree_changes"]
    )


def test_sync_finalize_updates_manifest_last_verified_commit(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    new_head = commit_all(existing_repo, "Add auth service")

    code, payload = _run_json(["sync", "--finalize"], capsys)
    assert code == 0
    assert payload["last_verified_commit"] == new_head

    _, status = _run_json(["status"], capsys)
    assert status["staleness"]["is_stale"] is False


def test_sync_finalize_accepts_explicit_commit(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    target = gitutil.get_log(existing_repo, 5)[-1][0]
    code, payload = _run_json(["sync", "--finalize", target], capsys)
    assert code == 0
    assert payload["last_verified_commit"] == target


def test_sync_finalize_rejects_unknown_commit(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    code, payload = _run_json(["sync", "--finalize", "0" * 40], capsys)
    assert code == 1
    assert payload["reason"] == "unknown_commit"


def test_sync_without_manifest_fails_clearly(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    code, payload = _run_json(["sync"], capsys)
    assert code == 1
    assert payload["reason"] == "manifest_unavailable"


def test_doctor_exit_code_zero_when_only_warnings(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    _run(["init"], capsys)
    code, payload = _run_json(["doctor"], capsys)
    assert code == 0
    assert payload["overall"] == "WARN"


def test_doctor_strict_exit_code_one_on_warning(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    _run(["init"], capsys)
    code, _ = _run_json(["doctor", "--strict"], capsys)
    assert code == 1


def test_doctor_exit_code_one_when_uninitialized(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    code, payload = _run_json(["doctor"], capsys)
    assert code == 1
    assert payload["overall"] == "FAIL"


def test_doctor_does_not_modify_context_files(blank_repo: Path, in_repo, capsys):
    in_repo(blank_repo)
    _run(["init"], capsys)
    before = (blank_repo / "docs/context/STATE.md").read_text(encoding="utf-8")
    _run(["doctor"], capsys)
    assert (blank_repo / "docs/context/STATE.md").read_text(encoding="utf-8") == before


def test_rebuild_prepare_backs_up_every_context_file(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    code, payload = _run_json(["rebuild", "--prepare"], capsys)
    assert code == 0
    assert len(payload["backed_up"]) == 7
    assert list((existing_repo / contract.BACKUP_DIR).rglob("PROJECT.md"))


def test_rebuild_without_flags_explains_options(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    code, out = _run(["rebuild"], capsys)
    assert code == 1
    assert "--prepare" in out and "--finalize" in out


def test_rebuild_finalize_advances_checkpoint(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    _run(["init"], capsys)
    write(existing_repo, "src/app/new.py", "y = 2\n")
    new_head = commit_all(existing_repo, "Add new module")
    code, payload = _run_json(["rebuild", "--finalize"], capsys)
    assert code == 0
    assert payload["last_verified_commit"] == new_head


def test_no_command_prints_help(capsys):
    code, out = _run([], capsys)
    assert code == 0
    assert "init" in out and "doctor" in out


def test_full_lifecycle_init_sync_doctor_on_existing_repo(existing_repo: Path, in_repo, capsys):
    in_repo(existing_repo)
    assert _run(["init"], capsys)[0] == 0
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    commit_all(existing_repo, "Add auth service")
    assert _run(["sync"], capsys)[0] == 0
    assert _run(["sync", "--finalize"], capsys)[0] == 0
    code, payload = _run_json(["doctor"], capsys)
    assert payload["overall"] != "FAIL"
