#!/bin/sh
# Stop hook: when a turn is about to end and committed work has outrun the
# context documents, ask the agent to rule on whether project reality changed.
#
# This is the enforcement path DEC-004 left open. It rejected a per-turn Stop
# hook because the sync policy's own default answer is "update nothing", so
# asking every turn would say "nothing needed" most of the time and train the
# dismissal it was built to prevent. That argument holds against asking every
# turn. It does not hold against asking once, at a moment the repository can
# point to — a commit past the context checkpoint. See DEC-011.
#
# Same contract as the other hooks, with one addition and one exception:
#   - Always exit 0. A hook must never disrupt a session.
#   - Print nothing unless there is something worth acting on.
#   - Never block twice for the same turn. The host sets `stop_hook_active`
#     once this hook has already blocked; the CLI reads it and goes quiet,
#     which is what keeps a block from becoming a loop.
#   - Never block twice for the same *commit* either. This is the addition, and
#     it is not optional: the trigger stays true until someone runs `sync
#     --finalize`, so without it the hook asks every turn and answering it does
#     not help. The first real run did exactly that.
#   - The exception: to remember an answer it writes one disposable marker under
#     .context-maintainer/cache/, which is gitignored. Never a context document,
#     never the manifest, never an attestation.
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

# What this prints is a JSON envelope carrying `decision: "block"` and a
# `reason`, which is the only Stop channel that reaches the agent: the host
# hands the reason back and the turn continues instead of ending. Plain text
# here would go to the debug log and nowhere else, the mistake DEC-009 records.
# The host's hook input JSON is left on stdin for the CLI to read — it needs
# `stop_hook_active` and `last_assistant_message` from it.
sh "$launcher" hook stop 2>/dev/null || true

exit 0
