"""Installer tests run entirely against a fake HOME.

Nothing here may touch the developer's real ~/.claude or ~/.agents — the
`fake_home` fixture is the only home any test sees.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from context_maintainer import installer

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_CANONICAL = REPO_ROOT / "skill" / "context-maintainer"


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def canonical(tmp_path: Path) -> Path:
    """A stand-in canonical skill directory, shaped like the real one."""
    skill = tmp_path / "checkout" / "skill" / "context-maintainer"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: context-maintainer\n---\n", encoding="utf-8")
    (skill / "references" / "sync-policy.md").write_text("policy\n", encoding="utf-8")
    return skill.resolve()


def _paths(home: Path):
    return {t.host: t.path for t in installer.target_paths(home)}


# --- canonical source discovery -------------------------------------------


def test_find_canonical_skill_source_locates_the_real_checkout():
    assert installer.find_canonical_skill_source() == REAL_CANONICAL.resolve()


def test_find_canonical_skill_source_raises_outside_a_checkout(tmp_path: Path):
    with pytest.raises(installer.InstallerError) as excinfo:
        installer.find_canonical_skill_source(start=tmp_path / "nowhere")
    assert "git checkout" in str(excinfo.value)


def test_target_paths_cover_both_hosts(fake_home: Path):
    paths = _paths(fake_home)
    assert paths["claude"] == fake_home / ".claude/skills/context-maintainer"
    assert paths["codex"] == fake_home / ".agents/skills/context-maintainer"


# --- install ---------------------------------------------------------------


def test_install_creates_both_symlinks_pointing_at_canonical_source(
    fake_home: Path, canonical: Path
):
    report = installer.install(home=fake_home, canonical=canonical)
    assert report.ok
    for path in _paths(fake_home).values():
        assert path.is_symlink()
        assert path.resolve() == canonical
    assert {a.action for a in report.actions} == {installer.CREATED}


def test_install_creates_parent_directories_as_needed(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical)
    assert (fake_home / ".claude" / "skills").is_dir()
    assert (fake_home / ".agents" / "skills").is_dir()


def test_installed_skill_content_is_readable_through_the_symlink(
    fake_home: Path, canonical: Path
):
    installer.install(home=fake_home, canonical=canonical)
    linked = _paths(fake_home)["claude"] / "SKILL.md"
    assert "name: context-maintainer" in linked.read_text(encoding="utf-8")


def test_install_is_idempotent_second_run_reports_already_installed(
    fake_home: Path, canonical: Path
):
    installer.install(home=fake_home, canonical=canonical)
    second = installer.install(home=fake_home, canonical=canonical)
    assert second.ok
    assert {a.action for a in second.actions} == {installer.ALREADY_INSTALLED}


def test_install_repairs_broken_symlink(fake_home: Path, canonical: Path):
    target = _paths(fake_home)["claude"]
    target.parent.mkdir(parents=True)
    target.symlink_to(fake_home / "gone-away", target_is_directory=True)
    report = installer.install(home=fake_home, canonical=canonical)
    assert report.ok
    assert target.resolve() == canonical
    assert any(a.action == installer.REPAIRED for a in report.actions)


def test_install_detects_conflict_when_target_is_real_directory(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("someone else's skill\n", encoding="utf-8")
    report = installer.install(home=fake_home, canonical=canonical)
    assert not report.ok
    conflict = next(a for a in report.actions if a.action == installer.CONFLICT)
    assert "real_directory" in conflict.detail
    assert "--force" in conflict.detail


def test_install_without_force_leaves_conflicting_content_untouched(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    original = target / "SKILL.md"
    original.write_text("do not lose me\n", encoding="utf-8")
    installer.install(home=fake_home, canonical=canonical)
    assert original.read_text(encoding="utf-8") == "do not lose me\n"
    assert not target.is_symlink()


def test_install_still_installs_the_unaffected_host_on_partial_conflict(
    fake_home: Path, canonical: Path
):
    claude = _paths(fake_home)["claude"]
    claude.mkdir(parents=True)
    (claude / "SKILL.md").write_text("other\n", encoding="utf-8")
    installer.install(home=fake_home, canonical=canonical)
    assert _paths(fake_home)["codex"].is_symlink()


def test_install_with_force_backs_up_conflict_then_symlinks(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("previous skill\n", encoding="utf-8")

    report = installer.install(home=fake_home, canonical=canonical, force=True)
    assert report.ok
    assert target.is_symlink()
    assert target.resolve() == canonical

    replaced = next(a for a in report.actions if a.action == installer.REPLACED)
    backup = Path(replaced.backup)
    assert backup.is_dir()
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "previous skill\n"


def test_install_with_force_replaces_a_symlink_pointing_elsewhere(
    fake_home: Path, canonical: Path, tmp_path: Path
):
    other = tmp_path / "other-skill"
    other.mkdir()
    target = _paths(fake_home)["claude"]
    target.parent.mkdir(parents=True)
    target.symlink_to(other, target_is_directory=True)

    report = installer.install(home=fake_home, canonical=canonical, force=True)
    assert report.ok
    assert target.resolve() == canonical
    assert other.is_dir(), "the other skill directory itself must survive"


def test_wrong_symlink_requires_force(fake_home: Path, canonical: Path, tmp_path: Path):
    other = tmp_path / "other-skill"
    other.mkdir()
    target = _paths(fake_home)["claude"]
    target.parent.mkdir(parents=True)
    target.symlink_to(other, target_is_directory=True)
    report = installer.install(home=fake_home, canonical=canonical)
    assert not report.ok
    assert target.resolve() == other


# --- dry run --------------------------------------------------------------


def test_dry_run_install_makes_no_filesystem_changes(fake_home: Path, canonical: Path):
    before = sorted(p.as_posix() for p in fake_home.rglob("*"))
    report = installer.install(home=fake_home, canonical=canonical, dry_run=True)
    assert report.dry_run
    assert {a.action for a in report.actions} == {installer.WOULD_CREATE}
    assert sorted(p.as_posix() for p in fake_home.rglob("*")) == before


def test_dry_run_uninstall_makes_no_filesystem_changes(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical)
    before = sorted(p.as_posix() for p in fake_home.rglob("*"))
    report = installer.uninstall(home=fake_home, canonical=canonical, dry_run=True)
    assert {a.action for a in report.actions} == {installer.WOULD_REMOVE}
    assert sorted(p.as_posix() for p in fake_home.rglob("*")) == before
    assert _paths(fake_home)["claude"].is_symlink()


def test_dry_run_reports_conflicts_without_backing_anything_up(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("other\n", encoding="utf-8")
    report = installer.install(home=fake_home, canonical=canonical, dry_run=True, force=True)
    assert any(a.action == installer.WOULD_REPLACE for a in report.actions)
    assert not list(fake_home.glob(".claude/skills/*.cm-backup-*"))


# --- uninstall ------------------------------------------------------------


def test_uninstall_removes_symlinks_pointing_at_canonical_source(
    fake_home: Path, canonical: Path
):
    installer.install(home=fake_home, canonical=canonical)
    report = installer.uninstall(home=fake_home, canonical=canonical)
    assert report.ok
    for path in _paths(fake_home).values():
        assert not path.exists()
    assert canonical.is_dir(), "uninstall must never touch the canonical source"


def test_uninstall_is_idempotent(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical)
    installer.uninstall(home=fake_home, canonical=canonical)
    second = installer.uninstall(home=fake_home, canonical=canonical)
    assert second.ok
    assert {a.action for a in second.actions} == {installer.NOT_INSTALLED}


def test_uninstall_refuses_unrelated_directory_without_force(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("someone else\n", encoding="utf-8")
    report = installer.uninstall(home=fake_home, canonical=canonical)
    assert not report.ok
    assert (target / "SKILL.md").exists()
    conflict = next(a for a in report.actions if a.action == installer.CONFLICT)
    assert "refusing to remove" in conflict.detail


def test_uninstall_with_force_backs_up_unrelated_directory(
    fake_home: Path, canonical: Path
):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("someone else\n", encoding="utf-8")
    report = installer.uninstall(home=fake_home, canonical=canonical, force=True)
    assert report.ok
    removed = next(a for a in report.actions if a.action == installer.REMOVED and a.backup)
    assert (Path(removed.backup) / "SKILL.md").exists()


def test_uninstall_clears_a_broken_symlink(fake_home: Path, canonical: Path):
    target = _paths(fake_home)["claude"]
    target.parent.mkdir(parents=True)
    target.symlink_to(fake_home / "gone", target_is_directory=True)
    report = installer.uninstall(home=fake_home, canonical=canonical)
    assert report.ok
    assert not target.exists() and not target.is_symlink()


def test_uninstall_works_without_a_canonical_checkout(fake_home: Path, canonical: Path):
    """Uninstalling must still work if the checkout has moved away."""
    installer.install(home=fake_home, canonical=canonical)
    report = installer.uninstall(home=fake_home, canonical=Path("/nonexistent"))
    # The symlink no longer matches canonical, so it is treated as foreign.
    assert not report.ok


# --- status ---------------------------------------------------------------


def test_status_reports_absent_before_install(fake_home: Path, canonical: Path):
    report = installer.status(home=fake_home, canonical=canonical)
    assert {a.action for a in report.actions} == {installer.ABSENT}


def test_status_reports_correct_symlink_after_install(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical)
    report = installer.status(home=fake_home, canonical=canonical)
    assert {a.action for a in report.actions} == {installer.CORRECT_SYMLINK}


def test_status_changes_nothing(fake_home: Path, canonical: Path):
    before = sorted(p.as_posix() for p in fake_home.rglob("*"))
    installer.status(home=fake_home, canonical=canonical)
    assert sorted(p.as_posix() for p in fake_home.rglob("*")) == before


# --- rendering and reports ------------------------------------------------


def test_render_text_marks_conflicts_and_reports_verb(fake_home: Path, canonical: Path):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    text = installer.render_text(
        installer.install(home=fake_home, canonical=canonical), "Install"
    )
    assert "Install incomplete" in text
    assert "!" in text


def test_report_to_dict_is_json_serializable(fake_home: Path, canonical: Path):
    payload = installer.install(home=fake_home, canonical=canonical).to_dict()
    assert json.loads(json.dumps(payload))["ok"] is True


# --- bootstrap scripts ----------------------------------------------------


def _bootstrap(script: str, *args: str):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "installer" / script), *args],
        capture_output=True,
        text=True,
    )


def test_bootstrap_install_script_runs_without_prior_pip_install(
    fake_home: Path, canonical: Path
):
    """Must work straight from a bare clone, with src/ not on sys.path."""
    result = _bootstrap(
        "install.py",
        "--home",
        str(fake_home),
        "--canonical",
        str(canonical),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert _paths(fake_home)["claude"].is_symlink()


def test_bootstrap_dry_run_does_not_mutate_user_configuration(
    fake_home: Path, canonical: Path
):
    result = _bootstrap(
        "install.py",
        "--home",
        str(fake_home),
        "--canonical",
        str(canonical),
        "--dry-run",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert not (fake_home / ".claude").exists()
    assert not (fake_home / ".agents").exists()


def test_bootstrap_uninstall_script_removes_installation(
    fake_home: Path, canonical: Path
):
    _bootstrap("install.py", "--home", str(fake_home), "--canonical", str(canonical))
    result = _bootstrap(
        "uninstall.py",
        "--home",
        str(fake_home),
        "--canonical",
        str(canonical),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    assert not _paths(fake_home)["claude"].exists()


def test_bootstrap_install_exits_nonzero_on_conflict(fake_home: Path, canonical: Path):
    target = _paths(fake_home)["claude"]
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("other\n", encoding="utf-8")
    result = _bootstrap(
        "install.py", "--home", str(fake_home), "--canonical", str(canonical)
    )
    assert result.returncode == 1
    assert "--force" in result.stdout


def test_bootstrap_install_against_the_real_canonical_source(fake_home: Path):
    """No --canonical: exercises real discovery from the checkout."""
    result = _bootstrap("install.py", "--home", str(fake_home), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["canonical"] == str(REAL_CANONICAL.resolve())
    assert (
        _paths(fake_home)["codex"] / "SKILL.md"
    ).is_file(), "real SKILL.md must be reachable through the symlink"
