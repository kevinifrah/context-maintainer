#!/bin/sh
# Run the context-maintainer CLI, however it happens to be available.
#
# Three situations must all work:
#   1. Installed with pip      -> the `context-maintainer` console script is on PATH
#   2. Installed as a plugin   -> no pip; the Python package sits next to this
#                                 script inside the plugin directory
#   3. A plain git checkout    -> same as (2)
#
# Because both hosts copy only the plugin directory when installing a plugin,
# the bundled package is always a sibling of this script's parent. That is what
# makes a zero-pip plugin install work.
#
# Path handling uses shell parameter expansion rather than dirname/readlink so
# that even the failure message survives a badly broken PATH.
set -eu

# Resolve this script's real location, following symlinks (the skill directory
# is typically reached through one).
script_path=$0
while [ -L "$script_path" ]; do
    link=$(readlink "$script_path" 2>/dev/null) || break
    case $link in
        /*) script_path=$link ;;
        *)  script_path=${script_path%/*}/$link ;;
    esac
done

case $script_path in
    */*) script_dir=${script_path%/*} ;;
    *)   script_dir=. ;;
esac
script_dir=$(cd "$script_dir" && pwd -P)
plugin_root=$(cd "$script_dir/.." && pwd -P)

# 1. Prefer a pip-installed console script.
if command -v context-maintainer >/dev/null 2>&1; then
    exec context-maintainer "$@"
fi

# 2. Fall back to the bundled package. PEP 540: force UTF-8 so paths with
#    non-ASCII characters do not crash on a cp1252 default (Windows).
export PYTHONUTF8=1
if [ -d "$plugin_root/context_maintainer" ]; then
    PYTHONPATH="$plugin_root${PYTHONPATH:+:$PYTHONPATH}"
    export PYTHONPATH
fi

# Probe interpreters rather than trusting the first name that exists: on
# Windows Git Bash `python3` is often a Microsoft Store stub that exits
# non-zero in a non-TTY subprocess, so it must fall through to `python`.
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" \
            >/dev/null 2>&1 \
        && "$candidate" -c "import context_maintainer" >/dev/null 2>&1; then
        exec "$candidate" -m context_maintainer "$@"
    fi
done

# Built-ins only from here down — external commands may be unavailable.
printf '%s\n' "context-maintainer could not be run." >&2
printf '%s\n' "" >&2
printf '%s\n' "Looked for:" >&2
printf '%s\n' "  - a 'context-maintainer' command on PATH" >&2
printf '%s\n' "  - a bundled package at $plugin_root/context_maintainer" >&2
printf '%s\n' "    runnable with python3 (>= 3.9)" >&2
printf '%s\n' "" >&2
printf '%s\n' "Fixes:" >&2
printf '%s\n' "  - from a checkout:  pip install -e ." >&2
printf '%s\n' "  - or ensure python3 3.9+ is installed and on PATH" >&2
printf '%s\n' "" >&2
printf '%s\n' "See the project README for installation instructions." >&2
exit 127
