from pathlib import Path

from context_maintainer import contract, scaffold

from conftest import commit_all, write


def test_write_contract_files_creates_all_seven_contract_files(git_repo: Path):
    result = scaffold.write_contract_files(git_repo, project_name="demo")
    assert len(result.created) == 7
    for contract_file in contract.CONTRACT_FILES:
        assert (git_repo / contract_file.relative_path).exists()


def test_claude_md_first_line_is_agents_md_import(git_repo: Path):
    scaffold.write_contract_files(git_repo, project_name="demo")
    text = (git_repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.splitlines()[0].strip() == "@AGENTS.md"


def test_project_name_is_substituted_into_agents_md(git_repo: Path):
    scaffold.write_contract_files(git_repo, project_name="my-service")
    text = (git_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "my-service" in text
    assert "{project_name}" not in text


def test_existing_files_are_preserved_not_overwritten(git_repo: Path):
    write(git_repo, "AGENTS.md", "# hand written rules\n\nDo not lose me.\n")
    result = scaffold.write_contract_files(git_repo, project_name="demo")
    assert "AGENTS.md" in result.preserved
    assert "AGENTS.md" not in result.created
    assert "Do not lose me." in (git_repo / "AGENTS.md").read_text(encoding="utf-8")


def test_force_backs_up_before_replacing(git_repo: Path):
    write(git_repo, "AGENTS.md", "# original\n")
    commit_all(git_repo, "Add original agents file")
    result = scaffold.write_contract_files(git_repo, project_name="demo", force=True)
    assert "AGENTS.md" in result.backed_up
    backups = list((git_repo / contract.BACKUP_DIR).rglob("AGENTS.md"))
    assert backups
    assert "# original" in backups[0].read_text(encoding="utf-8")


def test_force_refuses_to_clobber_a_dirty_tracked_file(git_repo: Path):
    write(git_repo, "AGENTS.md", "# committed\n")
    commit_all(git_repo, "Add agents file")
    write(git_repo, "AGENTS.md", "# uncommitted work in progress\n")
    result = scaffold.write_contract_files(git_repo, project_name="demo", force=True)
    assert "AGENTS.md" in result.preserved
    assert "work in progress" in (git_repo / "AGENTS.md").read_text(encoding="utf-8")


def test_running_twice_is_idempotent_and_creates_nothing_new(git_repo: Path):
    first = scaffold.write_contract_files(git_repo, project_name="demo")
    second = scaffold.write_contract_files(git_repo, project_name="demo")
    assert len(first.created) == 7
    assert second.created == []
    assert len(second.preserved) == 7


def test_ensure_cache_gitignore_creates_star_ignore_file(git_repo: Path):
    path = scaffold.ensure_cache_gitignore(git_repo)
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("*")


def test_backup_file_preserves_original_content_and_relative_path(git_repo: Path):
    write(git_repo, "docs/context/STATE.md", "# State\n\noriginal state\n")
    destination = scaffold.backup_file(git_repo, "docs/context/STATE.md", slug="stamp")
    assert destination.exists()
    assert "original state" in destination.read_text(encoding="utf-8")
    assert destination.as_posix().endswith("stamp/docs/context/STATE.md")


def test_detect_existing_agent_files_finds_root_and_nested_files(git_repo: Path):
    write(git_repo, "AGENTS.md", "root rules\n")
    write(git_repo, "CLAUDE.md", "claude rules\n")
    write(git_repo, "packages/api/AGENTS.md", "nested rules\n")
    write(git_repo, ".cursorrules", "cursor rules\n")
    found = {f.relative_path for f in scaffold.detect_existing_agent_files(git_repo)}
    assert "AGENTS.md" in found
    assert "CLAUDE.md" in found
    assert "packages/api/AGENTS.md" in found
    assert ".cursorrules" in found


def test_detect_existing_agent_files_reports_size_metadata(git_repo: Path):
    write(git_repo, "AGENTS.md", "line one\nline two\n")
    found = scaffold.detect_existing_agent_files(git_repo)
    assert found[0].line_count == 2
    assert found[0].size_bytes > 0


def test_detect_existing_agent_files_empty_on_blank_repo(blank_repo: Path):
    assert scaffold.detect_existing_agent_files(blank_repo) == []


def test_backup_context_documents_copies_every_existing_contract_file(git_repo: Path):
    scaffold.write_contract_files(git_repo, project_name="demo")
    backed_up = scaffold.backup_context_documents(git_repo)
    assert len(backed_up) == 7
    copies = list((git_repo / contract.BACKUP_DIR).rglob("PROJECT.md"))
    assert copies


def test_render_template_leaves_markdown_and_json_braces_intact():
    text = scaffold.render_template("DECISIONS.md.tmpl", {"project_name": "x"})
    assert "DEC-001" in text
    schema = scaffold.load_template("manifest.schema.json")
    assert "{" in schema and "}" in schema
