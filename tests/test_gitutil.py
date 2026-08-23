from pathlib import Path

from context_maintainer import gitutil

from conftest import commit_all, write


def test_git_is_available_in_test_environment():
    assert gitutil.is_git_available()


def test_get_head_commit_on_fresh_repo_with_no_commits_returns_none(git_repo: Path):
    assert gitutil.get_head_commit(git_repo) is None


def test_get_commit_count_matches_number_of_commits_made(existing_repo: Path):
    assert gitutil.get_commit_count(existing_repo) == 3


def test_get_head_commit_returns_full_sha(existing_repo: Path):
    head = gitutil.get_head_commit(existing_repo)
    assert head is not None
    assert len(head) == 40


def test_get_changed_files_since_detects_added_modified_deleted(existing_repo: Path):
    base = gitutil.get_head_commit(existing_repo)
    write(existing_repo, "src/app/auth.py", "def login():\n    return True\n")
    write(existing_repo, "src/app/main.py", "def main():\n    return 'changed'\n")
    (existing_repo / "tests/test_main.py").unlink()
    commit_all(existing_repo, "Add auth, change main, drop test")

    changes = dict(
        (path, status) for status, path in gitutil.get_changed_files_since(existing_repo, base)
    )
    assert changes["src/app/auth.py"] == "A"
    assert changes["src/app/main.py"] == "M"
    assert changes["tests/test_main.py"] == "D"


def test_get_changed_files_since_reports_rename_destination(existing_repo: Path):
    base = gitutil.get_head_commit(existing_repo)
    (existing_repo / "src/app/main.py").rename(existing_repo / "src/app/entry.py")
    commit_all(existing_repo, "Rename main to entry")
    paths = [path for _, path in gitutil.get_changed_files_since(existing_repo, base)]
    assert "src/app/entry.py" in paths


def test_get_commits_since_lists_only_newer_commits(existing_repo: Path):
    base = gitutil.get_head_commit(existing_repo)
    write(existing_repo, "src/app/extra.py", "x = 1\n")
    commit_all(existing_repo, "Add extra module")
    commits = gitutil.get_commits_since(existing_repo, base)
    assert len(commits) == 1
    assert commits[0][1] == "Add extra module"


def test_is_ancestor_true_for_earlier_commit(existing_repo: Path):
    log = gitutil.get_log(existing_repo, 10)
    oldest_sha = log[-1][0]
    assert gitutil.is_ancestor(existing_repo, oldest_sha)


def test_commit_exists_false_for_unknown_sha(existing_repo: Path):
    assert not gitutil.commit_exists(existing_repo, "0" * 40)


def test_commit_exists_true_for_head(existing_repo: Path):
    head = gitutil.get_head_commit(existing_repo)
    assert gitutil.commit_exists(existing_repo, head)


def test_get_tracked_files_lists_committed_paths(existing_repo: Path):
    tracked = gitutil.get_tracked_files(existing_repo)
    assert "pyproject.toml" in tracked
    assert "src/app/main.py" in tracked


def test_get_working_tree_changes_reports_uncommitted_edits(existing_repo: Path):
    write(existing_repo, "src/app/main.py", "def main():\n    return 'dirty'\n")
    changes = gitutil.get_working_tree_changes(existing_repo)
    assert any(path == "src/app/main.py" for _, path in changes)


def test_is_path_dirty_true_only_for_modified_path(existing_repo: Path):
    write(existing_repo, "src/app/main.py", "def main():\n    return 'dirty'\n")
    assert gitutil.is_path_dirty(existing_repo, "src/app/main.py")
    assert not gitutil.is_path_dirty(existing_repo, "pyproject.toml")


def test_get_current_branch_reports_main(existing_repo: Path):
    assert gitutil.get_current_branch(existing_repo) == "main"


def test_is_git_repo_false_outside_a_repository(tmp_path: Path):
    plain = tmp_path / "outside"
    plain.mkdir()
    assert not gitutil.is_git_repo(plain)
