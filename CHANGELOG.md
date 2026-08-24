# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing yet.

## [0.4.0] — 2026-08-24

The release that makes context *self-maintaining*, by giving the agent a
bounded worklist instead of trusting it to notice.

v0.3.0 made claims checkable, and this repository still drifted underneath it:
a stale test count, a phase that had moved on, a CI job described nowhere.
`doctor --verify --strict` was green the whole time, because contradiction-
checking can only judge claims that exist and only in a closed vocabulary.
Nothing in a diff points at a sentence that quietly stopped being true.

### Added
- **`context-maintainer review`** — the claims worklist. Prose truth is not
  mechanically decidable, but evidence *movement* is: every claim already cites
  where it came from, so `review` resolves those citations and reports the ones
  whose evidence has moved since anyone confirmed them. Reports seven kinds —
  `DANGLING_CITATION`, `VERSION_DRIFT`, `STALE_EVIDENCE`, `VOLATILE_NUMBER`,
  `NEGATIVE_CLAIM`, `COVERAGE_GAP`, `UNATTESTED`.
- **`.context-maintainer/evidence.json`** — the attestation ledger, re-stamped
  by `sync --finalize`. Records the commit each cited file was last touched by,
  **per citation rather than per checkpoint**: a commit touching only
  `README.md` produces no findings unless a document cites `README.md`. Without
  that precision the signal would fire on every commit and be ignored.
- **`doctor --verify` gains `context_drift`** — fails on unambiguous defects (a
  citation pointing at nothing, a release newer than any document), warns when
  evidence has merely moved. Judgment-shaped findings stay in `review` so a
  pull request that touched code does not go red for claims that are probably
  fine.
- **`gitutil.get_tags` and `get_last_commit_touching`** — the two primitives
  drift detection needs.
- Drift now rides along in `sync --json` (`claims_to_adjudicate`) and in the
  session-start notice, because a signal that needs its own command to discover
  is a signal that gets skipped.

### Changed
- **The skill now tells the agent to re-validate existing claims.** Until now
  nothing did: every trigger was change-driven or structural, and `--verify`
  was not mentioned anywhere in `SKILL.md` or `references/`, so the one check
  that tested truth was invisible to the agent meant to run it. `sync` gained an
  adjudication step, `doctor` guidance now says to pass `--verify`.
- `references/evidence-policy.md` reconciles the two vocabularies that had been
  drifting apart — the CONFIRMED/INFERRED/UNKNOWN grade an author writes versus
  the CONFIRMED/UNVERIFIED/CONTRADICTED verdict the CLI reports — and asks for
  citations that can actually be re-checked later.
- `DECISIONS.md` is exempt from current-state drift checks: it records what was
  true when a decision was taken, and re-checking it against today's repository
  would ask authors to rewrite history the contract forbids rewriting.

### Fixed
- Citation resolution is case-sensitive everywhere. `Path.exists()` folds case
  on macOS and Windows, so a miscased citation resolved on a laptop and failed
  on a Linux CI runner — findings that depend on the developer's filesystem are
  worse than no findings. Caught by this repository's own CI, on a real
  miscased citation in `ARCHITECTURE.md`.

## [0.3.0] — 2026-08-24

The release that makes context *checkable* rather than merely well-formed.

### Added
- **`doctor --verify`** — the first check that looks at whether content is
  true, not just whether it is structurally valid. Reads documented commands
  from WORKFLOWS.md and technologies from ARCHITECTURE.md, then looks for
  evidence: a marker file, a dependency entry, or source usage. Three verdicts,
  and UNVERIFIED never fails, because a false positive costs more trust than a
  missed claim. Historical statements ("previously", "migrated away") are exempt
  by design, since recording migrations is something this tool asks for.
- **Time-based staleness.** `manifest.json` (schema 2) records
  `state_confirmed_at`, stamped when STATE.md is updated at `--finalize`. After
  21 days `doctor` and the session hook ask for re-confirmation — catching the
  case every other signal misses, where nothing changed and STATE quietly
  became false anyway.
- **`.context-maintainer/log.md`** — a capped, 20-entry record of what context
  changed and why. The CLI supplies which files; `--note` supplies the reason.
- **`docs/CI.md`** and a blocking `context-check` job in this repository's own
  CI, so its context cannot silently drift.
- Forward-looking triggers in the generated AGENTS.md: a new feature agreed, a
  direction change, or something deferred all change project reality even when
  no code has moved.

### Changed
- **`--strict` no longer promotes environmental warnings.** Repomix
  availability, MCP companion presence, skill installation, checkpoint
  freshness and state freshness are advisory: they are always warnings in CI
  and say nothing about whether the documents are correct. Without this,
  `--strict` was unusable for the enforcement it exists to provide.
- Staleness ignores changes confined to context files, so a sync's own
  bookkeeping no longer reports itself as drift.
- An empty section written as "None. CONFIRMED (user, date)." is recognised as
  empty, so `status` stopped inventing blockers.

### Fixed
- `doctor` reported a working marketplace plugin install as not installed.

## [0.2.0] — 2026-08-24

### Added
- `SessionStart` hook (`hooks/hooks.json`, auto-discovered by both hosts): a
  read-only freshness check when a project is opened, which tells the agent
  only when context has fallen behind the code. Silent otherwise, writes
  nothing, always exits 0.
- Generated `AGENTS.md` and the skill now require the agent to *state* its
  update decision — either what it changed, or "no context update needed" —
  with a concrete change-to-document trigger table replacing the word
  "meaningful".
- Existing-project `init` now confirms intent with the user (current objective,
  blockers, next milestone) instead of inferring it from commits, since intent
  is not evidence available in a repository.
- `SECURITY.md`, and Context Maintainer's own `docs/context/` (dogfooding).
- A test asserting `pyproject.toml` and `__version__` agree, because both hosts
  cache installed plugins under a version-keyed path.

### Changed
- Marketplace renamed from `context-maintainer` to `kevinifrah`, so installing
  reads `context-maintainer@kevinifrah` rather than stuttering. **Existing users
  must remove and re-add the marketplace** — there is no rename migration for
  marketplaces.
- README badge is now a live CI badge; the previous hardcoded test-count badge
  had already gone stale.

### Fixed
- `doctor` reported a working marketplace plugin install as "not installed",
  because it only looked for the symlink install. It now recognises either
  route, and fails only when an install exists but lacks its bundled CLI.

## [0.1.0] — 2026-08-23

First release.

### Added
- `context-maintainer` CLI: `init`, `status`, `sync`, `doctor`, `rebuild`,
  `audit`, `skill`, all with `--json` output. Python standard library only,
  zero runtime dependencies.
- The context contract: `AGENTS.md`, `CLAUDE.md`,
  `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md`, and
  `.context-maintainer/manifest.json`, enforced by 17 deterministic `doctor`
  checks.
- The `context-maintainer` Agent Skill, working on Claude Code and Codex from
  one canonical source, with references for the audit protocol, evidence
  policy, sync policy, and context contract.
- Deterministic blank-vs-existing project detection that ignores a README,
  a LICENSE, a `.gitignore`, and Context Maintainer's own output.
- Staged Repomix evidence gathering with an explicit, non-silent degraded mode
  when Repomix is unavailable.
- Optional `mcp-language-server` companion detection, never auto-installed.
- Conflict-safe symlink installer and uninstaller, per-host install flags, and
  plugin plus marketplace manifests for both hosts.
- README, CONTRIBUTING, `docs/INSTALL.md`, `docs/TESTING.md`.

### Security
- The originally specified code-intelligence backend
  (`DeusData/codebase-memory-mcp`) was evaluated and **rejected**: fabricated
  popularity signals, README text dismissing a Defender trojan detection as a
  false positive, non-verifiable self-scored VirusTotal claims, binary-only
  distribution, an installer writing into 43 unrelated agent configurations,
  and content that triggered prompt-injection defenses during research. The
  rationale is recorded in the README and `SECURITY.md` so it is not quietly
  reversed.
