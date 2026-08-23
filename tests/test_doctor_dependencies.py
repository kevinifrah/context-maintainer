"""Doctor's dependency checks: degraded is acceptable, dishonest is not."""
import json
from pathlib import Path

import pytest

from context_maintainer import contract, doctor, gitutil, manifest as manifest_mod, scaffold

from conftest import write

from test_repomix import fake_repomix, no_repomix  # noqa: F401  (fixtures)


def _initialize(root: Path, mode: str = "blank"):
    scaffold.write_contract_files(root, project_name=root.name)
    created = manifest_mod.default_manifest(mode, commit=gitutil.get_head_commit(root))
    manifest_mod.save_manifest(created, root / contract.MANIFEST_PATH)


def _result(report: doctor.DoctorReport, name: str) -> doctor.CheckResult:
    return next(r for r in report.results if r.name == name)


def test_doctor_warns_degraded_mode_when_repomix_missing(
    blank_repo: Path, no_repomix  # noqa: F811
):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    result = _result(report, "repomix_available")
    assert result.status == doctor.WARN
    assert "degraded" in result.message.lower()


def test_doctor_passes_repomix_check_when_available(
    blank_repo: Path, fake_repomix  # noqa: F811
):
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    result = _result(report, "repomix_available")
    assert result.status == doctor.PASS
    assert "1.18.0" in result.message


def test_doctor_never_fails_solely_for_missing_repomix(
    blank_repo: Path, no_repomix  # noqa: F811
):
    """A missing optional dependency must never read as a broken repository."""
    _initialize(blank_repo)
    for contract_file in contract.CONTRACT_FILES:
        path = blank_repo / contract_file.relative_path
        text = path.read_text(encoding="utf-8").replace(
            contract.PLACEHOLDER_SENTINEL, "documented"
        )
        path.write_text(text, encoding="utf-8")
    report = doctor.run_all_checks(blank_repo)
    assert report.overall != doctor.FAIL


def test_doctor_never_fails_for_missing_mcp_companion(
    blank_repo: Path, monkeypatch  # noqa: F811
):
    monkeypatch.setenv("HOME", str(blank_repo / "fake-home"))
    _initialize(blank_repo)
    report = doctor.run_all_checks(blank_repo)
    result = _result(report, "mcp_language_server")
    assert result.status == doctor.PASS
    assert "not configured (optional)" in result.message


def test_doctor_notes_mcp_language_server_when_configured(blank_repo: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(blank_repo / "fake-home"))
    _initialize(blank_repo)
    write(
        blank_repo,
        ".mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "language-server": {
                        "command": "mcp-language-server",
                        "args": ["--workspace", ".", "--lsp", "gopls"],
                    }
                }
            }
        ),
    )
    report = doctor.run_all_checks(blank_repo)
    result = _result(report, "mcp_language_server")
    assert result.status == doctor.PASS
    assert "configured" in result.message
    assert "language-server" in result.message


def test_dependency_checks_do_not_write_anything(
    blank_repo: Path, no_repomix  # noqa: F811
):
    _initialize(blank_repo)
    before = sorted(p.as_posix() for p in blank_repo.rglob("*"))
    doctor.run_all_checks(blank_repo)
    assert sorted(p.as_posix() for p in blank_repo.rglob("*")) == before
