from pathlib import Path

from context_maintainer import repository

from conftest import commit_all, init_git_repo, write


def test_blank_repo_with_only_readme_license_gitignore_returns_blank_mode(blank_repo: Path):
    result = repository.classify(blank_repo)
    assert result.mode == repository.MODE_BLANK
    assert not result.is_existing


def test_repo_with_pyproject_toml_returns_existing_mode(git_repo: Path):
    write(git_repo, "pyproject.toml", '[project]\nname = "x"\n')
    result = repository.classify(git_repo)
    assert result.mode == repository.MODE_EXISTING
    assert any("manifest" in item for item in result.evidence)


def test_repo_with_single_source_file_returns_existing_mode(git_repo: Path):
    write(git_repo, "app.py", "print('hi')\n")
    result = repository.classify(git_repo)
    assert result.mode == repository.MODE_EXISTING


def test_many_trivial_commits_only_touching_readme_returns_blank_mode(git_repo: Path):
    for index in range(6):
        write(git_repo, "README.md", f"# demo\n\nrevision {index}\n")
        commit_all(git_repo, f"Update README {index}")
    result = repository.classify(git_repo)
    assert result.mode == repository.MODE_BLANK
    assert result.commit_count == 6


def test_repo_with_no_git_and_source_files_returns_existing_mode(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    write(plain, "main.go", "package main\n")
    result = repository.classify(plain)
    assert result.mode == repository.MODE_EXISTING
    assert result.commit_count == 0


def test_repo_with_only_config_files_and_several_commits_returns_existing_mode(git_repo: Path):
    write(git_repo, "docs/guide.md", "# guide\n")
    commit_all(git_repo, "Add guide")
    write(git_repo, "docs/faq.md", "# faq\n")
    commit_all(git_repo, "Add faq")
    write(git_repo, "docs/spec.md", "# spec\n")
    commit_all(git_repo, "Add spec")
    result = repository.classify(git_repo)
    assert result.mode == repository.MODE_EXISTING


def test_context_maintainer_own_files_do_not_make_a_repo_existing(blank_repo: Path):
    write(blank_repo, "AGENTS.md", "# router\n")
    write(blank_repo, "CLAUDE.md", "@AGENTS.md\n")
    write(blank_repo, "docs/context/PROJECT.md", "# Project\n")
    write(blank_repo, "docs/context/STATE.md", "# State\n")
    write(blank_repo, "docs/context/ARCHITECTURE.md", "# Architecture\n")
    commit_all(blank_repo, "Add context scaffold")
    result = repository.classify(blank_repo)
    assert result.mode == repository.MODE_BLANK


def test_classify_evidence_lists_matched_signals(git_repo: Path):
    write(git_repo, "package.json", '{"name": "x"}\n')
    write(git_repo, "index.js", "console.log(1)\n")
    result = repository.classify(git_repo)
    joined = " ".join(result.evidence)
    assert "package.json" in joined
    assert "source file" in joined


def test_mode_override_forces_blank_on_a_real_project(existing_repo: Path):
    result = repository.classify(existing_repo, mode="blank")
    assert result.mode == repository.MODE_BLANK
    assert result.overridden
    assert "mode override" in result.evidence[0]


def test_mode_override_forces_existing_on_blank_looking_repo(blank_repo: Path):
    result = repository.classify(blank_repo, mode="existing")
    assert result.mode == repository.MODE_EXISTING
    assert result.overridden


def test_find_repo_root_returns_git_toplevel_from_subdirectory(existing_repo: Path):
    nested = existing_repo / "src" / "app"
    assert repository.find_repo_root(nested) == existing_repo.resolve()


def test_find_repo_root_falls_back_to_start_outside_git(tmp_path: Path):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert repository.find_repo_root(plain) == plain.resolve()


def test_describe_repo_reports_branch_and_commit_count(existing_repo: Path):
    context = repository.describe_repo(existing_repo)
    assert context.is_git_repo
    assert context.branch == "main"
    assert context.commit_count == 3
    assert context.has_commits


def test_describe_repo_on_non_git_directory(tmp_path: Path):
    plain = tmp_path / "plain2"
    plain.mkdir()
    context = repository.describe_repo(plain)
    assert not context.is_git_repo
    assert context.head_commit is None


def test_iter_candidate_files_skips_ignored_directories(git_repo: Path):
    write(git_repo, "node_modules/pkg/index.js", "module.exports = 1\n")
    write(git_repo, "src/real.py", "x = 1\n")
    found = repository.iter_candidate_files(git_repo)
    assert "src/real.py" in found
    assert not any("node_modules" in path for path in found)


def test_unborn_head_repo_is_blank(tmp_path: Path):
    fresh = init_git_repo(tmp_path / "fresh")
    result = repository.classify(fresh)
    assert result.mode == repository.MODE_BLANK
    assert result.commit_count == 0
