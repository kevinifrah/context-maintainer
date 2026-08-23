# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing yet.

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
