import json
from pathlib import Path

import pytest

from context_maintainer import __version__, manifest as manifest_mod


def test_default_manifest_has_schema_version_and_mode():
    created = manifest_mod.default_manifest("blank")
    assert created.schema_version == manifest_mod.SCHEMA_VERSION
    assert created.mode == "blank"
    assert created.initialized_at
    assert created.context_maintainer_version == __version__


def test_save_then_load_round_trips_exactly(tmp_path: Path):
    path = tmp_path / "manifest.json"
    created = manifest_mod.default_manifest("existing", commit="a" * 40)
    manifest_mod.save_manifest(created, path)
    loaded = manifest_mod.load_manifest(path)
    assert loaded.to_dict() == created.to_dict()


def test_save_creates_parent_directories(tmp_path: Path):
    path = tmp_path / ".context-maintainer" / "manifest.json"
    manifest_mod.save_manifest(manifest_mod.default_manifest("blank"), path)
    assert path.exists()


def test_validate_rejects_unknown_keys():
    problems = manifest_mod.validate_manifest_dict(
        {
            "schema_version": 1,
            "mode": "blank",
            "initialized_at": "2026-01-01T00:00:00+00:00",
            "project_goal": "should not live here",
        }
    )
    assert any("project_goal" in p for p in problems)


def test_validate_rejects_missing_required_key():
    problems = manifest_mod.validate_manifest_dict({"schema_version": 1, "mode": "blank"})
    assert any("initialized_at" in p for p in problems)


def test_validate_rejects_invalid_mode():
    problems = manifest_mod.validate_manifest_dict(
        {
            "schema_version": 1,
            "mode": "sideways",
            "initialized_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert any("mode" in p for p in problems)


def test_validate_rejects_future_schema_version():
    problems = manifest_mod.validate_manifest_dict(
        {
            "schema_version": manifest_mod.SCHEMA_VERSION + 5,
            "mode": "blank",
            "initialized_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert any("newer than supported" in p for p in problems)


def test_validate_accepts_a_default_manifest():
    created = manifest_mod.default_manifest("existing")
    assert manifest_mod.validate_manifest_dict(created.to_dict()) == []


def test_load_raises_manifest_error_on_corrupt_json(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(manifest_mod.ManifestError):
        manifest_mod.load_manifest(path)


def test_load_raises_manifest_error_when_missing(tmp_path: Path):
    with pytest.raises(manifest_mod.ManifestError):
        manifest_mod.load_manifest(tmp_path / "absent.json")


def test_load_raises_manifest_error_on_unknown_key(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "blank",
                "initialized_at": "2026-01-01T00:00:00+00:00",
                "architecture_notes": "nope",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(manifest_mod.ManifestError):
        manifest_mod.load_manifest(path)


def test_update_checkpoint_advances_commit_and_timestamp():
    created = manifest_mod.default_manifest("existing", commit="a" * 40, now="2026-01-01T00:00:00+00:00")
    manifest_mod.update_checkpoint(created, "b" * 40, now="2026-02-02T00:00:00+00:00")
    assert created.last_verified_commit == "b" * 40
    assert created.last_synced_at == "2026-02-02T00:00:00+00:00"
    assert created.initialized_at == "2026-01-01T00:00:00+00:00"


def test_manifest_holds_no_product_knowledge_fields():
    fields = set(manifest_mod.default_manifest("blank").to_dict())
    for forbidden in ("goal", "problem", "architecture", "components", "decisions"):
        assert forbidden not in fields
