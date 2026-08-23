"""Both hosts must be able to load the one canonical skill directory.

Layout under test:

    skill/context-maintainer/
    ├── .claude-plugin/plugin.json      Claude Code plugin manifest
    ├── .codex-plugin/plugin.json       Codex plugin manifest
    ├── SKILL.md                        canonical; also serves plain-skill discovery
    ├── references/  scripts/
    └── skills/context-maintainer/      Codex's demonstrated plugin layout
        └── SKILL.md -> ../../SKILL.md  (symlink; never a second copy)
"""
import json
from pathlib import Path

import pytest

from context_maintainer import __version__, pluginspec

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skill" / "context-maintainer"
CLAUDE_MANIFEST = SKILL_DIR / pluginspec.CLAUDE_MANIFEST_RELPATH
CODEX_MANIFEST = SKILL_DIR / pluginspec.CODEX_MANIFEST_RELPATH
NESTED_SKILL_DIR = SKILL_DIR / "skills" / "context-maintainer"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_both_manifests_exist():
    assert CLAUDE_MANIFEST.is_file()
    assert CODEX_MANIFEST.is_file()


def test_manifests_are_valid_json():
    assert isinstance(_load(CLAUDE_MANIFEST), dict)
    assert isinstance(_load(CODEX_MANIFEST), dict)


def test_claude_plugin_manifest_has_required_name_field():
    assert _load(CLAUDE_MANIFEST)["name"] == "context-maintainer"


def test_codex_plugin_manifest_has_required_fields():
    data = _load(CODEX_MANIFEST)
    for field in ("name", "version", "description", "author", "interface"):
        assert field in data, field
    assert data["author"]["name"]


def test_codex_interface_has_every_universally_present_field():
    """Mirrors the fields present in all 180 openai/plugins marketplace entries."""
    interface = _load(CODEX_MANIFEST)["interface"]
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ):
        assert field in interface, field


def test_both_manifests_agree_on_version_with_package():
    assert _load(CLAUDE_MANIFEST)["version"] == __version__
    assert _load(CODEX_MANIFEST)["version"] == __version__


def test_manifests_on_disk_match_pluginspec():
    """Regenerating from pluginspec must be a no-op — no silent drift."""
    assert _load(CLAUDE_MANIFEST) == pluginspec.claude_manifest()
    assert _load(CODEX_MANIFEST) == pluginspec.codex_manifest()


def test_validate_reports_no_problems_for_shipped_layout():
    assert pluginspec.validate(SKILL_DIR) == []


def test_validate_detects_a_version_mismatch():
    problems = pluginspec.validate(SKILL_DIR, version="9.9.9")
    assert any("does not match package version" in p for p in problems)


def test_validate_detects_missing_manifest(tmp_path: Path):
    problems = pluginspec.validate(tmp_path)
    assert any("missing manifest" in p for p in problems)


def test_manifest_directories_contain_only_plugin_json():
    """Component dirs must live at plugin root, never inside the manifest dir."""
    for manifest_dir in (SKILL_DIR / ".claude-plugin", SKILL_DIR / ".codex-plugin"):
        assert [p.name for p in manifest_dir.iterdir()] == ["plugin.json"]


def test_canonical_skill_md_is_at_package_root():
    """Root SKILL.md is what makes plain-skill discovery work on both hosts."""
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert not (SKILL_DIR / "SKILL.md").is_symlink()


def test_codex_manifest_declares_the_skills_directory():
    assert _load(CODEX_MANIFEST)["skills"] == "./skills/"


def test_nested_codex_skill_is_a_symlink_not_a_copy():
    """One canonical workflow definition — never two files to keep in sync."""
    nested = NESTED_SKILL_DIR / "SKILL.md"
    assert nested.is_symlink(), "nested SKILL.md must be a symlink"
    assert nested.resolve() == (SKILL_DIR / "SKILL.md").resolve()


def test_nested_codex_skill_resolves_to_identical_content():
    nested = NESTED_SKILL_DIR / "SKILL.md"
    assert nested.read_text(encoding="utf-8") == (
        SKILL_DIR / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_nested_references_and_scripts_resolve_from_the_codex_layout():
    """SKILL.md links to references/ relatively, so they must resolve there too."""
    assert (NESTED_SKILL_DIR / "references" / "audit-protocol.md").is_file()
    assert (NESTED_SKILL_DIR / "scripts" / "cm.sh").is_file()


def test_nested_skill_directory_name_matches_skill_name():
    """Codex derives the skill name from its directory."""
    assert NESTED_SKILL_DIR.name == "context-maintainer"


def test_no_duplicate_skill_md_content_in_repository():
    """Exactly one real SKILL.md file; everything else is a link to it."""
    real = [
        p
        for p in SKILL_DIR.rglob("SKILL.md")
        if not p.is_symlink()
    ]
    assert len(real) == 1, [str(p) for p in real]
