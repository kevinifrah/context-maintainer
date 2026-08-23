"""The skill is prose-as-instructions, so these tests validate packaging and
internal consistency — above all that the written contract cannot drift away
from the contract the CLI enforces.
"""
import re
from pathlib import Path

import pytest

from context_maintainer import contract

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skill" / "context-maintainer"
SKILL_MD = SKILL_DIR / "SKILL.md"

#: Anthropic's documented authoring budget for a skill body.
MAX_SKILL_BODY_LINES = 500
MAX_DESCRIPTION_CHARS = 1024

REQUIRED_REFERENCES = (
    "context-contract.md",
    "evidence-policy.md",
    "audit-protocol.md",
    "sync-policy.md",
    "mcp-companion.md",
)


def _split_frontmatter(text: str):
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    _, frontmatter, body = text.split("---", 2)
    return frontmatter.strip(), body.strip()


def _parse_frontmatter(frontmatter: str) -> dict:
    """Minimal single-level YAML parse — enough for the portable field set."""
    fields = {}
    key = None
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([a-zA-Z][\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
        elif key:  # folded continuation line
            fields[key] += " " + line.strip()
    return fields


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text) -> dict:
    return _parse_frontmatter(_split_frontmatter(skill_text)[0])


def test_skill_md_exists():
    assert SKILL_MD.is_file()


def test_skill_frontmatter_has_required_fields(frontmatter):
    assert "name" in frontmatter
    assert "description" in frontmatter


def test_skill_name_matches_directory_name(frontmatter):
    assert frontmatter["name"] == SKILL_DIR.name == "context-maintainer"


def test_skill_name_is_valid_per_open_standard(frontmatter):
    name = frontmatter["name"]
    assert len(name) <= 64
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name


def test_skill_description_under_1024_chars(frontmatter):
    assert 0 < len(frontmatter["description"]) <= MAX_DESCRIPTION_CHARS


def test_skill_description_mentions_all_five_commands(frontmatter):
    description = frontmatter["description"].lower()
    for command in ("init", "status", "sync", "doctor", "rebuild"):
        assert command in description, command


def test_skill_uses_only_portable_frontmatter_fields(frontmatter):
    """Non-portable fields break packaging outside Claude Code."""
    portable = {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
    assert set(frontmatter) <= portable, set(frontmatter) - portable


def test_skill_body_under_line_budget(skill_text):
    body = _split_frontmatter(skill_text)[1]
    assert len(body.splitlines()) <= MAX_SKILL_BODY_LINES


def test_skill_documents_every_command(skill_text):
    for command in ("init", "status", "sync", "doctor", "rebuild"):
        assert re.search(rf"^##\s+{command}\b", skill_text, re.MULTILINE), command


def test_skill_references_all_exist_on_disk():
    for reference in REQUIRED_REFERENCES:
        assert (SKILL_DIR / "references" / reference).is_file(), reference


def test_skill_links_to_every_reference(skill_text):
    for reference in REQUIRED_REFERENCES:
        assert reference in skill_text, reference


def test_no_reference_file_is_orphaned(skill_text):
    for path in (SKILL_DIR / "references").glob("*.md"):
        assert path.name in skill_text, f"{path.name} is not linked from SKILL.md"


def test_wrapper_script_exists_and_is_executable():
    script = SKILL_DIR / "scripts" / "cm.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "cm.sh must be executable"


def test_skill_states_the_cli_versus_judgment_split(skill_text):
    lowered = skill_text.lower()
    assert "never ask the cli to reason" in lowered


def test_skill_forbids_reading_secret_values(skill_text):
    assert "never read secret values" in skill_text.lower()


def test_skill_requires_claude_md_to_import_agents_md(skill_text):
    assert "@AGENTS.md" in skill_text


# --- the drift guard that actually matters -------------------------------


def _parse_contract_reference() -> dict:
    """Extract `### <path>` → required sections from context-contract.md."""
    text = (SKILL_DIR / "references" / "context-contract.md").read_text(encoding="utf-8")
    documented = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+(\S+)\s*$", line)
        if heading:
            current = heading.group(1)
            documented[current] = []
            continue
        required = re.match(r"^Required sections:\s*(.*)$", line)
        if required and current:
            value = required.group(1).strip()
            if value.startswith("(none"):
                documented[current] = []
            else:
                documented[current] = [s.strip() for s in value.split(",") if s.strip()]
    return documented


def test_skill_context_contract_matches_python_contract_module():
    """The prose contract and the enforced contract must never diverge."""
    documented = _parse_contract_reference()
    expected = {
        cf.relative_path: list(cf.required_sections) for cf in contract.CONTRACT_FILES
    }
    assert documented == expected


def test_contract_reference_documents_every_contract_file():
    documented = _parse_contract_reference()
    for contract_file in contract.CONTRACT_FILES:
        assert contract_file.relative_path in documented


def test_contract_reference_mentions_the_placeholder_sentinel_convention(skill_text):
    assert contract.PLACEHOLDER_SENTINEL in skill_text
