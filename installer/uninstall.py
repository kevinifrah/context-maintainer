#!/usr/bin/env python3
"""Remove the context-maintainer skill from Claude Code and Codex.

Runs straight from a bare `git clone` — no `pip install` required first.
Only removes symlinks that point at this checkout; anything else needs --force.

    python3 installer/uninstall.py --dry-run
    python3 installer/uninstall.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from context_maintainer.installer import main_uninstall  # noqa: E402

if __name__ == "__main__":
    sys.exit(main_uninstall(sys.argv[1:]))
