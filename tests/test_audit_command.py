import hashlib
import json
from pathlib import Path

import pytest

from context_maintainer import cli, contract

from conftest import write

from test_repomix import fake_repomix, no_repomix  # noqa: F401  (fixtures)


@pytest.fixture
def in_repo(monkeypatch):
    def _chdir(root: Path):
        monkeypatch.chdir(root)
        return root

    return _chdir


def _run_json(argv, capsys):
    code = cli.main(argv + ["--json"])
    return code, json.loads(capsys.readouterr().out)


def _fingerprint(root: Path) -> dict:
    prints = {}
    for path in contract.all_required_paths(root):
        if path.exists():
            prints[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return prints


def test_audit_structure_only_writes_cache_file_and_reports_json(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    code, payload = _run_json(["audit"], capsys)
    assert code == 0
    assert payload["repomix"]["mode"] == "structure"
    assert payload["repomix"]["succeeded"] is True
    assert payload["degraded_mode"] is False
    assert Path(payload["repomix"]["output_path"]).exists()


def test_audit_full_pass_includes_logs_and_diffs_flags_in_report(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    code, payload = _run_json(["audit", "--full"], capsys)
    assert code == 0
    command = " ".join(payload["repomix"]["command"])
    assert "--include-logs" in command
    assert "--include-diffs" in command
    assert "--compress" in command


def test_audit_full_pass_honors_no_logs_and_no_diffs(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    _, payload = _run_json(["audit", "--full", "--no-logs", "--no-diffs"], capsys)
    command = " ".join(payload["repomix"]["command"])
    assert "--include-logs" not in command
    assert "--include-diffs" not in command


def test_audit_reports_degraded_mode_true_when_repomix_unavailable(
    existing_repo: Path, in_repo, no_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    code, payload = _run_json(["audit"], capsys)
    assert code == 0  # degraded, but not a hard failure
    assert payload["degraded_mode"] is True
    assert payload["repomix"]["available"] is False


def test_audit_degraded_output_explains_installation(
    existing_repo: Path, in_repo, no_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    cli.main(["audit"])
    out = capsys.readouterr().out
    assert "DEGRADED MODE" in out
    assert "npm install -g repomix" in out
    assert "Do not describe the audit as complete" in out


def test_audit_does_not_modify_any_contract_files(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    cli.main(["init"])
    capsys.readouterr()
    before = _fingerprint(existing_repo)
    cli.main(["audit", "--full"])
    capsys.readouterr()
    assert _fingerprint(existing_repo) == before


def test_audit_works_before_initialization(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    """The skill audits first and materializes context afterwards."""
    in_repo(existing_repo)
    code, payload = _run_json(["audit"], capsys)
    assert code == 0
    assert not (existing_repo / contract.MANIFEST_PATH).exists()


def test_audit_creates_cache_gitignore(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    cli.main(["audit"])
    capsys.readouterr()
    ignore = existing_repo / contract.CACHE_DIR / ".gitignore"
    assert ignore.exists()
    assert "*" in ignore.read_text(encoding="utf-8")


def test_audit_reports_mcp_companion_absent_by_default(
    existing_repo: Path, in_repo, fake_repomix, capsys, monkeypatch  # noqa: F811
):
    monkeypatch.setenv("HOME", str(existing_repo / "fake-home"))
    in_repo(existing_repo)
    _, payload = _run_json(["audit"], capsys)
    assert payload["mcp_language_server"]["configured"] is False
    assert "definition" in payload["mcp_language_server"]["tools"]


def test_audit_detects_configured_mcp_companion(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    write(
        existing_repo,
        ".mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "language-server": {
                        "command": "mcp-language-server",
                        "args": ["--workspace", ".", "--lsp", "pyright-langserver"],
                    }
                }
            }
        ),
    )
    in_repo(existing_repo)
    _, payload = _run_json(["audit"], capsys)
    assert payload["mcp_language_server"]["configured"] is True


def test_init_records_repomix_version_in_manifest(
    existing_repo: Path, in_repo, fake_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    cli.main(["init"])
    capsys.readouterr()
    data = json.loads((existing_repo / contract.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert data["repomix_version"] == "1.18.0"
    assert data["mcp_language_server_configured"] is False


def test_init_records_null_repomix_version_when_unavailable(
    existing_repo: Path, in_repo, no_repomix, capsys  # noqa: F811
):
    in_repo(existing_repo)
    cli.main(["init"])
    capsys.readouterr()
    data = json.loads((existing_repo / contract.MANIFEST_PATH).read_text(encoding="utf-8"))
    assert data["repomix_version"] is None
