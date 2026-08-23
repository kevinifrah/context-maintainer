#!/usr/bin/env bash
# One-command install for a git checkout.
#
#   ./scripts/install.sh              install for both Claude Code and Codex
#   ./scripts/install.sh --check      report dependencies, change nothing
#   ./scripts/install.sh --dry-run    report what would change, change nothing
#   ./scripts/install.sh --claude     install for Claude Code only
#   ./scripts/install.sh --codex      install for Codex only
#   ./scripts/install.sh --force      replace unrelated content (backs it up first)
#
# Never runs a remote installer and never installs a third-party dependency.
# Missing optional tools are reported with the command you would run yourself.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"

CHECK_ONLY=0
PASSTHROUGH=()

for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=1 ;;
        --dry-run|--force|--claude|--codex) PASSTHROUGH+=("$arg") ;;
        -h|--help)
            sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Try: $0 --help" >&2
            exit 2
            ;;
    esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '  [ok]   %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*"; }
bad()  { printf '  [MISS] %s\n' "$*"; }

# --- pick a python interpreter --------------------------------------------
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
           >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

say "Context Maintainer — dependency check"
say ""

MISSING_REQUIRED=0

if [ -n "$PYTHON" ]; then
    ok "Python $("$PYTHON" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])') ($PYTHON)"
else
    bad "Python 3.9+ not found — required. Install from https://www.python.org/downloads/"
    MISSING_REQUIRED=1
fi

if command -v git >/dev/null 2>&1; then
    ok "$(git --version)"
else
    bad "git not found — required. https://git-scm.com/downloads"
    MISSING_REQUIRED=1
fi

if command -v repomix >/dev/null 2>&1; then
    ok "Repomix $(repomix --version 2>/dev/null || echo '(version unknown)')"
else
    warn "Repomix not found — optional. Audits run in degraded mode."
    warn "       Install with:  npm install -g repomix     (needs Node 22+)"
fi

if command -v mcp-language-server >/dev/null 2>&1; then
    ok "mcp-language-server found (optional structural analysis)"
else
    warn "mcp-language-server not found — optional. Structural claims stay INFERRED."
    warn "       Install with:  go install github.com/isaacphi/mcp-language-server@latest"
fi

say ""

if [ "$MISSING_REQUIRED" -ne 0 ]; then
    say "Install the missing required dependencies above, then re-run."
    exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
    say "Check only — nothing was changed."
    exit 0
fi

# --- install the CLI ------------------------------------------------------
say "Installing the context-maintainer CLI..."
if "$PYTHON" -m pip install -e . >/tmp/cm-pip-install.log 2>&1; then
    ok "CLI installed (editable)"
else
    warn "pip install failed; see /tmp/cm-pip-install.log"
    warn "       The skill still works — it falls back to the bundled package."
fi

# --- install the skill ---------------------------------------------------
say ""
say "Installing the skill..."
"$PYTHON" installer/install.py ${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"}
