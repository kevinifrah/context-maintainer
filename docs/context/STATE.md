# State

<!--
This file is a CURRENT SNAPSHOT, not a chronological log. Overwrite sections
as reality changes; do not append entries. History lives in Git; durable
decisions live in DECISIONS.md.
-->

## Phase

v0.6.0 is committed on `main` and installed as the working plugin, but is
deliberately **not tagged**: the newest tag is v0.5.1. Tagging waits until the
`Stop` hook is proven in real use, because v0.5.0 shipped a `PreCompact` hook
that passed every unit test and reached nobody (DEC-009).

v0.4.0's drift detection and `review` worklist are dogfooded here; v0.5.0 added
a `PreCompact` hook, a convention for recording abandoned approaches, and size
budgets with a generated `DECISIONS.md` index; v0.5.1 fixed how those hook
notices are delivered; v0.6.0 adds the `Stop` hook (DEC-011) and
`COMPLETED_INTENT` detection (DEC-010). CONFIRMED: `git tag`, `CHANGELOG.md`,
`pyproject.toml`.

## Objective

Making the context maintain itself. v0.2.0 added the `SessionStart` hook and
made the per-turn update decision explicit. v0.3.0 made claims *checkable*:
`doctor --verify`, time-based STATE staleness, and a `context-check` CI job
that fails the build on a contradicted claim.

v0.4.0 closes the gap those left. Checkable was not enough — this repository
drifted anyway (a stale test count, a phase that had moved on, a CI job
described nowhere) while `doctor --verify --strict` stayed green, because
contradiction-checking only judges claims that exist, in a vocabulary it
already knows. So v0.4.0 detects drift by *evidence movement* instead of by
judging prose: `review` parses the citations the documents already carry,
resolves them, and reports the claims whose evidence has moved since anyone
confirmed them. The agent is now told to adjudicate that list, in `SKILL.md`,
`references/sync-policy.md`, and `AGENTS.md`.

CONFIRMED by CHANGELOG [0.4.0], `drift.py`, `tests/test_drift.py`, DEC-006,
and by running `review` against this repository.

## Implemented

CONFIRMED by direct reading and by running the test suite (`pytest -q`,
2026-08-24; the count is in WORKFLOWS.md "Testing"):

- Full CLI: `init`, `status`, `sync`, `review`, `doctor`, `rebuild`, `audit`,
  `skill` (status/install/uninstall), all with `--json` output.
- The context contract (`AGENTS.md`, `CLAUDE.md`,
  `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md`,
  `.context-maintainer/manifest.json`) plus the deterministic `doctor` checks,
  plus (v0.3.0) an optional `doctor --verify` pass that checks documented
  commands/technologies against repository evidence
  (CONFIRMED/UNVERIFIED/CONTRADICTED).
- Self-maintenance (v0.6.0): a `Stop` hook blocks the end of a turn when a
  commit has landed past the context checkpoint and the turn has not ruled on
  whether project reality changed — the enforcement layer DEC-004 left open,
  now taken because instructions demonstrably were not enough.
  `COMPLETED_INTENT` reports plans the repository
  shows are already carried out — the one drift class evidence-movement
  detection cannot see, because a plan cites nothing. `review --exit-code` lets
  automation gate on it. CONFIRMED: `cli.stop_notice`,
  `skill/context-maintainer/hooks/stop.sh`,
  `drift._detect_completed_intent`, DEC-011.
- Narrative drift detection (v0.4.0): `drift.py` and `context-maintainer
  review` parse the citations in each context document, resolve them against a
  repository path index, and compare them to the per-citation baseline in
  `.context-maintainer/evidence.json`, re-stamped by `sync --finalize`.
  Reported as DANGLING_CITATION, VERSION_DRIFT, STALE_EVIDENCE,
  VOLATILE_NUMBER, NEGATIVE_CLAIM, COVERAGE_GAP, UNATTESTED,
  COMPLETED_INTENT. `doctor --verify`
  fails on the unambiguous kinds only; the rest is worklist, not gate.
- A `PreCompact` hook (v0.5.0): `hooks/pre-compact.sh` and `cli.py`'s `hook
  pre-compact` report what a session has not written down — uncommitted source
  work, commits past the checkpoint, claims on moved evidence — just before
  the context window is summarised away. It informs and never writes, for the
  reason DEC-004 gave and DEC-007 restates.
- Hook notices delivered by the channel each event actually has (v0.5.1):
  `PreCompact` emits a `systemMessage` JSON envelope to the user, and
  `SessionStart` — the only compaction-adjacent event whose stdout the host
  injects — carries the same report to the agent when its source is `compact`.
  `cli._hook_payload` reads the host's stdin payload without blocking on a tty.
  Covered by `tests/test_hook_delivery.py`, which asserts delivery rather than
  wording. See DEC-009.
- A convention for recording approaches that were tried and abandoned
  (v0.5.0), in the `Alternatives considered:` field of the decision for what
  shipped, gated behind three tests in `references/sync-policy.md` so
  `DECISIONS.md` does not become a diary. Prose only — no CLI, no new store.
- Context size budgets (v0.5.0): 24 KiB per document and 64 KiB across
  `docs/context/`, both reported by `doctor` at 85% and again when exceeded,
  and both advisory — an oversized document is expensive, not wrong (DEC-008).
- A generated `## Index` at the head of `DECISIONS.md` (v0.5.0,
  `decisionindex.py`), maintained by `sync --finalize` once the file passes six
  entries. It is the only context document that grows without limit, and the
  index turns a lookup there from ~15 KiB into ~700 bytes. An index, not a
  summary: it restates only the headings below it, so it cannot drift on its
  own (DEC-008).
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

Closing the gap between *detecting* staleness and *fixing* it — the thing that
makes this a maintainer rather than a linter.

Both halves are written and green (DEC-010), and neither is proven in the wild.

`COMPLETED_INTENT` is the detector: a finished plan cites nothing, so no
evidence can move underneath it and every other detector here is blind to it by
construction. It found three stale claims in this file on its first run,
including the two this section previously contained.

The `Stop` hook is the actuator (DEC-011): when a commit lands past the context
checkpoint and the turn has not ruled on context, it blocks the turn and hands
the agent a reason. No API key, no CI, no cost — the agent already in the
session does the work. **Observed working**: on 2026-08-24 it blocked a real
turn, was answered in one sentence, and released — exactly one block, loop guard
intact.

That run also exposed a defect the tests had not: the trigger stays true until
`sync --finalize` runs, so the hook asked again every turn and answering it did
not help. Fixed by remembering the ruling against the commit it was given for,
in a disposable cache marker. That fix is tested but has not itself been
observed in real use.

A CI workflow driving a fresh agent through an API key was built during this
work and removed before release (DEC-010, superseded in part by DEC-011). It
never ran. What it would have covered and the `Stop` hook does not — claims that
go stale with no commit at all — is still uncovered, and is a real gap rather
than a solved problem.

## Blockers

None. CONFIRMED (user, 2026-08-24).

## Next

Build the self-healing pull-request loop (DEC-010), then validate that
generated context is *accurate* on projects other than this one — still the
main unproven claim, and still the priority. CONFIRMED (user, 2026-08-24).

Accuracy has two failure modes and they need different evidence:

- **Does the tooling catch drift it should?** Partly answered here.
  Development of v0.4.0 was itself the first test: `review` found a stale test
  count repeated in three documents, plus a stale `doctor` check count that its
  own first regex missed, and the repository's dogfooding test caught a citation
  bug (newly added files are invisible to `git ls-files`) before it shipped.
  That is real evidence, but it is evidence from one repository that happens to
  be the tool's own.
- **Does an agent actually adjudicate the worklist honestly?** Unanswered, and
  not mechanically answerable. Attestation is per document, so re-stamping
  without re-reading is possible and undetectable — see DEC-006's Consequences.
  This is the thing real-world use has to show.

Specifically outstanding:
- Drift detection has only ever run against this repository. Its false-positive
  rate on unfamiliar prose is unmeasured, and an early draft produced a flood of
  false defects here before calibration — so the risk is real, not theoretical.
  Volatile-number detection was since inverted from an allowlist of nouns to a
  list of suppressions, precisely because an allowlist cannot generalise past
  the vocabulary it was written against; that trade raises recall and lowers
  precision, and the precision cost has only been measured here (two added
  findings, both real).
- The v0.5.1 hook delivery fix is verified by tests and by hand, and its one
  open assumption is now closed: a diagnostic `SessionStart` hook recorded
  `{"hook_event_name": "SessionStart", "source": "compact"}` for the same
  `session_id` that had just been compacted, so the event does re-fire
  in-session rather than only on resuming a compacted session. What has *not*
  been observed is the v0.5.1 wording arriving during a real compaction: the
  installed plugin is still v0.5.0 (`~/.claude/plugins/installed_plugins.json`,
  commit `1a4fe0e`), so the notice that arrived was v0.5.0's stale-context text.
  That check needs a release first.
- Untested consequence of the v0.5.1 envelope: on a manual `/compact` the host
  echoes a `PreCompact` hook's raw stdout into the transcript. Under v0.5.0 that
  echoed the notice as prose; under v0.5.1 it will echo `{"systemMessage": …}`
  as literal JSON. Cosmetic rather than harmful — the agent-facing report now
  arrives via `SessionStart` regardless — but it should be looked at on release,
  not assumed.
- A cold install by someone with no local checkout has never been exercised;
  every install so far happened on the machine holding the repository.
- Codex plugin-local hooks may not execute yet (openai/codex#16430), so the
  `SessionStart` hook is verified on Claude Code only.
- Whether the `AGENTS.md` "state your conclusion" instruction actually
  changes agent behaviour is unmeasured.
