"""How a hook notice reaches its reader — the half the other hook tests miss.

v0.5.0 shipped a `PreCompact` hook that ran, built a correct notice, printed it,
and was read by nobody: the host writes `PreCompact` stdout to its debug log and
shows it nowhere else. Every unit test passed, because every unit test called
the notice *builder*.

So these tests assert delivery rather than wording:

- `PreCompact` must emit a JSON envelope carrying `systemMessage`, the only
  `PreCompact` channel that reaches a human.
- `SessionStart` must emit plain text, because that is what the host adds to the
  agent's context — a JSON envelope there would be injected verbatim as prose.
- The unrecorded-work report belongs to `source == "compact"` and to no other
  session start, or it nags in every repository with a dirty working tree.

A notice nobody receives is indistinguishable from a hook that never ran, which
is why these are separated out and named for the delivery, not the message.
"""
import io
import json
import sys
from pathlib import Path

import pytest

from context_maintainer import cli, contract

from fixtures import make_blank_repo, run_cli
from fixtures.helpers import commit, in_dir, write


def _settled(tmp_path: Path) -> Path:
    """A repository whose context is filled in, committed, and attested."""
    repo = make_blank_repo(tmp_path)
    run_cli(repo, ["init"])
    for contract_file in contract.CONTRACT_FILES:
        path = repo / contract_file.relative_path
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                contract.PLACEHOLDER_SENTINEL, "documented"
            ),
            encoding="utf-8",
        )
    commit(repo, "Add context")
    run_cli(repo, ["sync", "--finalize"])
    return repo


def run_hook(root: Path, event: str, payload=None, raw_stdin=None):
    """Run the hook the way a host does: JSON on stdin, notice on stdout."""
    if raw_stdin is None:
        raw_stdin = "" if payload is None else json.dumps(payload)

    captured = io.StringIO()
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(raw_stdin), captured
    try:
        with in_dir(root):
            code = cli.main(["hook", event])
    finally:
        sys.stdin, sys.stdout = real_stdin, real_stdout
    return code, captured.getvalue()


# --- PreCompact: a JSON envelope, or nothing -----------------------------


def test_pre_compact_emits_a_json_envelope_with_a_system_message(tmp_path: Path):
    """The regression. Plain text here is written to a debug log and lost."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")

    code, out = run_hook(repo, "pre-compact")

    assert code == 0
    assert out.strip(), "the hook had something to say and said nothing"
    envelope = json.loads(out)
    assert "systemMessage" in envelope
    assert "uncommitted" in envelope["systemMessage"]


def test_pre_compact_output_is_never_bare_text(tmp_path: Path):
    """Whatever it prints must be parseable, or the host discards it."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "x = 1\n")

    _code, out = run_hook(repo, "pre-compact")

    assert not out.startswith("Context Maintainer")
    json.loads(out)


def test_pre_compact_prints_nothing_at_all_when_there_is_nothing_to_say(
    tmp_path: Path,
):
    """Not an empty envelope — nothing. Silence is the common case."""
    code, out = run_hook(_settled(tmp_path), "pre-compact")

    assert code == 0
    assert out == ""


# --- SessionStart: plain text, and only compact reports unrecorded work ---


def test_session_start_reports_unrecorded_work_after_a_compaction(tmp_path: Path):
    """`SessionStart` is the only compaction-adjacent event the agent reads."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")

    code, out = run_hook(repo, "session-start", {"source": "compact"})

    assert code == 0
    assert "compacted" in out
    assert "uncommitted" in out


def test_session_start_stays_quiet_about_a_dirty_tree_at_normal_startup(
    tmp_path: Path,
):
    """Otherwise it speaks in every repository anyone is mid-edit in."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")

    for source in ("startup", "resume", "clear", "fork", "", "unrecognised"):
        code, out = run_hook(repo, "session-start", {"source": source})
        assert code == 0, source
        assert out == "", f"spoke about a dirty tree on source={source!r}"


def test_session_start_output_is_plain_text_not_a_json_envelope(tmp_path: Path):
    """The inverse regression: JSON here is injected as prose, verbatim."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "x = 1\n")

    _code, out = run_hook(repo, "session-start", {"source": "compact"})

    assert out.startswith("Context Maintainer")
    with pytest.raises(ValueError):
        json.loads(out)


def test_a_compacted_session_hears_about_stale_context_too(tmp_path: Path):
    """Both failures can be true at once, and one must not hide the other."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "x = 1\n")
    placeholder = repo / "docs/context/STATE.md"
    placeholder.write_text(
        placeholder.read_text(encoding="utf-8") + f"\n{contract.PLACEHOLDER_SENTINEL}\n",
        encoding="utf-8",
    )

    _code, out = run_hook(repo, "session-start", {"source": "compact"})

    assert "compacted" in out
    assert "placeholder" in out


# --- stdin is a host's channel, and hosts are inconsistent ----------------


@pytest.mark.parametrize(
    "raw",
    ["", "   \n", "not json at all", "[]", "null", '{"source": null}', "123"],
)
def test_unusable_stdin_is_ignored_rather_than_fatal(tmp_path: Path, raw: str):
    """A hook must never disrupt a session, whatever the host sends."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "x = 1\n")

    code, out = run_hook(repo, "session-start", raw_stdin=raw)

    assert code == 0
    assert out == ""


def test_reading_stdin_does_not_consume_a_terminal(tmp_path: Path, monkeypatch):
    """Run by hand there is no piped stdin; waiting on it would hang."""

    class Terminal(io.StringIO):
        def isatty(self):
            return True

        def read(self, *_args):  # pragma: no cover - must never be reached
            raise AssertionError("read a tty; this would block a real session")

    monkeypatch.setattr(sys, "stdin", Terminal())
    assert cli._hook_payload() == {}


# --- the contract every hook shares --------------------------------------


def _fingerprint(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.stat().st_mtime_ns
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git/" not in str(p.relative_to(root))
    }


@pytest.mark.parametrize(
    "event,payload",
    [("pre-compact", None), ("session-start", {"source": "compact"})],
)
def test_delivering_a_notice_writes_nothing(tmp_path: Path, event, payload):
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "x = 1\n")
    before = _fingerprint(repo)

    run_hook(repo, event, payload)

    assert _fingerprint(repo) == before
