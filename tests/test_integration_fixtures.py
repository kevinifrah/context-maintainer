"""End-to-end lifecycle tests against realistic repositories.

These drive the real CLI, in order, the way a user (or the skill) would.
"""
import hashlib
from pathlib import Path

import pytest

from context_maintainer import contract, gitutil, repository

from fixtures import (
    ExistingRepoFixture,
    cli_json,
    make_blank_repo,
    make_existing_repo_with_stale_doc,
    run_cli,
)
from fixtures.helpers import commit, write

from test_repomix import fake_repomix, no_repomix  # noqa: F401  (fixtures)


@pytest.fixture
def blank(tmp_path: Path) -> Path:
    return make_blank_repo(tmp_path)


@pytest.fixture
def existing(tmp_path: Path) -> ExistingRepoFixture:
    return make_existing_repo_with_stale_doc(tmp_path)


def _fingerprint(root: Path) -> dict:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in contract.all_required_paths(root)
        if path.exists()
    }


# --- classification -------------------------------------------------------


def test_blank_fixture_is_classified_blank(blank: Path):
    assert repository.classify(blank).mode == repository.MODE_BLANK


def test_existing_fixture_is_classified_existing(existing: ExistingRepoFixture):
    result = repository.classify(existing.root)
    assert result.mode == repository.MODE_EXISTING
    assert any("pyproject.toml" in item for item in result.evidence)


# --- blank lifecycle ------------------------------------------------------


def test_init_on_blank_fixture_creates_full_contract_and_doctor_does_not_fail(
    blank: Path, fake_repomix  # noqa: F811
):
    code, payload = cli_json(blank, ["init"])
    assert code == 0
    assert payload["mode"] == "blank"
    for contract_file in contract.CONTRACT_FILES:
        assert (blank / contract_file.relative_path).is_file()

    code, doctor_payload = cli_json(blank, ["doctor"])
    assert doctor_payload["overall"] != "FAIL"


def test_init_on_blank_fixture_refused_second_time_pointing_to_sync_or_rebuild(
    blank: Path,
):
    run_cli(blank, ["init"])
    code, out = run_cli(blank, ["init"])
    assert code == 1
    assert "sync" in out and "rebuild" in out


def test_blank_init_leaves_placeholders_for_the_skill_to_fill(blank: Path):
    cli_json(blank, ["init"])
    _, status = cli_json(blank, ["status"])
    assert status["placeholder_files"], "a blank init must not pretend to be complete"
    assert status["goal"] is None


# --- the stale-documentation scenario ------------------------------------


def test_fixture_documentation_contradicts_reality_as_designed(
    existing: ExistingRepoFixture,
):
    """Guards the fixture itself: the contradiction must actually be present."""
    workflows = existing.stale_workflows_path.read_text(encoding="utf-8")
    ci = (existing.root / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert existing.stale_test_command in workflows
    assert existing.confirmed_test_command in ci
    assert "unittest" not in ci
    assert "unittest" in existing.stale_readme_path.read_text(encoding="utf-8")


def test_current_evidence_for_the_test_command_is_reachable_from_sync(
    existing: ExistingRepoFixture,
):
    """The evidence that overrides the stale docs shows up as changed files."""
    _, payload = cli_json(existing.root, ["sync"])
    changed = {entry["path"] for entry in payload["changed_files"]}
    assert ".github/workflows/ci.yml" in changed
    assert "tests/test_main.py" in changed


# --- existing-project lifecycle ------------------------------------------


def test_doctor_on_existing_fixture_reports_checkpoint_behind_head(
    existing: ExistingRepoFixture,
):
    _, payload = cli_json(existing.root, ["doctor"])
    freshness = next(
        r for r in payload["results"] if r["name"] == "checkpoint_freshness"
    )
    assert "behind HEAD" in freshness["message"]
    assert "2 commit(s)" in freshness["message"]


def test_status_on_existing_fixture_reports_stale_before_sync_and_current_after(
    existing: ExistingRepoFixture,
):
    _, before = cli_json(existing.root, ["status"])
    assert before["staleness"]["is_stale"] is True
    assert before["staleness"]["commits_behind"] == 2

    run_cli(existing.root, ["sync", "--finalize"])

    _, after = cli_json(existing.root, ["status"])
    assert after["staleness"]["is_stale"] is False


def test_sync_evidence_lists_auth_py_and_pytest_files_as_changed(
    existing: ExistingRepoFixture,
):
    _, payload = cli_json(existing.root, ["sync"])
    changed = {entry["path"] for entry in payload["changed_files"]}
    assert "src/app/auth.py" in changed
    assert "pyproject.toml" in changed
    assert len(payload["commits"]) == 2


def test_sync_evidence_does_not_include_files_changed_before_checkpoint(
    existing: ExistingRepoFixture,
):
    _, payload = cli_json(existing.root, ["sync"])
    changed = {entry["path"] for entry in payload["changed_files"]}
    # Added in the very first commit, long before the checkpoint.
    assert "README.md" not in changed
    assert ".env.example" not in changed


def test_sync_finalize_advances_manifest_checkpoint_to_head(
    existing: ExistingRepoFixture,
):
    _, payload = cli_json(existing.root, ["sync", "--finalize"])
    assert payload["last_verified_commit"] == existing.head_commit

    _, after = cli_json(existing.root, ["sync"])
    assert after["note"] == "checkpoint matches HEAD"
    assert after["changed_files"] == []


def test_sync_does_not_modify_context_documents(existing: ExistingRepoFixture):
    """The CLI half of sync gathers evidence; only the skill edits prose."""
    before = _fingerprint(existing.root)
    run_cli(existing.root, ["sync"])
    assert _fingerprint(existing.root) == before


def test_status_and_doctor_do_not_modify_context_documents(
    existing: ExistingRepoFixture,
):
    before = _fingerprint(existing.root)
    run_cli(existing.root, ["status"])
    run_cli(existing.root, ["doctor"])
    assert _fingerprint(existing.root) == before


def test_init_on_already_initialized_existing_fixture_is_refused(
    existing: ExistingRepoFixture,
):
    code, payload = cli_json(existing.root, ["init"])
    assert code == 1
    assert payload["reason"] == "already_initialized"
    # The hand-written workflows file must survive a refused init untouched.
    assert existing.stale_test_command in existing.stale_workflows_path.read_text(
        encoding="utf-8"
    )


# --- rebuild --------------------------------------------------------------


def test_rebuild_prepare_backs_up_the_stale_workflows_md_before_regeneration(
    existing: ExistingRepoFixture,
):
    code, payload = cli_json(existing.root, ["rebuild", "--prepare"])
    assert code == 0
    assert "docs/context/WORKFLOWS.md" in payload["backed_up"]

    backups = list((existing.root / contract.BACKUP_DIR).rglob("WORKFLOWS.md"))
    assert backups
    assert existing.stale_test_command in backups[0].read_text(encoding="utf-8")


def test_rebuild_prepare_leaves_the_live_documents_in_place(
    existing: ExistingRepoFixture,
):
    """Backing up is not the same as clearing; the skill rewrites in place."""
    run_cli(existing.root, ["rebuild", "--prepare"])
    assert existing.stale_workflows_path.is_file()


def test_rebuild_finalize_advances_checkpoint(existing: ExistingRepoFixture):
    _, payload = cli_json(existing.root, ["rebuild", "--finalize"])
    assert payload["last_verified_commit"] == existing.head_commit


# --- audit ----------------------------------------------------------------


def test_audit_on_existing_fixture_produces_cache_evidence_without_touching_contract_files(
    existing: ExistingRepoFixture, fake_repomix  # noqa: F811
):
    before = _fingerprint(existing.root)
    code, payload = cli_json(existing.root, ["audit", "--full"])
    assert code == 0
    assert payload["repomix"]["succeeded"] is True
    assert Path(payload["repomix"]["output_path"]).is_file()
    assert _fingerprint(existing.root) == before


def test_audit_cache_is_ignored_by_git(
    existing: ExistingRepoFixture, fake_repomix  # noqa: F811
):
    run_cli(existing.root, ["audit"])
    tracked = gitutil.get_tracked_files(existing.root)
    assert not any(path.startswith(".context-maintainer/cache/repomix") for path in tracked)
    working = gitutil.get_working_tree_changes(existing.root)
    assert not any("cache/repomix" in path for _, path in working)


def test_audit_degrades_honestly_without_repomix(
    existing: ExistingRepoFixture, no_repomix  # noqa: F811
):
    code, payload = cli_json(existing.root, ["audit", "--full"])
    assert code == 0
    assert payload["degraded_mode"] is True


# --- existing agent instructions -----------------------------------------


def test_existing_agent_instructions_survive_init(blank: Path):
    write(blank, "AGENTS.md", "# House rules\n\nAlways run `make check` first.\n")
    commit(blank, "Add house rules for agents")

    code, payload = cli_json(blank, ["init"])
    assert code == 0
    assert "AGENTS.md" in payload["preserved"]
    assert any(f["path"] == "AGENTS.md" for f in payload["existing_agent_files"])
    assert "make check" in (blank / "AGENTS.md").read_text(encoding="utf-8")


def test_nested_agent_files_are_reported_for_migration(blank: Path):
    write(blank, "services/api/AGENTS.md", "API-specific rules.\n")
    write(blank, ".cursorrules", "Cursor rules.\n")
    commit(blank, "Add nested and editor rules")

    _, payload = cli_json(blank, ["init"])
    reported = {f["path"] for f in payload["existing_agent_files"]}
    assert "services/api/AGENTS.md" in reported
    assert ".cursorrules" in reported


# --- full lifecycle -------------------------------------------------------


def test_full_lifecycle_init_then_change_then_sync_then_doctor(
    blank: Path, fake_repomix  # noqa: F811
):
    assert run_cli(blank, ["init"])[0] == 0
    commit(blank, "Commit generated context")

    write(blank, "src/service.py", "def handler():\n    return 200\n")
    commit(blank, "Add a real module")

    code, sync_payload = cli_json(blank, ["sync"])
    assert code == 0
    assert any(
        entry["path"] == "src/service.py" for entry in sync_payload["changed_files"]
    )

    assert run_cli(blank, ["sync", "--finalize"])[0] == 0
    _, status = cli_json(blank, ["status"])
    assert status["staleness"]["is_stale"] is False

    _, doctor_payload = cli_json(blank, ["doctor"])
    assert doctor_payload["overall"] != "FAIL"


def test_lifecycle_from_a_subdirectory_targets_the_repository_root(
    existing: ExistingRepoFixture,
):
    nested = existing.root / "src" / "app"
    _, payload = cli_json(nested, ["status"])
    assert payload["root"] == str(existing.root.resolve())
    assert payload["initialized"] is True
