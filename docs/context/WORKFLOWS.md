# Workflows

How to work on this repository correctly. Never invent a command — if it isn't confirmed, mark it unknown.

## Development

```bash
git clone https://github.com/kevinifrah/context-maintainer.git context-maintainer
cd context-maintainer
python3 -m venv .venv
source .venv/bin/activate      # Windows not supported in v1; use WSL
pip install -e ".[dev]"
```

Requires Python 3.9+ and Git only — no Node, no Repomix, no network access
needed for development or tests (Repomix is exercised through a stub binary
in tests). To try the CLI/skill loop against a throwaway repo rather than a
real project:

```bash
mkdir /tmp/scratch && cd /tmp/scratch && git init
git commit --allow-empty -m "Initial commit"
context-maintainer init
context-maintainer doctor
```

CONFIRMED: CONTRIBUTING.md "Development setup".

## Testing

```bash
pytest -q
```

Confirmed by running it directly: **415 tests pass** as of 2026-08-24
(README states "300+ automated tests", which still holds). No network access, no Node, no real Repomix
required; installer tests run against a fake `$HOME` so the real
`~/.claude`/`~/.agents` are never touched. Coverage includes the
blank/existing detection heuristic, Git edge cases (unborn HEAD, renames,
deletions), manifest validation, all 17 `doctor` checks, the Repomix wrapper
including its degraded path, installer conflict handling, skill/plugin
packaging, and end-to-end lifecycles against two fixtures (one deliberately
containing stale docs that contradict the code, to exercise "prefer the
source" behavior). CONFIRMED: README "Testing", CONTRIBUTING.md "Testing
conventions", direct test run.

CI runs the same command across a matrix — see Build below.

## Build

No separate "build" step beyond the standard editable install used for
development (`pip install -e ".[dev]"`); packaging is `setuptools` via
`pyproject.toml`, with the package sourced from
`skill/context-maintainer/` (`[tool.setuptools.packages.find] where =
["skill/context-maintainer"]`) so templates ship as package data. UNKNOWN:
no CI step or script builds a distributable wheel/sdist or publishes to
PyPI — `context-maintainer` does not appear to be published there yet;
only `pip install -e .` from a checkout is confirmed. CONFIRMED (packaging
config): `pyproject.toml`.

## Deploy

There is no deployed service — this is a CLI + Agent Skill installed locally
by each user. Two install paths, both CONFIRMED (README "Installation"):

- **Plugin marketplace** (no clone needed):
  `/plugin marketplace add kevinifrah/context-maintainer` then
  `/plugin install context-maintainer@kevinifrah` (Claude Code); analogous
  `codex plugin marketplace add` / `codex plugin add` for Codex. The CLI is
  bundled inside the plugin directory, since both hosts copy only that
  subdirectory on install.
- **From a checkout**: `./scripts/install.sh [--claude|--codex|--check]`,
  which symlinks the checkout into `~/.claude/skills/context-maintainer`
  and/or `~/.agents/skills/context-maintainer` and installs the
  `context-maintainer` console script. Symlinks (not copies) so `git pull`
  updates both hosts at once.

CI (`.github/workflows/ci.yml`) has two jobs, both on `push` to `main` and
every `pull_request`:

- `test`: `pytest -q` across Python 3.9 and 3.12 on `ubuntu-latest`. Uses a
  full checkout (`fetch-depth: 0`) because several tests reason about commit
  history; a test that needs the recorded context checkpoint commit skips
  itself on a shallow clone instead of failing.
- `context-check` (added v0.3.0): `context-maintainer doctor --verify
  --strict` on a full checkout — this repository's own context documents must
  not contradict the repository, or the build fails. See `docs/CI.md` for
  exactly which checks can fail the build versus which stay advisory
  (environmental checks like Repomix/MCP-companion availability never do).

There is no separate release/publish workflow found — release is currently a
manual git-tag-and-marketplace-update process (INFERRED from the absence of a
publish CI job and the recent marketplace-naming commit).

## Notes

- Uninstall: `python3 installer/uninstall.py [--dry-run]` (removes only
  symlinks pointing at your checkout; anything else needs `--force` and is
  backed up first) and `pip uninstall context-maintainer`.
- `doctor --strict` treats warnings as failures. Since v0.3.0 it is wired
  into `ci.yml`'s `context-check` job, combined with `--verify` (see Deploy
  above and `docs/CI.md`).
- Troubleshooting for common install/symlink/command-name issues is
  documented at length in README "Troubleshooting" — check there before
  re-deriving a fix.
- The CLI/skill boundary and contract are enforced by tests: changing
  `contract.py` requires updating `references/context-contract.md` in
  lockstep (a test parses the prose and asserts equality), and changing a
  template requires it to still satisfy the contract. See CONTRIBUTING.md
  before touching either.
