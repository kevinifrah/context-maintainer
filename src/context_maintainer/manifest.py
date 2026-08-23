"""Read/write `.context-maintainer/manifest.json`.

The manifest is machine metadata only — schema version, mode, timestamps, the
last verified commit, and tool versions. Product knowledge belongs in
`docs/context/`, so unknown keys are rejected rather than quietly stored.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__

SCHEMA_VERSION = 1

_REQUIRED_KEYS = ("schema_version", "mode", "initialized_at")
_ALLOWED_KEYS = (
    "schema_version",
    "mode",
    "initialized_at",
    "last_synced_at",
    "last_verified_commit",
    "context_maintainer_version",
    "repomix_version",
    "mcp_language_server_configured",
)
_VALID_MODES = ("blank", "existing")


class ManifestError(Exception):
    """The manifest is missing, unparseable, or structurally invalid."""


@dataclass
class Manifest:
    schema_version: int = SCHEMA_VERSION
    mode: str = "blank"
    initialized_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_verified_commit: Optional[str] = None
    context_maintainer_version: str = __version__
    repomix_version: Optional[str] = None
    mcp_language_server_configured: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_manifest(
    mode: str,
    commit: Optional[str] = None,
    now: Optional[str] = None,
    repomix_version: Optional[str] = None,
) -> Manifest:
    timestamp = now or utc_now()
    return Manifest(
        schema_version=SCHEMA_VERSION,
        mode=mode,
        initialized_at=timestamp,
        last_synced_at=timestamp,
        last_verified_commit=commit,
        context_maintainer_version=__version__,
        repomix_version=repomix_version,
    )


def validate_manifest_dict(data: Any) -> List[str]:
    """Return a list of human-readable problems; empty means valid."""
    problems: List[str] = []
    if not isinstance(data, dict):
        return ["manifest root must be a JSON object"]

    for key in _REQUIRED_KEYS:
        if key not in data:
            problems.append(f"missing required key: {key}")

    for key in data:
        if key not in _ALLOWED_KEYS:
            problems.append(
                f"unexpected key: {key} (the manifest holds metadata only, "
                "not project knowledge)"
            )

    version = data.get("schema_version")
    if "schema_version" in data and not isinstance(version, int):
        problems.append("schema_version must be an integer")
    elif isinstance(version, int) and version > SCHEMA_VERSION:
        problems.append(
            f"schema_version {version} is newer than supported {SCHEMA_VERSION}"
        )

    mode = data.get("mode")
    if "mode" in data and mode not in _VALID_MODES:
        problems.append(f"mode must be one of {_VALID_MODES}, got {mode!r}")

    commit = data.get("last_verified_commit")
    if commit is not None and not isinstance(commit, str):
        problems.append("last_verified_commit must be a string or null")

    configured = data.get("mcp_language_server_configured")
    if configured is not None and not isinstance(configured, bool):
        problems.append("mcp_language_server_configured must be a boolean or null")

    return problems


def from_dict(data: Dict[str, Any]) -> Manifest:
    problems = validate_manifest_dict(data)
    if problems:
        raise ManifestError("; ".join(problems))
    known = {k: v for k, v in data.items() if k in _ALLOWED_KEYS}
    return Manifest(**known)


def load_manifest(path: Path) -> Manifest:
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc
    return from_dict(raw)


def save_manifest(manifest: Manifest, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")


def update_checkpoint(
    manifest: Manifest,
    commit: Optional[str],
    now: Optional[str] = None,
) -> Manifest:
    """Advance the sync checkpoint, leaving everything else intact."""
    manifest.last_verified_commit = commit
    manifest.last_synced_at = now or utc_now()
    manifest.context_maintainer_version = __version__
    return manifest
