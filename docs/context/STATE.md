# State

<!--
This file is a CURRENT SNAPSHOT, not a chronological log. Overwrite sections
as reality changes; do not append entries. History lives in Git; durable
decisions live in DECISIONS.md.
-->

## Phase

v0.2.0 released and published; awaiting real-world validation. CONFIRMED:
`git tag` shows v0.1.0 and v0.2.0, both with GitHub releases; CHANGELOG
records both.

## Objective

Closing the loop between "context exists" and "context stays true". v0.2.0
added the `SessionStart` hook (automatic staleness detection across sessions)
and made the per-turn update decision explicit and reportable in `AGENTS.md`
and `SKILL.md`. CONFIRMED by commits c3a5159, 76721f8, 0a1e7e2.

## Implemented

CONFIRMED by direct reading and by running the test suite (338 tests
passing, `pytest -q`, 2026-08-24):

- Full CLI: `init`, `status`, `sync`, `doctor`, `rebuild`, `audit`, `skill`
  (status/install/uninstall), all with `--json` output.
- The context contract (`AGENTS.md`, `CLAUDE.md`,
  `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md`,
  `.context-maintainer/manifest.json`) plus 17 deterministic `doctor` checks.
- Staged Repomix evidence gathering (`--structure-only` / `--full`) with an
  explicit, non-silent degraded mode when Repomix is absent.
- Optional `mcp-language-server` companion detection.
- Symlink-based installer/uninstaller with conflict-safe behavior
  (refuses to clobber an unrelated directory without `--force`, which then
  backs it up first) and marketplace-plugin-install detection for both
  hosts.
- Dual-host packaging: Claude Code plugin (`.claude-plugin/`) and Codex
  plugin (`.codex-plugin/`), both sourced from one canonical
  `skill/context-maintainer/` directory.
- Comprehensive README, CONTRIBUTING.md, docs/INSTALL.md, docs/TESTING.md.

## In Progress

None — the user confirmed (2026-08-24) there is no in-progress work beyond
what's already committed; working tree is clean at `HEAD` (`92132b1`) aside
from this `init` run's own output.

## Blockers

None. CONFIRMED (user, 2026-08-24).

## Next

Validate that generated context is *accurate*, not merely well-structured —
still the main unproven claim, and now testable since both a blank and an
existing fixture workflow are documented in `docs/TESTING.md`.

Specifically outstanding:
- A cold install by someone with no local checkout has never been exercised;
  every install so far happened on the machine holding the repository.
- Codex plugin-local hooks may not execute yet (openai/codex#16430), so the
  `SessionStart` hook is verified on Claude Code only.
- Whether the `AGENTS.md` "state your conclusion" instruction actually
  changes agent behaviour is unmeasured.
