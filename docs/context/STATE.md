# State

<!--
This file is a CURRENT SNAPSHOT, not a chronological log. Overwrite sections
as reality changes; do not append entries. History lives in Git; durable
decisions live in DECISIONS.md.
-->

## Phase

v0.3.0 released and published; awaiting real-world validation. CONFIRMED:
`git tag` shows v0.1.0, v0.2.0, and v0.3.0 (tagged at `b3aebed`), all with
CHANGELOG entries.

## Objective

Closing the loop between "context exists" and "context stays true". v0.2.0
added the `SessionStart` hook (automatic staleness detection across sessions)
and made the per-turn update decision explicit and reportable in `AGENTS.md`
and `SKILL.md`. v0.3.0 went further: `doctor --verify` mechanically checks
documented claims against repository evidence, `manifest.json` tracks
`state_confirmed_at` so STATE.md itself can go stale on a timer (21 days) even
with no code changes, and a `context-check` CI job now fails this repository's
own build on a contradicted claim. CONFIRMED by CHANGELOG [0.3.0], commit
1e3c1aa, `docs/CI.md`, and commits c3a5159/76721f8/0a1e7e2 for the v0.2.0 half.

## Implemented

CONFIRMED by direct reading and by running the test suite (415 tests
passing, `pytest -q`, 2026-08-24):

- Full CLI: `init`, `status`, `sync`, `doctor`, `rebuild`, `audit`, `skill`
  (status/install/uninstall), all with `--json` output.
- The context contract (`AGENTS.md`, `CLAUDE.md`,
  `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md`,
  `.context-maintainer/manifest.json`) plus 18 deterministic `doctor` checks,
  plus (v0.3.0) an optional `doctor --verify` pass that checks documented
  commands/technologies against repository evidence
  (CONFIRMED/UNVERIFIED/CONTRADICTED).
- Time-based STATE staleness (v0.3.0): `manifest.json` records
  `state_confirmed_at`; after 21 days `doctor` and the session hook ask for
  re-confirmation even if nothing else changed.
- A capped, 20-entry context update log (`.context-maintainer/log.md`),
  written by `sync --finalize`/`rebuild --finalize`.
- This repository's own CI now enforces context correctness: a
  `context-check` job runs `doctor --verify --strict` on every push/PR (see
  `docs/CI.md`, DEC-005).
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

None — working tree is clean at `HEAD` (`3010ebe`, "Fix a test that depended
on checkout depth"). CONFIRMED: `git status`, 2026-08-24.

## Blockers

None. CONFIRMED (user, 2026-08-24).

## Next

Validate that generated context is *accurate*, not merely well-structured or
mechanically claim-checked — still the main unproven claim. CONFIRMED
(user, 2026-08-24): this remains the priority even after v0.3.0.

`doctor --verify` (v0.3.0) only mechanically checks documented *commands* and
*technologies* against evidence — it does not catch narrative drift (a stale
test count, a phase/tag that has moved on, a CI job added but never
described). This sync session (2026-08-24) found exactly that kind of drift
across PROJECT/ARCHITECTURE/WORKFLOWS/STATE — none of it caught by
`doctor --verify --strict`, all of it predating this sync's own checkpoint —
which is itself evidence for why the *judgment* layer (an agent actually
reading sections, not just running `doctor`) still matters and is the thing
to keep validating.

Specifically outstanding:
- A cold install by someone with no local checkout has never been exercised;
  every install so far happened on the machine holding the repository.
- Codex plugin-local hooks may not execute yet (openai/codex#16430), so the
  `SessionStart` hook is verified on Claude Code only.
- Whether the `AGENTS.md` "state your conclusion" instruction actually
  changes agent behaviour is unmeasured.
