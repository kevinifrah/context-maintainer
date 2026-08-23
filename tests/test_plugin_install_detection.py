"""A marketplace plugin install must count as installed.

There are two legitimate ways to install: a plugin from a marketplace, and the
symlinks this project's installer creates. An earlier version of the doctor
check only looked for symlinks, so it reported a perfectly working plugin
install as "not installed" — which is exactly the kind of misleading output
this project is supposed to avoid.
"""
from pathlib import Path

import pytest

from context_maintainer import doctor, installer


def _make_plugin_install(
    home: Path,
    host_reldir: str,
    marketplace: str = "context-maintainer",
    plugin: str = "context-maintainer",
    version: str = "0.1.0",
    with_cli: bool = True,
) -> Path:
    """Build the on-disk shape a real marketplace install produces."""
    version_dir = home / host_reldir / marketplace / plugin / version
    version_dir.mkdir(parents=True)
    (version_dir / "SKILL.md").write_text(
        "---\nname: context-maintainer\n---\n", encoding="utf-8"
    )
    (version_dir / "references").mkdir()
    (version_dir / "scripts").mkdir()
    if with_cli:
        package = version_dir / "context_maintainer"
        package.mkdir()
        (package / "cli.py").write_text("# bundled CLI\n", encoding="utf-8")
    return version_dir


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_no_plugin_installs_detected_on_a_clean_home(fake_home: Path):
    assert installer.detect_plugin_installs(home=fake_home) == {}


def test_detects_a_claude_plugin_install(fake_home: Path):
    _make_plugin_install(fake_home, ".claude/plugins/cache")
    found = installer.detect_plugin_installs(home=fake_home)
    assert list(found) == ["claude"]
    assert found["claude"][0].endswith("context-maintainer/0.1.0")


def test_detects_a_codex_plugin_install(fake_home: Path):
    _make_plugin_install(fake_home, ".codex/plugins/cache")
    assert list(installer.detect_plugin_installs(home=fake_home)) == ["codex"]


def test_detects_installs_for_both_hosts(fake_home: Path):
    _make_plugin_install(fake_home, ".claude/plugins/cache")
    _make_plugin_install(fake_home, ".codex/plugins/cache")
    assert set(installer.detect_plugin_installs(home=fake_home)) == {"claude", "codex"}


def test_detects_multiple_versions(fake_home: Path):
    _make_plugin_install(fake_home, ".claude/plugins/cache", version="0.1.0")
    _make_plugin_install(fake_home, ".claude/plugins/cache", version="0.2.0")
    assert len(installer.detect_plugin_installs(home=fake_home)["claude"]) == 2


def test_ignores_an_unrelated_plugin(fake_home: Path):
    _make_plugin_install(fake_home, ".claude/plugins/cache", plugin="something-else")
    assert installer.detect_plugin_installs(home=fake_home) == {}


def test_finds_the_plugin_under_any_marketplace_name(fake_home: Path):
    _make_plugin_install(fake_home, ".claude/plugins/cache", marketplace="community")
    assert list(installer.detect_plugin_installs(home=fake_home)) == ["claude"]


def test_a_directory_without_skill_md_is_not_an_install(fake_home: Path):
    stray = fake_home / ".claude/plugins/cache/mkt/context-maintainer/0.1.0"
    stray.mkdir(parents=True)
    assert installer.detect_plugin_installs(home=fake_home) == {}


def test_plugin_install_is_runnable_requires_the_bundled_cli(fake_home: Path):
    good = _make_plugin_install(fake_home, ".claude/plugins/cache")
    bad = _make_plugin_install(
        fake_home, ".codex/plugins/cache", with_cli=False
    )
    assert installer.plugin_install_is_runnable(good)
    assert not installer.plugin_install_is_runnable(bad)


# --- the doctor check that was wrong -------------------------------------


def _skill_check(monkeypatch, home: Path) -> doctor.CheckResult:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    report = doctor.run_all_checks(home)
    return next(r for r in report.results if r.name == "skill_installation")


def test_doctor_reports_a_plugin_install_as_installed(fake_home: Path, monkeypatch):
    """The regression this file exists for."""
    _make_plugin_install(fake_home, ".claude/plugins/cache")
    _make_plugin_install(fake_home, ".codex/plugins/cache")
    result = _skill_check(monkeypatch, fake_home)
    assert result.status == doctor.PASS
    assert "plugin" in result.message
    assert "not installed" not in result.message


def test_doctor_names_the_host_still_missing(fake_home: Path, monkeypatch):
    _make_plugin_install(fake_home, ".claude/plugins/cache")
    result = _skill_check(monkeypatch, fake_home)
    assert result.status == doctor.WARN
    assert "claude (plugin)" in result.message
    assert "codex" in result.message


def test_doctor_fails_when_a_plugin_install_lacks_its_bundled_cli(
    fake_home: Path, monkeypatch
):
    """A plugin copied without the CLI is broken, and must not read as fine."""
    _make_plugin_install(fake_home, ".claude/plugins/cache", with_cli=False)
    _make_plugin_install(fake_home, ".codex/plugins/cache", with_cli=False)
    result = _skill_check(monkeypatch, fake_home)
    assert result.status == doctor.FAIL
    assert "bundled CLI" in result.message


def test_doctor_warns_when_nothing_is_installed(fake_home: Path, monkeypatch):
    result = _skill_check(monkeypatch, fake_home)
    assert result.status == doctor.WARN
    assert "not installed" in result.message
    # Both installation routes should be offered, not just ours.
    assert "plugin" in (result.remediation or "")
    assert "skill install" in (result.remediation or "")
