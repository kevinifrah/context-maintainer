"""A bounded index at the head of DECISIONS.md.

Why this file exists: `DECISIONS.md` is the only context document that grows
without limit. Everything else is bounded by something — `STATE.md` is a
snapshot that gets overwritten, `PROJECT.md` and `WORKFLOWS.md` by the project's
actual scope and command count, `ARCHITECTURE.md` sublinearly by the system. The
contract forbids deleting a superseded decision, so `DECISIONS.md` only ever
gets longer, and it is already the largest document in this repository's own
context.

But an agent almost never needs to *read* it. It needs to check whether a
decision exists before reversing one — a lookup, being paid for as a full read.
The index makes that lookup cost a few hundred bytes instead of the whole file.

An index, deliberately, and not a summary. A summary restates claims, so it
drifts on its own and doubles the surface `review` must adjudicate: every claim
would live in two places, each able to go stale without the other. An index
restates only the `## DEC-NNN:` headings that already exist verbatim below it,
so it can never say anything the document does not already say. That is also
why generating it is CLI work rather than the agent's — it is derived structure,
not prose, and a machine can rebuild it exactly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

#: The heading the index lives under.
INDEX_HEADING = "Index"

#: Below this many entries the whole file is cheap enough to read, and an index
#: would cost more attention than it saves.
MIN_ENTRIES = 6

#: Marks the block as machine-owned, so nobody hand-edits what will be
#: regenerated out from under them.
GENERATED_MARKER = (
    "<!-- CONTEXT-MAINTAINER: generated from the headings below. "
    "Edit those, not this. -->"
)

_ENTRY = re.compile(r"^## (DEC-[0-9A-Za-z.\-]+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_STATUS = re.compile(r"^Status:\s*(.+?)\s*$", re.MULTILINE)
_HEADING_LINE = re.compile(r"^## ", re.MULTILINE)


@dataclass(frozen=True)
class Entry:
    identifier: str
    title: str
    status: str


def _plain(title: str) -> str:
    """Titles without markup.

    Backticks are stripped rather than carried over: a path in an index line
    would be read as a citation by `drift.py` and could be reported as dangling
    from a place nobody can fix, since this text is regenerated.
    """
    title = title.replace("`", "")
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
    return re.sub(r"\*+", "", title).strip()


def parse_entries(text: str) -> List[Entry]:
    """Every `## DEC-NNN: Title` entry, in document order, with its status."""
    entries = []
    matches = list(_ENTRY.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        status_match = _STATUS.search(body)
        entries.append(
            Entry(
                identifier=match.group(1),
                title=_plain(match.group(2)),
                status=status_match.group(1).strip() if status_match else "Unknown",
            )
        )
    return entries


def needs_index(entries: List[Entry]) -> bool:
    return len(entries) >= MIN_ENTRIES


def render(entries: List[Entry]) -> str:
    """The index block, heading included, without trailing blank lines."""
    lines = [f"## {INDEX_HEADING}", "", GENERATED_MARKER, ""]
    for entry in entries:
        lines.append(f"- {entry.identifier} ({entry.status}) — {entry.title}")
    return "\n".join(lines)


def extract(text: str) -> Optional[str]:
    """The index block as it currently stands, or None when there is none."""
    marker = f"## {INDEX_HEADING}\n"
    start = text.find(marker)
    if start == -1:
        if not text.startswith(marker.rstrip("\n")):
            return None
        start = 0
    rest = _HEADING_LINE.search(text, start + len(marker))
    end = rest.start() if rest else len(text)
    return text[start:end].rstrip("\n")


def is_current(text: str) -> bool:
    entries = parse_entries(text)
    if not needs_index(entries):
        return extract(text) is None
    return extract(text) == render(entries)


def apply(text: str) -> str:
    """`text` with the index inserted, refreshed, or removed as appropriate."""
    entries = parse_entries(text)
    existing = extract(text)

    if not needs_index(entries):
        if existing is None:
            return text
        return text.replace(existing + "\n\n", "", 1).replace(existing, "", 1)

    block = render(entries)
    if existing is not None:
        return text.replace(existing, block, 1)

    # Insert above the first entry, so the intro paragraph still reads first.
    first = _ENTRY.search(text)
    if first is None:
        return text
    return text[: first.start()] + block + "\n\n" + text[first.start() :]


def refresh(path: Path) -> bool:
    """Rewrite the file's index if it is missing or stale. True if it changed."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    updated = apply(text)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True
