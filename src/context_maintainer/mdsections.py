"""Minimal Markdown H2 section parser.

Deliberately tiny: the contract only needs to know which `## ` headings exist
and what text sits under each. Headings inside fenced code blocks are ignored.
"""
from __future__ import annotations

from typing import Dict, List, Optional

_FENCES = ("```", "~~~")


def _iter_lines_outside_fences(text: str):
    fence: Optional[str] = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if fence is None:
            for marker in _FENCES:
                if stripped.startswith(marker):
                    fence = marker
                    break
            else:
                yield line, False
                continue
            yield line, True
        else:
            if stripped.startswith(fence):
                fence = None
            yield line, True


def _heading_of(line: str) -> Optional[str]:
    if line.startswith("## ") and not line.startswith("### "):
        return line[3:].strip()
    return None


def list_headings(text: str) -> List[str]:
    """Every H2 heading in document order."""
    headings = []
    for line, in_fence in _iter_lines_outside_fences(text):
        if in_fence:
            continue
        heading = _heading_of(line)
        if heading is not None:
            headings.append(heading)
    return headings


def parse_sections(text: str) -> Dict[str, str]:
    """Map each H2 heading to the raw text beneath it (up to the next H2)."""
    sections: Dict[str, str] = {}
    current: Optional[str] = None
    buffer: List[str] = []

    for line, in_fence in _iter_lines_outside_fences(text):
        heading = None if in_fence else _heading_of(line)
        if heading is not None:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = heading
            buffer = []
        elif current is not None:
            buffer.append(line)

    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def get_section(text: str, heading: str) -> Optional[str]:
    """The body of one H2 section, or None if that heading is absent."""
    return parse_sections(text).get(heading)
