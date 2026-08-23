from context_maintainer import mdsections

SAMPLE = """# Title

Intro text.

## Goal

Ship the thing.

## Problem

### Sub-detail

Nested body.

More problem text.

## Empty
"""


def test_parse_sections_splits_on_h2_headings():
    sections = mdsections.parse_sections(SAMPLE)
    assert set(sections) == {"Goal", "Problem", "Empty"}
    assert sections["Goal"] == "Ship the thing."


def test_parse_sections_handles_nested_h3_within_h2_body():
    sections = mdsections.parse_sections(SAMPLE)
    assert "### Sub-detail" in sections["Problem"]
    assert "More problem text." in sections["Problem"]


def test_parse_sections_returns_empty_string_for_empty_section():
    assert mdsections.parse_sections(SAMPLE)["Empty"] == ""


def test_get_section_returns_none_for_missing_heading():
    assert mdsections.get_section(SAMPLE, "Nonexistent") is None


def test_list_headings_preserves_document_order():
    assert mdsections.list_headings(SAMPLE) == ["Goal", "Problem", "Empty"]


def test_headings_inside_fenced_code_blocks_are_ignored():
    text = """## Real

```markdown
## Fake heading
```

after
"""
    assert mdsections.list_headings(text) == ["Real"]
    assert "## Fake heading" in mdsections.get_section(text, "Real")


def test_tilde_fenced_blocks_are_also_ignored():
    text = """## Real

~~~
## Fake
~~~
"""
    assert mdsections.list_headings(text) == ["Real"]


def test_h1_and_h3_are_not_treated_as_sections():
    text = "# One\n\n### Three\n\n## Two\n\nbody\n"
    assert mdsections.list_headings(text) == ["Two"]


def test_empty_document_yields_no_sections():
    assert mdsections.parse_sections("") == {}
    assert mdsections.list_headings("") == []
