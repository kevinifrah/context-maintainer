"""The DECISIONS.md index: making a lookup cost a lookup.

`DECISIONS.md` is the only context document that grows without limit — the
contract forbids deleting a superseded decision — and an agent almost never
needs to read it, only to check whether a decision exists before reversing one.

Two properties decide whether the index is safe to generate automatically:

1. It says nothing the document does not already say. It is built from the
   `## DEC-NNN:` headings, so it cannot drift into a second, contradictory
   account the way a summary would.
2. It is cheap. If it grew with the entries it indexes, it would be a copy.
"""
from pathlib import Path

import pytest

from context_maintainer import decisionindex as di

HEADER = """# Decisions

Durable, ADR-style record of decisions worth preserving.
"""


def _entry(number: int, title: str = "Something was decided", status: str = "Accepted") -> str:
    return f"""
## DEC-{number:03d}: {title}

Status: {status}

Decision: Do the thing.

Why: It was better than not doing the thing.
"""


def _doc(count: int, **kwargs) -> str:
    return HEADER + "".join(_entry(i, **kwargs) for i in range(1, count + 1))


# --- parsing -------------------------------------------------------------


def test_entries_are_read_with_their_status():
    entries = di.parse_entries(_doc(2, status="Superseded"))
    assert [e.identifier for e in entries] == ["DEC-001", "DEC-002"]
    assert {e.status for e in entries} == {"Superseded"}


def test_status_is_reported_when_an_entry_omits_it():
    """A malformed entry must not crash the index that has to list it."""
    text = HEADER + "\n## DEC-001: No status here\n\nDecision: something.\n"
    assert di.parse_entries(text)[0].status == "Unknown"


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Rejected `some/path.py` as a backend", "Rejected some/path.py as a backend"),
        ("Use **Postgres** for sessions", "Use Postgres for sessions"),
        ("See [the RFC](https://example.com/rfc)", "See the RFC"),
    ],
)
def test_markup_is_stripped_from_index_titles(title: str, expected: str):
    """A backticked path in an index line would be read as a citation by
    `drift.py`, and reported as dangling from text nobody can fix by hand."""
    index = di.render(di.parse_entries(_doc(1) + _entry(2, title)))
    assert expected in index
    assert "`" not in index


# --- when it applies -----------------------------------------------------


def test_a_short_file_gets_no_index():
    """Below the threshold the whole file is cheaper to read than to route."""
    text = _doc(di.MIN_ENTRIES - 1)
    assert di.apply(text) == text
    assert di.is_current(text)


def test_an_index_appears_once_the_file_is_worth_routing():
    text = di.apply(_doc(di.MIN_ENTRIES))
    assert f"## {di.INDEX_HEADING}" in text
    assert di.is_current(text)


def test_the_index_sits_above_the_first_entry_and_below_the_intro():
    text = di.apply(_doc(di.MIN_ENTRIES))
    assert text.index("Durable, ADR-style") < text.index("## Index")
    assert text.index("## Index") < text.index("## DEC-001")


def test_an_index_that_is_no_longer_warranted_is_removed():
    """Entries can be pruned; a stub index should not outlive the need."""
    text = di.apply(_doc(di.MIN_ENTRIES))
    shrunk = HEADER + di.extract(text) + "\n\n" + _entry(1)
    assert "## Index" not in di.apply(shrunk)


# --- the properties that make it safe to generate ------------------------


def test_the_index_lists_every_entry():
    entries = di.parse_entries(_doc(12))
    index = di.render(entries)
    for entry in entries:
        assert entry.identifier in index


def test_each_indexed_entry_costs_a_bounded_line():
    """The invariant that makes this an index and not a copy.

    Stated per entry rather than as a share of the file, because the share
    depends on how verbose the entries are — and it is precisely the verbose
    file the index is meant to save you from reading.
    """
    text = di.apply(_doc(20))
    index = di.extract(text)
    overhead = len(di.render([]).encode())
    per_entry = (len(index.encode()) - overhead) / 20
    assert per_entry < 120, per_entry


def test_the_index_is_a_small_fraction_of_a_realistically_sized_file():
    body = "\n".join(f"Consideration {i}: " + ("detail " * 30) for i in range(8))
    text = di.apply(HEADER + "".join(
        f"\n## DEC-{i:03d}: A decision\n\nStatus: Accepted\n\n{body}\n"
        for i in range(1, 21)
    ))
    assert len(di.extract(text).encode()) < len(text.encode()) * 0.05


def test_the_index_says_nothing_the_headings_do_not():
    """The property that distinguishes an index from a summary: it introduces
    no claim of its own, so `review` has one place to adjudicate, not two."""
    entries = di.parse_entries(_doc(di.MIN_ENTRIES, title="Adopted a queue"))
    for line in di.render(entries).splitlines():
        if not line.startswith("- "):
            continue
        identifier, _, rest = line[2:].partition(" (")
        title = rest.split(") — ", 1)[1]
        assert any(e.identifier == identifier and e.title == title for e in entries)


def test_regeneration_is_idempotent():
    once = di.apply(_doc(di.MIN_ENTRIES))
    assert di.apply(once) == once


def test_a_stale_index_is_replaced_not_appended():
    text = di.apply(_doc(di.MIN_ENTRIES))
    grown = text + _entry(di.MIN_ENTRIES + 1, "A later decision")
    refreshed = di.apply(grown)
    assert refreshed.count(f"## {di.INDEX_HEADING}") == 1
    assert f"DEC-{di.MIN_ENTRIES + 1:03d}" in di.extract(refreshed)


def test_a_hand_edited_index_is_detected_as_stale():
    text = di.apply(_doc(di.MIN_ENTRIES))
    tampered = text.replace("DEC-001", "DEC-999", 1)
    assert not di.is_current(tampered)


# --- the file-level helper -----------------------------------------------


def test_refresh_reports_whether_it_changed_anything(tmp_path: Path):
    path = tmp_path / "DECISIONS.md"
    path.write_text(_doc(di.MIN_ENTRIES), encoding="utf-8")
    assert di.refresh(path) is True
    assert di.refresh(path) is False


def test_refresh_is_silent_on_a_missing_file(tmp_path: Path):
    assert di.refresh(tmp_path / "nope.md") is False


# --- wiring --------------------------------------------------------------


def test_sync_finalize_regenerates_the_index(git_repo: Path):
    """The index is only maintenance-free if something actually maintains it."""
    from fixtures import make_blank_repo, run_cli
    from fixtures.helpers import commit

    repo = make_blank_repo(git_repo.parent / "wired")
    run_cli(repo, ["init"])
    path = repo / "docs/context/DECISIONS.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "".join(
            _entry(i, f"Decision {i}") for i in range(2, 2 + di.MIN_ENTRIES)
        ),
        encoding="utf-8",
    )
    commit(repo, "Record several decisions")
    assert not di.is_current(path.read_text(encoding="utf-8"))

    run_cli(repo, ["sync", "--finalize"])
    assert di.is_current(path.read_text(encoding="utf-8"))
