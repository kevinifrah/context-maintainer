#!/bin/sh
# SessionStart hook: report stale project context to the agent.
#
# Contract this script must honour, because it runs at the start of every
# session in every project:
#   - Always exit 0. A hook must never disrupt a session.
#   - Never write anything. Detection only.
#   - Print nothing unless there is something worth acting on. A hook that
#     speaks every time gets ignored.
#
# Plain stdout from a SessionStart hook is added to the agent's context on both
# Claude Code and Codex, so a plain-text notice is all that is needed — no JSON
# envelope, nothing to escape.
set -u

# ${CLAUDE_PLUGIN_ROOT} is set by Claude Code and aliased by Codex. Fall back to
# this script's own location so the hook also works from a plain checkout.
plugin_root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-}}"
if [ -z "$plugin_root" ]; then
    script_path=$0
    case $script_path in
        */*) script_dir=${script_path%/*} ;;
        *)   script_dir=. ;;
    esac
    plugin_root=$(cd "$script_dir/.." 2>/dev/null && pwd -P) || exit 0
fi

launcher="$plugin_root/scripts/cm.sh"
[ -x "$launcher" ] || exit 0

# `hook session-start` prints a notice only when action is warranted, and is
# itself written to never raise. Suppress stderr so a broken environment stays
# invisible rather than alarming, and swallow any non-zero status.
sh "$launcher" hook session-start 2>/dev/null || true

exit 0
