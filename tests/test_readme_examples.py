"""Documentation drift guards.

A tool about keeping documentation honest should not ship a stale README.
These tests assert the docs describe what the code actually does.
"""
import re
from pathlib import Path

import pytest

from context_maintainer import contract, doctor
from context_maintainer.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def _subcommands():
    parser = build_parser()
    actions = [
        a
        for a in parser._actions
        if getattr(a, "choices", None) and hasattr(a.choices, "keys")
    ]
    return set(actions[0].choices.keys()) if actions else set()


def test_readme_exists_and_is_substantial(readme: str):
    assert len(readme) > 5000


#: Invoked by the host, never typed by a user. Listing these in the README's
#: command reference would imply they are part of the interface. The features
#: they implement are documented in prose instead.
INTERNAL_SUBCOMMANDS = {"hook"}


def test_readme_documents_all_user_facing_cli_subcommands(readme: str):
    for command in _subcommands() - INTERNAL_SUBCOMMANDS:
        assert re.search(rf"^###\s+`{command}`", readme, re.MULTILINE), command


def test_internal_subcommands_still_have_their_feature_documented(readme: str):
    """`hook` is not a command to type, but the behaviour must be explained."""
    assert "SessionStart" in readme
    assert "hooks/hooks.json" in readme


def test_readme_documents_every_contract_file(readme: str):
    for contract_file in contract.CONTRACT_FILES:
        assert Path(contract_file.relative_path).name in readme


def test_readme_doctor_check_count_matches_implementation(readme: str):
    """The count is easy to get wrong and easy to verify."""
    counts = {int(n) for n in re.findall(r"(\d+) deterministic (?:health )?checks", readme)}
    assert counts, "README should state how many doctor checks exist"
    assert counts == {len(doctor.CHECKS)}, (
        f"README says {counts}, implementation has {len(doctor.CHECKS)}"
    )


def test_readme_states_the_real_python_requirement(readme: str):
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*"(>=?)(\d+\.\d+)"', pyproject)
    assert match, "could not read requires-python from pyproject.toml"
    assert match.group(2) in readme


def test_readme_covers_every_topic_an_open_source_project_needs(readme: str):
    required_sections = (
        "The problem",
        "How it works",
        "Requirements",
        "Installation",
        "Quick start",
        "Commands",
        "The context contract",
        "How Claude Code and Codex share context",
        "How Repomix is used",
        "Structural code analysis",
        "Security model",
        "Evidence model",
        "Testing",
        "Troubleshooting",
        "Uninstalling",
        "Limitations",
        "Future ideas",
        "Contributing",
        "License",
    )
    for section in required_sections:
        assert re.search(rf"^#{{2,3}}\s+{re.escape(section)}", readme, re.MULTILINE), section


def test_readme_documents_both_host_invocations(readme: str):
    assert "/context-maintainer" in readme
    assert "$context-maintainer" in readme


def test_readme_documents_both_skill_install_locations(readme: str):
    assert "~/.claude/skills/context-maintainer" in readme
    assert "~/.agents/skills/context-maintainer" in readme


def test_readme_records_the_rejected_dependency(readme: str):
    """This warning must survive future edits — it is a security decision."""
    assert "codebase-memory-mcp" in readme
    assert "rejected" in readme.lower()


def test_readme_declares_third_party_licenses(readme: str):
    assert "MIT" in readme
    assert "BSD-3-Clause" in readme
    assert "Repomix" in readme


def test_readme_states_limitations_honestly(readme: str):
    limitations = readme.split("## Limitations", 1)[1].split("##", 1)[0]
    assert "Windows" in limitations
    assert len(limitations) > 800, "limitations section should be specific, not a token gesture"


def test_readme_links_to_files_that_exist(readme: str):
    for target in re.findall(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)", readme):
        path = (REPO_ROOT / target.split("#", 1)[0]).resolve()
        assert path.exists(), f"README links to missing path: {target}"


def test_contributing_exists_and_links_resolve():
    assert CONTRIBUTING.is_file()
    text = CONTRIBUTING.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)", text):
        assert (REPO_ROOT / target.split("#", 1)[0]).resolve().exists(), target


def test_contributing_explains_the_cli_skill_boundary():
    text = CONTRIBUTING.read_text(encoding="utf-8").lower()
    assert "boundary" in text
    assert "judgment" in text
