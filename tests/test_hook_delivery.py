"""How a hook notice reaches its reader — the half the other hook tests miss.

v0.5.0 shipped a `PreCompact` hook whose only channel to a reader was plain
stdout, which the compaction machinery does not inject as context. A manual
`/compact` happens to echo it in the slash command's result line; an automatic
compaction — the case the hook exists for — does not. Every unit test passed
either way, because every unit test called the notice *builder*.

So these tests assert delivery rather than wording:

- `PreCompact` must emit a JSON envelope carrying `systemMessage`, the
  `PreCompact` channel that does not depend on how compaction was triggered.
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


# --- Stop: blocks the turn, and only under all three guards ---------------


def _worked(repo: Path) -> Path:
    """A settled repository where source has been committed past the checkpoint."""
    write(repo, "src/parser.py", "def parse():\n    return None\n")
    commit(repo, "Add the parser")
    return repo


def test_stop_blocks_when_committed_work_has_outrun_the_documents(tmp_path: Path):
    """The whole point: the turn does not end with the documents behind."""
    repo = _worked(_settled(tmp_path))

    code, out = run_hook(repo, "stop", {"stop_hook_active": False})

    assert code == 0
    assert out.strip(), "committed work outran the docs and the hook said nothing"
    envelope = json.loads(out)
    assert envelope["decision"] == "block"
    assert "context" in envelope["reason"].lower()


def test_stop_is_silent_when_it_has_already_blocked_this_turn(tmp_path: Path):
    """`stop_hook_active` is the loop guard. Without it a block never ends."""
    repo = _worked(_settled(tmp_path))

    code, out = run_hook(repo, "stop", {"stop_hook_active": True})

    assert code == 0
    assert out == ""


def test_stop_is_silent_when_the_turn_already_ruled_on_context(tmp_path: Path):
    """Saying "no context update needed" is a complete answer, and ends the turn."""
    repo = _worked(_settled(tmp_path))

    for message in (
        "Fixed the parser bug. No context update needed.",
        "Updated docs/context/STATE.md to record the new component.",
        "Ran context-maintainer sync --finalize after the change.",
    ):
        code, out = run_hook(
            repo, "stop", {"stop_hook_active": False, "last_assistant_message": message}
        )
        assert code == 0, message
        assert out == "", f"blocked a turn that already ruled: {message!r}"


def test_stop_does_not_nag_about_work_that_is_merely_uncommitted(tmp_path: Path):
    """Mid-task is the normal state. Blocking on it is DEC-004's objection."""
    repo = _settled(tmp_path)
    write(repo, "src/parser.py", "def parse():\n    return None\n")

    code, out = run_hook(repo, "stop", {"stop_hook_active": False})

    assert code == 0
    assert out == "", "blocked on an uncommitted edit; this would fire every turn"


def test_stop_is_silent_on_a_settled_repository(tmp_path: Path):
    code, out = run_hook(_settled(tmp_path), "stop", {"stop_hook_active": False})

    assert code == 0
    assert out == ""


def test_stop_ignores_context_only_commits(tmp_path: Path):
    """A sync must not make the next turn demand another sync."""
    repo = _settled(tmp_path)
    state = repo / "docs/context/STATE.md"
    state.write_text(state.read_text(encoding="utf-8") + "\nA note.\n", encoding="utf-8")
    commit(repo, "Record a note")

    code, out = run_hook(repo, "stop", {"stop_hook_active": False})

    assert code == 0
    assert out == ""


def test_stop_asks_once_per_commit_not_once_per_turn(tmp_path: Path):
    """The defect the first real run exposed, and the reason v0.6.0 waited.

    The trigger — a commit past the checkpoint — stays true until someone runs
    `sync --finalize`. `stop_hook_active` only guards within a turn, so the hook
    blocked, was answered, and blocked again on the next turn, and answering it
    never helped. That is DEC-004's nagging objection arriving through the side
    door.
    """
    repo = _worked(_settled(tmp_path))

    _code, first = run_hook(repo, "stop", {"stop_hook_active": False})
    assert first.strip(), "expected the first turn to ask"

    # The agent answers, as it did in the real trace.
    _code, answered = run_hook(
        repo,
        "stop",
        {"stop_hook_active": False, "last_assistant_message": "No context update needed."},
    )
    assert answered == ""

    # Every turn after that stays quiet, even saying nothing about context.
    for turn in range(3):
        _code, later = run_hook(
            repo,
            "stop",
            {"stop_hook_active": False, "last_assistant_message": "Here is the answer."},
        )
        assert later == "", f"asked again on turn {turn + 2} after being answered"


def test_stop_asks_again_once_new_work_is_committed(tmp_path: Path):
    """The memory is per commit, not permanent — or it would silence itself."""
    repo = _worked(_settled(tmp_path))
    run_hook(
        repo,
        "stop",
        {"stop_hook_active": False, "last_assistant_message": "No context update needed."},
    )

    write(repo, "src/writer.py", "def write():\n    return None\n")
    commit(repo, "Add the writer")

    _code, out = run_hook(repo, "stop", {"stop_hook_active": False})

    assert out.strip(), "new committed work did not earn a fresh ruling"


def test_stop_writes_nothing_outside_the_disposable_cache(tmp_path: Path):
    """The one write is a marker in `cache/`. Nothing else may move.

    Not a relaxation of DEC-007: a marker recording "someone was asked about
    commit X" claims nothing about whether the documents are correct, which is
    the thing DEC-007 forbids asserting without review.
    """
    repo = _worked(_settled(tmp_path))
    before = _fingerprint(repo)

    run_hook(
        repo,
        "stop",
        {"stop_hook_active": False, "last_assistant_message": "No context update needed."},
    )

    after = _fingerprint(repo)
    changed = {
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    }
    assert changed == {".context-maintainer/cache/last-context-ruling"}, changed


def test_stop_writes_nothing_at_all_when_it_blocks(tmp_path: Path):
    """Asking costs nothing on disk. Only an answer is worth remembering."""
    repo = _worked(_settled(tmp_path))
    before = _fingerprint(repo)

    run_hook(repo, "stop", {"stop_hook_active": False})

    assert _fingerprint(repo) == before
