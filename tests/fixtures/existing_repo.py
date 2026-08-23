"""A small but real project whose documentation has fallen behind its code.

The point of this fixture is the contradiction. At the checkpoint, everything
agreed: the project used unittest, and WORKFLOWS.md said so. Afterwards the
project moved to pytest and grew an auth service, and nobody updated the docs.

So a correct audit must conclude "the test command is pytest" from the CI
definition and the test files, and treat the README and WORKFLOWS.md claims as
stale — never the other way round.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .helpers import commit, git, init_repo, write

# --- state at the checkpoint (everything consistent) ----------------------

PYPROJECT_UNITTEST = """[project]
name = "widget-service"
version = "0.1.0"
description = "Turns widget orders into fulfilment jobs."
requires-python = ">=3.9"
dependencies = ["flask"]
"""

MAIN_PY = '''"""Widget service entry point."""


def create_app():
    """Build the Flask application."""
    from flask import Flask

    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
'''

TEST_UNITTEST = '''import unittest

from app.main import create_app


class HealthTests(unittest.TestCase):
    def test_health_returns_ok(self):
        client = create_app().test_client()
        self.assertEqual(client.get("/health").json["status"], "ok")
'''

CI_UNITTEST = """name: CI

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e .
      - run: python -m unittest discover
"""

README_UNITTEST = """# widget-service

Turns widget orders into fulfilment jobs.

## Running tests

    python -m unittest discover
"""

#: Hand-written at the checkpoint, correct at the time, stale afterwards.
WORKFLOWS_AT_CHECKPOINT = """# Workflows

How to work on this repository correctly.

## Development

    pip install -e .

## Testing

    python -m unittest discover

## Build

Not applicable — this is a service, not a distributable package.

## Deploy

Unknown — no deployment configuration found.

## Notes

Python 3.9 or newer is required.
"""

# --- changes made after the checkpoint (docs deliberately not updated) ----

PYPROJECT_PYTEST = """[project]
name = "widget-service"
version = "0.2.0"
description = "Turns widget orders into fulfilment jobs."
requires-python = ">=3.9"
dependencies = ["flask", "pyjwt"]

[project.optional-dependencies]
dev = ["pytest>=7"]
"""

TEST_PYTEST = '''from app.main import create_app


def test_health_returns_ok():
    client = create_app().test_client()
    assert client.get("/health").json["status"] == "ok"
'''

CI_PYTEST = """name: CI

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest -q
"""

AUTH_PY = '''"""Token verification for the widget service."""

import jwt


def verify_token(token, secret):
    """Return the token payload, or None when it does not verify."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
'''

MAIN_PY_WITH_AUTH = '''"""Widget service entry point."""

from app.auth import verify_token


def create_app(secret="dev-only"):
    """Build the Flask application."""
    from flask import Flask, request

    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/orders")
    def orders():
        payload = verify_token(request.headers.get("Authorization", ""), secret)
        if payload is None:
            return {"error": "unauthorized"}, 401
        return {"orders": []}

    return app
'''


@dataclass
class ExistingRepoFixture:
    root: Path
    checkpoint_commit: str
    head_commit: str
    #: Says `python -m unittest` while CI and the tests say pytest.
    stale_workflows_path: Path
    stale_readme_path: Path
    #: Added after the checkpoint; absent from ARCHITECTURE.md.
    new_module_path: Path

    @property
    def confirmed_test_command(self) -> str:
        """What an evidence-based audit should conclude."""
        return "pytest -q"

    @property
    def stale_test_command(self) -> str:
        """What the stale documentation still claims."""
        return "python -m unittest discover"


def make_existing_repo_with_stale_doc(
    tmp_path: Path, name: str = "existing-project"
) -> ExistingRepoFixture:
    from context_maintainer import contract, manifest as manifest_mod, scaffold

    root = init_repo(tmp_path / name)

    # --- five commits of consistent history -------------------------------
    write(root, "README.md", README_UNITTEST)
    write(root, "pyproject.toml", PYPROJECT_UNITTEST)
    commit(root, "Add project manifest")

    write(root, "src/app/__init__.py", "")
    write(root, "src/app/main.py", MAIN_PY)
    commit(root, "Add widget service entry point")

    write(root, "tests/test_main.py", TEST_UNITTEST)
    commit(root, "Add health check tests")

    write(root, ".github/workflows/ci.yml", CI_UNITTEST)
    commit(root, "Run unittest in CI")

    write(root, ".env.example", "SECRET_KEY=replace-me\nDATABASE_URL=\n")
    commit(root, "Document required configuration")

    # --- initialize context here, then hand-write accurate workflows ------
    scaffold.write_contract_files(root, project_name=name)
    write(root, "docs/context/WORKFLOWS.md", WORKFLOWS_AT_CHECKPOINT)
    manifest_mod.save_manifest(
        manifest_mod.default_manifest("existing"), root / contract.MANIFEST_PATH
    )
    checkpoint = commit(root, "Add project context")

    # Checkpoint at the commit that contains the context, as sync --finalize
    # would record it.
    loaded = manifest_mod.load_manifest(root / contract.MANIFEST_PATH)
    manifest_mod.update_checkpoint(loaded, checkpoint)
    manifest_mod.save_manifest(loaded, root / contract.MANIFEST_PATH)

    # --- reality moves on; documentation does not -------------------------
    write(root, "pyproject.toml", PYPROJECT_PYTEST)
    write(root, "tests/test_main.py", TEST_PYTEST)
    write(root, ".github/workflows/ci.yml", CI_PYTEST)
    commit(root, "Switch test runner from unittest to pytest")

    write(root, "src/app/auth.py", AUTH_PY)
    write(root, "src/app/main.py", MAIN_PY_WITH_AUTH)
    head = commit(root, "Add token authentication to orders endpoint")

    return ExistingRepoFixture(
        root=root,
        checkpoint_commit=checkpoint,
        head_commit=head,
        stale_workflows_path=root / "docs/context/WORKFLOWS.md",
        stale_readme_path=root / "README.md",
        new_module_path=root / "src/app/auth.py",
    )
