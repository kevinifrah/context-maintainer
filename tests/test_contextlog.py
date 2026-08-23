"""The context update log: small, capped, and honest about doing nothing.

`STATE.md` is a snapshot and forbidden from becoming a diary, `DECISIONS.md`
holds only decisions, and Git buries context syncs among every other commit.
This log fills that gap — but the whole point is that it stays small, so the
cap and the "record nothing when nothing happened" behaviour matter more than
the formatting.
"""
from pathlib import Path

from context_maintainer import contextlog, contract

from fixtures import cli_json, make_blank_repo, run_cli
from fixtures.helpers import commit, write


def test_no_log_file_before_anything_is_recorded(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    assert contextlog.read_recent(repo) == []
    assert contextlog.entry_count(repo) == 0


def test_append_entry_creates_the_log(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    path = contextlog.append_entry(
        repo, commit="a" * 40, files=["docs/context/STATE.md"], note="Recorded phase."
    )
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "docs/context/STATE.md" in text
    assert "Recorded phase." in text
    assert "aaaaaaaa" in text  # short commit


def test_records_nothing_when_nothing_changed_and_no_note(tmp_path: Path):
    """A routine no-op sync should leave no trace at all."""
    repo = make_blank_repo(tmp_path)
    assert contextlog.append_entry(repo, commit="a" * 40, files=[]) is None
    assert not contextlog.log_path(repo).exists()


def test_a_note_alone_is_worth_recording(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    path = contextlog.append_entry(
        repo, commit="a" * 40, files=[], note="Reviewed; nothing needed updating."
    )
    assert path is not None
    assert "nothing needed updating" in path.read_text(encoding="utf-8")


def test_newest_entry_comes_first(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    contextlog.append_entry(repo, "a" * 40, ["docs/context/STATE.md"], "First.")
    contextlog.append_entry(repo, "b" * 40, ["docs/context/STATE.md"], "Second.")
    text = contextlog.log_path(repo).read_text(encoding="utf-8")
    assert text.index("Second.") < text.index("First.")


def test_log_is_capped_and_prunes_the_oldest(tmp_path: Path):
    """The cap is the feature: this must never become a sprawling changelog."""
    repo = make_blank_repo(tmp_path)
    for index in range(contextlog.MAX_ENTRIES + 8):
        contextlog.append_entry(
            repo, f"{index:040d}", ["docs/context/STATE.md"], f"Entry {index}."
        )
    assert contextlog.entry_count(repo) == contextlog.MAX_ENTRIES
    text = contextlog.log_path(repo).read_text(encoding="utf-8")
    assert "Entry 0." not in text
    assert f"Entry {contextlog.MAX_ENTRIES + 7}." in text


def test_capped_log_stays_small_on_disk(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    for index in range(contextlog.MAX_ENTRIES + 5):
        contextlog.append_entry(
            repo, f"{index:040d}", contract.CONTRACT_FILES[0].relative_path.split(),
            "A reason of fairly typical length for one sync." ,
        )
    size = contextlog.log_path(repo).stat().st_size
    assert size < 8192, f"log grew to {size} bytes"


def test_an_overlong_note_is_truncated(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    contextlog.append_entry(repo, "a" * 40, ["docs/context/STATE.md"], "x" * 900)
    text = contextlog.log_path(repo).read_text(encoding="utf-8")
    assert "…" in text
    assert "x" * 400 not in text


def test_read_recent_respects_its_limit(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    for index in range(6):
        contextlog.append_entry(repo, f"{index:040d}", ["docs/context/STATE.md"], f"E{index}.")
    assert len(contextlog.read_recent(repo, limit=2)) == 2


# --- integration with sync --finalize ------------------------------------


def test_sync_finalize_records_which_context_files_changed(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    commit(repo, "Add context")

    code, payload = cli_json(repo, ["sync", "--finalize", "--note", "Initial audit."])
    assert code == 0
    assert "docs/context/PROJECT.md" in payload["context_files_updated"]
    assert payload["logged"]
    assert "Initial audit." in contextlog.log_path(repo).read_text(encoding="utf-8")


def test_sync_finalize_logs_nothing_when_only_code_changed(tmp_path: Path):
    """Advancing the checkpoint past a pure code change is not a context update."""
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    commit(repo, "Add context")
    run_cli(repo, ["sync", "--finalize"])

    write(repo, "src/app.py", "x = 1\n")
    commit(repo, "Add code only")
    before = contextlog.entry_count(repo)
    code, payload = cli_json(repo, ["sync", "--finalize"])
    assert code == 0
    assert payload["context_files_updated"] == []
    assert contextlog.entry_count(repo) == before


def test_sync_finalize_text_output_explains_when_nothing_was_logged(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    commit(repo, "Add context")
    run_cli(repo, ["sync", "--finalize"])
    write(repo, "src/app.py", "x = 1\n")
    commit(repo, "Add code only")
    _, out = run_cli(repo, ["sync", "--finalize"])
    assert "Nothing recorded in the log" in out
    assert "--note" in out


def test_rebuild_finalize_also_records(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    commit(repo, "Add context")
    code, payload = cli_json(
        repo, ["rebuild", "--finalize", "--note", "Rebuilt after a pivot."]
    )
    assert code == 0
    assert "Rebuilt after a pivot." in contextlog.log_path(repo).read_text(encoding="utf-8")


def test_status_surfaces_the_most_recent_context_update(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    commit(repo, "Add context")
    run_cli(repo, ["sync", "--finalize", "--note", "Initial audit."])

    _, payload = cli_json(repo, ["status"])
    assert payload["recent_context_updates"]
    assert "Initial audit." in payload["recent_context_updates"][0]

    _, out = run_cli(repo, ["status"])
    assert "Last context update:" in out


def test_log_lives_outside_the_context_contract(tmp_path: Path):
    """It is tool bookkeeping, so it must not become a sixth contract file."""
    repo = make_blank_repo(tmp_path)
    contextlog.append_entry(repo, "a" * 40, ["docs/context/STATE.md"], "note")
    assert contextlog.LOG_RELPATH.startswith(".context-maintainer/")
    contract_paths = {cf.relative_path for cf in contract.CONTRACT_FILES}
    assert contextlog.LOG_RELPATH not in contract_paths


def test_log_is_committed_not_cached(tmp_path: Path):
    """A teammate pulling the repository should see it, so it must not be ignored."""
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    contextlog.append_entry(repo, "a" * 40, ["docs/context/STATE.md"], "note")
    from context_maintainer import gitutil

    # Not under cache/, and not matched by the cache .gitignore.
    assert "/cache/" not in contextlog.LOG_RELPATH
    commit(repo, "Add context and log")
    assert contextlog.LOG_RELPATH in gitutil.get_tracked_files(repo)


def test_doctor_still_passes_with_a_log_present(tmp_path: Path):
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    contextlog.append_entry(repo, "a" * 40, ["docs/context/STATE.md"], "note")
    _, payload = cli_json(repo, ["doctor"])
    assert payload["overall"] != "FAIL"
