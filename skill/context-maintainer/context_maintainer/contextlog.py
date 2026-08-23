"""A deliberately small, capped log of context updates.

Why this exists: `STATE.md` is a snapshot and gets overwritten, `DECISIONS.md`
holds only decisions, and Git buries context syncs among every other commit. So
nothing answered "when was context last updated, and why?" without archaeology.

Why it lives in `.context-maintainer/` rather than `docs/context/`: it is tool
bookkeeping, not project knowledge. Putting it under `docs/context/` would add a
sixth file to the context contract and break `doctor` for every existing
project.

It is committed, not cached — a teammate pulling the repository should see it.
It is capped, so it can never become the sprawling changelog that `STATE.md` is
explicitly forbidden from being.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

LOG_RELPATH = ".context-maintainer/log.md"

#: Oldest entries are pruned beyond this. Small on purpose: the point is "what
#: happened lately", and Git holds the rest.
MAX_ENTRIES = 20

#: Truncate a note rather than let one entry dominate the file.
MAX_NOTE_CHARS = 300

_HEADER = """# Context update log

Newest first. Capped at {max_entries} entries — older history lives in Git.
Written by `context-maintainer sync --finalize` / `rebuild --finalize`.
""".format(max_entries=MAX_ENTRIES)

_ENTRY_PATTERN = re.compile(r"^## ", re.MULTILINE)


@dataclass
class LogEntry:
    timestamp: str
    commit: Optional[str]
    files: List[str]
    note: Optional[str] = None

    def render(self) -> str:
        short = self.commit[:8] if self.commit else "(no commit)"
        lines = [f"## {self.timestamp} — {short}"]
        if self.files:
            lines.append("")
            lines.append("Updated: " + ", ".join(self.files))
        if self.note:
            lines.append("")
            lines.append(self.note)
        return "\n".join(lines)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log_path(root: Path) -> Path:
    return Path(root) / LOG_RELPATH


def _split_entries(text: str) -> List[str]:
    """Existing entry blocks, newest first, without the file header."""
    if "## " not in text:
        return []
    _, _, body = text.partition("## ")
    blocks = ("## " + body).split("\n## ")
    return [b if b.startswith("## ") else "## " + b for b in blocks if b.strip()]


def append_entry(
    root: Path,
    commit: Optional[str],
    files: Sequence[str],
    note: Optional[str] = None,
    now: Optional[str] = None,
) -> Optional[Path]:
    """Prepend an entry, pruning to MAX_ENTRIES. Returns the path, or None.

    Returns None when there is nothing worth recording — no context files
    changed and no note supplied — so routine no-op syncs leave no trace.
    """
    files = [f for f in files if f]
    if not files and not note:
        return None

    if note and len(note) > MAX_NOTE_CHARS:
        note = note[: MAX_NOTE_CHARS - 1].rstrip() + "…"

    entry = LogEntry(
        timestamp=now or utc_now(), commit=commit, files=list(files), note=note
    )

    path = log_path(root)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    blocks = _split_entries(existing)[: MAX_ENTRIES - 1]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _HEADER + "\n" + "\n\n".join([entry.render(), *blocks]).rstrip() + "\n",
        encoding="utf-8",
    )
    return path


def read_recent(root: Path, limit: int = 3) -> List[str]:
    """The most recent entry blocks, newest first, for `status` to summarise."""
    path = log_path(root)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [b.strip() for b in _split_entries(text)[:limit]]


def entry_count(root: Path) -> int:
    path = log_path(root)
    if not path.exists():
        return 0
    try:
        return len(_ENTRY_PATTERN.findall(path.read_text(encoding="utf-8")))
    except OSError:
        return 0
