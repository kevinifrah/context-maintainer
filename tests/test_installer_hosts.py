"""Per-host installation: install for Claude Code only, Codex only, or both."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from context_maintainer import installer

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def canonical(tmp_path: Path) -> Path:
    skill = tmp_path / "checkout" / "skill" / "context-maintainer"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: context-maintainer\n---\n", encoding="utf-8")
    return skill.resolve()


def _claude(home: Path) -> Path:
    return home / ".claude/skills/context-maintainer"


def _codex(home: Path) -> Path:
    return home / ".agents/skills/context-maintainer"


def test_default_targets_both_hosts(fake_home: Path):
    assert {t.host for t in installer.target_paths(fake_home)} == {"claude", "codex"}


def test_target_paths_can_be_narrowed_to_one_host(fake_home: Path):
    targets = installer.target_paths(fake_home, hosts=["claude"])
    assert [t.host for t in targets] == ["claude"]


def test_unknown_host_is_rejected_with_a_helpful_message(fake_home: Path):
    with pytest.raises(installer.InstallerError) as excinfo:
        installer.target_paths(fake_home, hosts=["emacs"])
    assert "emacs" in str(excinfo.value)
    assert "claude" in str(excinfo.value)


def test_install_claude_only_leaves_codex_untouched(fake_home: Path, canonical: Path):
    report = installer.install(home=fake_home, canonical=canonical, hosts=["claude"])
    assert report.ok
    assert _claude(fake_home).is_symlink()
    assert not _codex(fake_home).exists()
    assert not (fake_home / ".agents").exists()


def test_install_codex_only_leaves_claude_untouched(fake_home: Path, canonical: Path):
    report = installer.install(home=fake_home, canonical=canonical, hosts=["codex"])
    assert report.ok
    assert _codex(fake_home).is_symlink()
    assert not _claude(fake_home).exists()


def test_install_both_hosts_explicitly(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical, hosts=["claude", "codex"])
    assert _claude(fake_home).is_symlink()
    assert _codex(fake_home).is_symlink()


def test_uninstall_one_host_leaves_the_other_installed(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical)
    installer.uninstall(home=fake_home, canonical=canonical, hosts=["claude"])
    assert not _claude(fake_home).exists()
    assert _codex(fake_home).is_symlink()


def test_status_can_report_a_single_host(fake_home: Path, canonical: Path):
    installer.install(home=fake_home, canonical=canonical, hosts=["codex"])
    report = installer.status(home=fake_home, canonical=canonical, hosts=["codex"])
    assert [a.host for a in report.actions] == ["codex"]
    assert report.actions[0].action == installer.CORRECT_SYMLINK


def test_bootstrap_script_accepts_host_flags(fake_home: Path, canonical: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "installer" / "install.py"),
            "--home",
            str(fake_home),
            "--canonical",
            str(canonical),
            "--claude",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [a["host"] for a in payload["actions"]] == ["claude"]
    assert not (fake_home / ".agents").exists()


def test_cli_skill_install_accepts_host_flags(fake_home: Path, canonical: Path, capsys):
    from context_maintainer import cli

    code = cli.main(
        [
            "skill",
            "install",
            "--codex",
            "--home",
            str(fake_home),
            "--canonical",
            str(canonical),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [a["host"] for a in payload["actions"]] == ["codex"]
