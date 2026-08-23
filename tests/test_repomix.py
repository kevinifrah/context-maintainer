import os
import stat
from pathlib import Path

import pytest

from context_maintainer import repomix

STUB = """#!/bin/sh
if [ -n "$FAKE_REPOMIX_LOG" ]; then
  echo "$@" >> "$FAKE_REPOMIX_LOG"
fi
if [ "$1" = "--version" ]; then
  echo "$FAKE_REPOMIX_VERSION"
  exit 0
fi
if [ -n "$FAKE_REPOMIX_FAIL" ]; then
  echo "stub failure" >&2
  exit "$FAKE_REPOMIX_FAIL"
fi
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --output) out="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [ -n "$out" ]; then
  mkdir -p "$(dirname "$out")"
  printf '<repomix>stub output</repomix>' > "$out"
fi
exit 0
"""


@pytest.fixture
def no_repomix(monkeypatch):
    """Hide only `repomix` from lookup, leaving git and everything else intact."""
    import shutil as shutil_mod

    real_which = shutil_mod.which

    def fake_which(cmd, *args, **kwargs):
        if cmd == repomix.EXECUTABLE:
            return None
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil_mod, "which", fake_which)
    return fake_which


@pytest.fixture
def fake_repomix(tmp_path, monkeypatch):
    """A stub `repomix` that records its arguments and writes its output file."""
    bindir = tmp_path / "stub-bin"
    bindir.mkdir()
    script = bindir / "repomix"
    script.write_text(STUB, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    log = tmp_path / "repomix-args.log"
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_REPOMIX_LOG", str(log))
    monkeypatch.setenv("FAKE_REPOMIX_VERSION", "1.18.0")
    monkeypatch.delenv("FAKE_REPOMIX_FAIL", raising=False)
    return log


def _args(log: Path) -> str:
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_is_repomix_available_false_when_not_on_path(no_repomix):
    assert not repomix.is_repomix_available()
    assert repomix.get_repomix_version() is None


def test_is_repomix_available_false_with_genuinely_empty_path(tmp_path, monkeypatch):
    """Exercises the real shutil.which lookup, not a patched one."""
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert not repomix.is_repomix_available()


def test_is_repomix_available_true_when_stub_binary_on_path(fake_repomix):
    assert repomix.is_repomix_available()
    assert repomix.get_repomix_version() == "1.18.0"


def test_run_structure_pass_invokes_no_files_flag(git_repo: Path, fake_repomix):
    result = repomix.run_structure_pass(git_repo)
    assert result.succeeded
    assert "--no-files" in _args(fake_repomix)
    assert result.mode == repomix.MODE_STRUCTURE


def test_run_structure_pass_writes_output_into_cache(git_repo: Path, fake_repomix):
    result = repomix.run_structure_pass(git_repo)
    output = Path(result.output_path)
    assert output.exists()
    assert ".context-maintainer/cache/repomix" in output.as_posix()
    assert "stub output" in output.read_text(encoding="utf-8")


def test_run_full_pass_includes_logs_diffs_and_compression(git_repo: Path, fake_repomix):
    result = repomix.run_full_pass(git_repo)
    recorded = _args(fake_repomix)
    assert result.succeeded
    assert "--include-logs" in recorded
    assert "--include-diffs" in recorded
    assert "--compress" in recorded
    assert "--no-files" not in recorded


def test_full_pass_can_omit_logs_and_diffs(git_repo: Path, fake_repomix):
    repomix.run_full_pass(git_repo, include_logs=False, include_diffs=False)
    recorded = _args(fake_repomix)
    assert "--include-logs" not in recorded
    assert "--include-diffs" not in recorded


def test_full_pass_passes_requested_log_count(git_repo: Path, fake_repomix):
    repomix.run_full_pass(git_repo, log_count=7)
    assert "--include-logs-count 7" in _args(fake_repomix)


def test_security_check_is_never_disabled(git_repo: Path, fake_repomix):
    repomix.run_structure_pass(git_repo)
    repomix.run_full_pass(git_repo)
    assert "--no-security-check" not in _args(fake_repomix)


def test_secret_paths_are_explicitly_ignored(git_repo: Path, fake_repomix):
    repomix.run_full_pass(git_repo)
    recorded = _args(fake_repomix)
    assert ".env" in recorded
    assert "*.pem" in recorded
    assert "id_rsa*" in recorded


def test_env_example_files_are_not_excluded(git_repo: Path, fake_repomix):
    """Safe example files stay visible; only real secrets are filtered."""
    repomix.run_full_pass(git_repo)
    assert "!.env.example" in _args(fake_repomix)


def test_unavailable_repomix_returns_degraded_result_without_raising(
    git_repo: Path, no_repomix
):
    result = repomix.run_structure_pass(git_repo)
    assert not result.available
    assert result.degraded_mode
    assert not result.succeeded
    assert "npm install -g repomix" in result.note


def test_failing_repomix_is_reported_as_degraded(git_repo: Path, fake_repomix, monkeypatch):
    monkeypatch.setenv("FAKE_REPOMIX_FAIL", "1")
    result = repomix.run_structure_pass(git_repo)
    assert result.available
    assert result.degraded_mode
    assert result.returncode == 1
    assert "stub failure" in result.stderr
    assert "incomplete" in result.note


def test_result_to_dict_is_json_serializable(git_repo: Path, fake_repomix):
    import json

    payload = repomix.run_structure_pass(git_repo).to_dict()
    assert json.loads(json.dumps(payload))["succeeded"] is True


def test_build_commands_are_pure_and_inspectable(tmp_path: Path):
    structure = repomix.build_structure_command(tmp_path / "out.xml")
    full = repomix.build_full_command(tmp_path / "out.xml")
    assert structure[0] == repomix.EXECUTABLE
    assert "--no-files" in structure
    assert "--compress" in full
    assert "--no-security-check" not in structure + full


def test_cache_dir_is_created_under_context_maintainer(git_repo: Path):
    path = repomix.cache_dir(git_repo)
    assert path.exists()
    assert path.as_posix().endswith(".context-maintainer/cache/repomix")
