# State

<!--
This file is a CURRENT SNAPSHOT, not a chronological log. Overwrite sections
as reality changes; do not append entries. History lives in Git; durable
decisions live in DECISIONS.md.
-->

## Phase

Pre-release polish for v0.1.0. CONFIRMED (user, 2026-08-24), consistent with
the last five commits, which fix marketplace naming, plugin-install
detection, and doc accuracy rather than adding new capability.

## Objective

Preparing for public release: recent work closed out rough edges in the
plugin/marketplace mechanics (marketplace renamed to `kevinifrah` to remove
a naming stutter; `doctor` fixed to recognize a marketplace plugin install,
not just a symlink install; docs updated to point at the real
`kevinifrah/context-maintainer` repository coordinates). CONFIRMED (user,
2026-08-24).

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

Real-world dogfooding: use the tool on actual projects to validate that the
skill-generated context is actually accurate and useful, not just
well-structured — the README explicitly flags this as unproven ("the parts
that depend on a live coding agent... need real-world use to prove out").
CONFIRMED (user, 2026-08-24).

Secondary, lower-priority items visible from this audit, not confirmed as
committed plans:
- README's own "320 passing" test badge is stale (338 actually pass as of
  this audit) — a small doc-accuracy fix.
- README's "Future ideas" section lists further candidates (`doctor
  --repair`, real monorepo support, a CI-integrated drift-check mode,
  Windows support, contract versioning) explicitly as directions, not
  commitments.
