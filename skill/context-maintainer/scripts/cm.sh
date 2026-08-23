#!/bin/sh
# Resilient wrapper for the context-maintainer CLI.
#
# Prefers the installed console script; falls back to the module, which works
# from a plain `pip install -e .` or a source checkout on PYTHONPATH.
set -eu

if command -v context-maintainer >/dev/null 2>&1; then
  exec context-maintainer "$@"
fi

for python in python3 python; do
  if command -v "$python" >/dev/null 2>&1; then
    if "$python" -c "import context_maintainer" >/dev/null 2>&1; then
      exec "$python" -m context_maintainer "$@"
    fi
  fi
done

cat >&2 <<'EOF'
context-maintainer is not available.

Install it from the Context Maintainer checkout:
  pip install -e .

Then re-run. See the project README for full installation instructions.
EOF
exit 127
