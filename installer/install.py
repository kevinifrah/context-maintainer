#!/usr/bin/env python3
"""Install the context-maintainer skill for Claude Code and Codex.

Runs straight from a bare `git clone` — no `pip install` required first.

    python3 installer/install.py --dry-run    # see what would happen
    python3 installer/install.py              # install
    python3 installer/install.py --force      # replace unrelated content (backs it up)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from context_maintainer.installer import main_install  # noqa: E402

if __name__ == "__main__":
    sys.exit(main_install(sys.argv[1:]))
