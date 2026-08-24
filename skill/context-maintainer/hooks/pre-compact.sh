#!/bin/sh
# PreCompact hook: remind the agent to record what this session learned, before
# the context window is compacted and the unwritten part of it is lost.
#
# Same contract as session-start.sh, because it runs in every project:
#   - Always exit 0. A hook must never disrupt a session.
#   - Never write anything. Detection only. DEC-004 rejected mechanical
#     re-stamping for a reason that applies harder mid-task: marking context
#     reviewed when nobody reviewed it is worse than leaving it visibly stale.
#   - Print nothing unless there is something worth acting on. A hook that
#     speaks at every compaction gets skimmed at the one that mattered.
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

# `hook pre-compact` prints a notice only when action is warranted, and is
# itself written to never raise. Suppress stderr so a broken environment stays
# invisible rather than alarming, and swallow any non-zero status.
sh "$launcher" hook pre-compact 2>/dev/null || true

exit 0
