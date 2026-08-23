import json
from pathlib import Path

from context_maintainer import contract, doctor, manifest as manifest_mod, scaffold

from conftest import commit_all, write


def _initialize(root: Path, mode: str = "blank"):
    scaffold.write_contract_files(root, project_name=root.name)
    from context_maintainer import gitutil

    created = manifest_mod.default_manifest(mode, commit=gitutil.get_head_commit(root))
    manifest_mod.save_manifest(created, root / contract.MANIFEST_PATH)
    return created


def _result(report: doctor.DoctorReport, name: str) -> doctor.CheckResult:
    return next(r for r in report.results if r.name == name)


def test_doctor_does_not_fail_on_freshly_scaffolded_blank_project(blank_repo: Path):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    assert report.overall != doctor.FAIL


def test_doctor_fails_on_uninitialized_repository(blank_repo: Path):
    report = doctor.run_all_checks(blank_repo)
    assert report.overall == doctor.FAIL
    assert _result(report, "manifest_present").status == doctor.FAIL


def test_doctor_fails_when_required_file_missing(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / "docs/context/ARCHITECTURE.md").unlink()
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "required_files").status == doctor.FAIL
    assert "ARCHITECTURE.md" in _result(report, "required_files").message


def test_doctor_fails_when_claude_md_missing_agents_import(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / "CLAUDE.md").write_text("# Claude rules\n", encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "claude_agents_bridge").status == doctor.FAIL


def test_doctor_accepts_agents_import_after_blank_lines(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / "CLAUDE.md").write_text("\n\n@AGENTS.md\n", encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "claude_agents_bridge").status == doctor.PASS


def test_doctor_fails_when_required_section_removed(blank_repo: Path):
    _initialize(blank_repo)
    path = blank_repo / "docs/context/PROJECT.md"
    text = path.read_text(encoding="utf-8").replace("## Non-Goals", "## Something Else")
    path.write_text(text, encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "required_sections").status == doctor.FAIL
    assert "Non-Goals" in _result(report, "required_sections").message


def test_doctor_warns_when_placeholder_sentinel_still_present(blank_repo: Path):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "no_placeholders").status == doctor.WARN


def test_doctor_passes_placeholder_check_once_content_is_written(blank_repo: Path):
    _initialize(blank_repo)
    for contract_file in contract.CONTRACT_FILES:
        path = blank_repo / contract_file.relative_path
        text = path.read_text(encoding="utf-8").replace(
            contract.PLACEHOLDER_SENTINEL, "real content"
        )
        path.write_text(text, encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "no_placeholders").status == doctor.PASS


def test_doctor_fails_when_manifest_json_is_malformed(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / contract.MANIFEST_PATH).write_text("{broken", encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "manifest_present").status == doctor.FAIL


def test_doctor_fails_when_manifest_carries_product_knowledge(blank_repo: Path):
    _initialize(blank_repo)
    path = blank_repo / contract.MANIFEST_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    data["project_goal"] = "knowledge does not belong here"
    path.write_text(json.dumps(data), encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "manifest_schema").status == doctor.FAIL


def test_doctor_fails_when_checkpoint_commit_does_not_exist(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    path = existing_repo / contract.MANIFEST_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    data["last_verified_commit"] = "0" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    report = doctor.run_all_checks(existing_repo)
    assert _result(report, "checkpoint_valid").status == doctor.FAIL


def test_doctor_reports_checkpoint_matching_head_as_pass(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    report = doctor.run_all_checks(existing_repo)
    assert _result(report, "checkpoint_freshness").status == doctor.PASS


def test_doctor_warns_when_checkpoint_far_behind_head(existing_repo: Path):
    _initialize(existing_repo, mode="existing")
    for index in range(doctor._STALE_COMMIT_THRESHOLD + 1):
        write(existing_repo, f"src/app/mod_{index}.py", f"value = {index}\n")
        commit_all(existing_repo, f"Add module {index}")
    report = doctor.run_all_checks(existing_repo)
    assert _result(report, "checkpoint_freshness").status == doctor.WARN


def test_doctor_warns_when_cache_not_ignored(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / contract.CACHE_DIR / ".gitignore").unlink()
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "cache_ignored").status == doctor.WARN


def test_doctor_warns_when_context_file_is_absurdly_large(blank_repo: Path):
    _initialize(blank_repo)
    path = blank_repo / "docs/context/STATE.md"
    path.write_text(
        path.read_text(encoding="utf-8") + ("x" * (contract.MAX_CONTEXT_FILE_BYTES + 1)),
        encoding="utf-8",
    )
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "context_size").status == doctor.WARN


def test_doctor_warns_when_agents_md_duplicates_context_prose(blank_repo: Path):
    _initialize(blank_repo)
    duplicated = (
        "This project exists to demonstrate a long duplicated prose paragraph that "
        "should live in exactly one place within the documented context contract."
    )
    project = blank_repo / "docs/context/PROJECT.md"
    project.write_text(
        project.read_text(encoding="utf-8") + "\n" + duplicated + "\n", encoding="utf-8"
    )
    agents = blank_repo / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8") + "\n" + duplicated + "\n", encoding="utf-8"
    )
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "no_duplication").status == doctor.WARN


def test_doctor_warns_on_broken_relative_link(blank_repo: Path):
    _initialize(blank_repo)
    path = blank_repo / "docs/context/ARCHITECTURE.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nSee [gone](../../src/missing.py).\n",
        encoding="utf-8",
    )
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "referenced_paths").status == doctor.WARN


def test_doctor_scaffold_links_resolve(blank_repo: Path):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "referenced_paths").status == doctor.PASS


def test_report_failed_respects_strict_mode(blank_repo: Path):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    assert report.overall == doctor.WARN
    assert not report.failed(strict=False)
    assert report.failed(strict=True)


def test_render_text_includes_overall_verdict(blank_repo: Path):
    _initialize(blank_repo)
    text = doctor.render_text(doctor.run_all_checks(blank_repo))
    assert "Overall:" in text


def test_decisions_check_warns_when_entries_removed(blank_repo: Path):
    _initialize(blank_repo)
    (blank_repo / "docs/context/DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert _result(report, "decisions_entries").status == doctor.WARN
