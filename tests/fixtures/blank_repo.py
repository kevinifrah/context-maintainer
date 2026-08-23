"""A repository that is effectively empty.

Deliberately not literally empty: it has the files a brand-new project always
picks up — README, LICENSE, .gitignore, and a couple of trivial commits — so it
proves those alone never make a project look "existing".
"""
from __future__ import annotations

from pathlib import Path

from .helpers import commit, init_repo, write

README = """# scratch

A placeholder README, not yet describing anything.
"""


def make_blank_repo(tmp_path: Path, name: str = "blank-project") -> Path:
    root = init_repo(tmp_path / name)
    write(root, "README.md", README)
    write(root, "LICENSE", "MIT License\n")
    write(root, ".gitignore", "__pycache__/\n.venv/\n")
    commit(root, "Initial commit")

    write(root, "README.md", README + "\nStill nothing here.\n")
    commit(root, "Expand README")
    return root
