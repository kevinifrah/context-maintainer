from pathlib import Path

from context_maintainer import briefing, contract, gitutil, manifest as manifest_mod, scaffold

from conftest import commit_all, write


def _initialize(root: Path, mode: str = "blank"):
    """Scaffold, commit that scaffold, then checkpoint at the resulting HEAD.

    Committing matters here: otherwise the scaffold itself shows up as
    "changed since the checkpoint" and muddies every staleness assertion.
    """
    path = root / contract.MANIFEST_PATH
    scaffold.write_contract_files(root, project_name=root.name)
    created = manifest_mod.default_manifest(mode)
    manifest_mod.save_manifest(created, path)
    if gitutil.is_git_repo(root):
        commit_all(root, "Add context scaffold")
        # Checkpoint at the commit that contains the scaffold, exactly as
        # `sync --finalize` would after the fact.
        manifest_mod.update_checkpoint(created, gitutil.get_head_commit(root))
        manifest_mod.save_manifest(created, path)
    return created


def _set_section(root: Path, relative_path: str, heading: str, body: str):
    path = root / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    output = []
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        if line.strip() == f"## {heading}":
            index += 1
            # skip the existing placeholder body up to the next H2
            while index < len(lines) and not lines[index].startswith("## "):
                index += 1
            output.append("")
            output.append(body)
            output.append("")
            continue
        index += 1
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def test_status_report_flags_uninitialized_repository(blank_repo: Path):
    report = briefing.build_status_report(blank_repo)
    assert not report.initialized
    assert any("init" in action for action in report.suggested_next_actions)


def test_status_report_extracts_goal_from_project_md(blank_repo: Path):
    _initialize(blank_repo)
    _set_section(blank_repo, "docs/context/PROJECT.md", "Goal", "Ship a widget factory.")
    report = briefing.build_status_report(blank_repo)
    assert report.goal == "Ship a widget factory."


def test_status_report_extracts_blockers_from_state_md(blank_repo: Path):
    _initialize(blank_repo)
    _set_section(blank_repo, "docs/context/STATE.md", "Blockers", "Waiting on API keys.")
    report = briefing.build_status_report(blank_repo)
    assert report.blockers == "Waiting on API keys."
    assert any("blockers" in a.lower() for a in report.suggested_next_actions)


def test_placeholder_sections_are_reported_as_not_documented(blank_repo: Path):
    _initialize(blank_repo)
    report = briefing.build_status_report(blank_repo)
    assert report.goal is None
    assert report.phase is None
    assert "docs/context/PROJECT.md" in report.placeholder_files


def test_status_report_flags_stale_when_checkpoint_behind_head(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    commit_all(existing_repo, "Add auth service")
    report = briefing.build_status_report(existing_repo)
    assert report.staleness.is_stale
    assert report.staleness.commits_behind == 1
    assert report.staleness.files_changed >= 1
    changed = [
        path
        for _, path in gitutil.get_changed_files_since(
            existing_repo, report.staleness.checkpoint
        )
    ]
    assert "src/app/auth.py" in changed
    assert any("sync" in a for a in report.suggested_next_actions)


def test_status_report_not_stale_when_checkpoint_matches_head(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    report = briefing.build_status_report(existing_repo)
    assert not report.staleness.is_stale
    assert report.staleness.reason == "checkpoint matches HEAD"


def test_status_report_lists_recent_commits(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    report = briefing.build_status_report(existing_repo)
    assert report.recent_changes
    assert any("Add tests" in change for change in report.recent_changes)


def test_status_report_reports_branch(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    report = briefing.build_status_report(existing_repo)
    assert report.branch == "main"


def test_status_report_detects_missing_checkpoint_as_stale(existing_repo: Path):
    created = _initialize(existing_repo, mode="existing")
    created.last_verified_commit = None
    manifest_mod.save_manifest(created, existing_repo / contract.MANIFEST_PATH)
    report = briefing.build_status_report(existing_repo)
    assert report.staleness.is_stale
    assert "no checkpoint" in report.staleness.reason


def test_status_report_suggests_nothing_to_do_when_fully_populated(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    for contract_file in contract.CONTRACT_FILES:
        path = existing_repo / contract_file.relative_path
        text = path.read_text(encoding="utf-8").replace(
            contract.PLACEHOLDER_SENTINEL, "documented"
        )
        path.write_text(text, encoding="utf-8")
    _set_section(existing_repo, "docs/context/STATE.md", "Blockers", "None")
    _set_section(existing_repo, "docs/context/STATE.md", "Next", "None")
    report = briefing.build_status_report(existing_repo)
    assert report.suggested_next_actions == [
        "Context appears current; no maintenance needed."
    ]


def test_blockers_written_as_none_are_not_reported_as_blockers(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    _set_section(existing_repo, "docs/context/STATE.md", "Blockers", "None.")
    report = briefing.build_status_report(existing_repo)
    assert report.blockers is None


def test_render_text_handles_uninitialized_and_initialized(blank_repo: Path):
    uninitialized = briefing.render_text(briefing.build_status_report(blank_repo))
    assert "Not initialized" in uninitialized
    _initialize(blank_repo)
    initialized = briefing.render_text(briefing.build_status_report(blank_repo))
    assert "Context freshness" in initialized


def test_to_dict_is_json_serializable(existing_repo: Path):
    import json

    _initialize(existing_repo, mode="existing")
    payload = briefing.build_status_report(existing_repo).to_dict()
    assert json.loads(json.dumps(payload))["initialized"] is True


def test_long_sections_are_truncated(blank_repo: Path):
    _initialize(blank_repo)
    _set_section(blank_repo, "docs/context/PROJECT.md", "Goal", "word " * 300)
    report = briefing.build_status_report(blank_repo)
    assert len(report.goal) <= briefing._MAX_SUMMARY_CHARS
    assert report.goal.endswith("…")


def test_commits_touching_only_context_files_are_not_reported_as_drift(
    existing_repo: Path,
):
    """A sync's own bookkeeping must not make the tool report itself stale.

    `sync --finalize` writes the manifest; committing that write lands after
    the checkpoint it recorded. Counting that as drift produced a permanent
    false positive right after every sync.
    """
    _initialize(existing_repo, mode="existing")
    _set_section(existing_repo, "docs/context/STATE.md", "Phase", "Shipping.")
    commit_all(existing_repo, "Sync context and advance checkpoint")

    report = briefing.build_status_report(existing_repo)
    assert report.staleness.commits_behind == 1
    assert report.staleness.files_changed == 0
    assert report.staleness.is_stale is False
    assert "no code drift" in report.staleness.reason


def test_code_changes_alongside_context_changes_still_count_as_drift(
    existing_repo: Path,
):
    _initialize(existing_repo, mode="existing")
    _set_section(existing_repo, "docs/context/STATE.md", "Phase", "Shipping.")
    write(existing_repo, "src/app/billing.py", "def charge():\n    return True\n")
    commit_all(existing_repo, "Add billing alongside a context edit")

    report = briefing.build_status_report(existing_repo)
    assert report.staleness.is_stale is True
    assert report.staleness.files_changed == 1


def test_agents_md_and_claude_md_count_as_context_owned(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    write(existing_repo, "AGENTS.md", "# rules\n\nUpdated router.\n")
    commit_all(existing_repo, "Tweak agent instructions")

    report = briefing.build_status_report(existing_repo)
    assert report.staleness.is_stale is False


def test_none_followed_by_an_evidence_annotation_is_still_empty(existing_repo: Path):
    """Evidence-graded docs write "None. CONFIRMED (user, date)." for an empty
    section; the annotation must not make it look like real content."""
    _initialize(existing_repo, mode="existing")
    _set_section(
        existing_repo,
        "docs/context/STATE.md",
        "Blockers",
        "None. CONFIRMED (user, 2026-08-24).",
    )
    report = briefing.build_status_report(existing_repo)
    assert report.blockers is None
    assert not any("blockers" in a.lower() for a in report.suggested_next_actions)


def test_none_beginning_a_real_sentence_is_still_content(existing_repo: Path):
    """"None of the storage layer is migrated" is a blocker, not an empty section."""
    _initialize(existing_repo, mode="existing")
    _set_section(
        existing_repo,
        "docs/context/STATE.md",
        "Blockers",
        "None of the storage layer is migrated yet.",
    )
    report = briefing.build_status_report(existing_repo)
    assert report.blockers is not None
    assert "storage layer" in report.blockers
