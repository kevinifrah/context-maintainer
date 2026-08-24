# Architecture

How the system works. Focus on the mental model required to safely change it — not a mechanical directory listing.

## Overview

Two layers, deliberately kept apart (CONFIRMED: README "How it works",
CONTRIBUTING.md "The two rules that matter"):

- **The skill** (`skill/context-maintainer/SKILL.md` + `references/`) runs
  inside a live coding agent (Claude Code or Codex). It holds all judgment:
  deciding what a project *is*, grading evidence CONFIRMED/INFERRED/UNKNOWN,
  writing the prose that ends up in `docs/context/`.
- **The CLI** (`context_maintainer` Python package, stdlib only) does
  everything mechanical: repo root and blank-vs-existing detection, Git
  state, scaffolding files, manifest/checkpoint bookkeeping, structural
  validation (`doctor`), and staged evidence gathering (`audit`). It never
  writes prose or interprets meaning.

The skill calls the CLI and consumes its `--json` output; the CLI never
reasons about content. This project *is* Context Maintainer's own
implementation — running `/context-maintainer:context-maintainer` in this
repository operates on itself.

## Components

All CLI source lives under `skill/context-maintainer/context_maintainer/`
(the Python package sits inside the plugin directory on purpose — see
Persistence/Integrations below). CONFIRMED by direct reading:

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing and subcommand dispatch |
| `repository.py` | Repo root discovery; blank-vs-existing heuristic |
| `gitutil.py` | Git wrapper via subprocess — no GitPython or similar |
| `manifest.py` | Reads/writes `.context-maintainer/manifest.json` |
| `contract.py` | The context contract (required files/sections), as data |
| `mdsections.py` | Markdown H2 section parser, used to validate/diff docs |
| `scaffold.py` | Safe file creation, placeholder insertion, backups |
| `briefing.py` | Builds the `status` report |
| `doctor.py` | 18 deterministic health checks (`CHECKS` list), plus an optional `--verify` pass (v0.3.0) that cross-checks documented claims against evidence |
| `verify.py` | Backs `doctor --verify`: extracts documented commands (WORKFLOWS.md) and technologies (ARCHITECTURE.md) and checks each against repo evidence (marker file, dependency entry, source usage), yielding CONFIRMED / UNVERIFIED / CONTRADICTED per claim — never fails on UNVERIFIED, only on CONTRADICTED |
| `repomix.py` | Staged Repomix invocation (structure pass, full pass) and degraded-mode handling |
| `mcp_companion.py` | Detects an optional configured `mcp-language-server` |
| `installer.py` | Symlink install/uninstall + marketplace-plugin-install detection |
| `pluginspec.py` | Plugin + marketplace manifests, as data |
| `templates/` | The seven context-contract templates used to scaffold new files |

Skill-side: `SKILL.md` (the only real copy; the one under
`skills/context-maintainer/` is a symlink for Codex's expected layout — a
test enforces this) plus `references/{audit-protocol,context-contract,
evidence-policy,sync-policy,mcp-companion}.md`.

Hook-side (added v0.2.0): `hooks/hooks.json` registers a single `SessionStart`
hook, auto-discovered by both hosts from the plugin root. It runs
`hooks/session-start.sh`, a thin wrapper over `cli.py`'s `hook session-start`
subcommand, which prints a one-paragraph notice to stdout — added to the
agent's context by both hosts — only when the project is initialized *and*
either context is behind HEAD or placeholders remain. CONFIRMED by direct
reading and by `tests/test_session_start_hook.py`.

Deliberately absent: a `Stop` hook. Its only channel to the model is
`decision: "block"`, which would interrupt every turn and risks a loop, so
the per-turn "did this change project reality?" question is handled by
instructions in `AGENTS.md` and `SKILL.md` instead of a hook. See DEC-004.

## Data Flow

1. A user invokes a skill command (`/context-maintainer:context-maintainer
   init|status|sync|doctor|rebuild`) inside Claude Code or Codex.
2. The skill calls `context-maintainer <command> --json` (this CLI, resolved
   via the `context-maintainer` console script, `python3 -m
   context_maintainer`, or the bundled `scripts/cm.sh` launcher).
3. For `init`/`rebuild` on a non-blank repo, and generally for evidence
   gathering, the skill also drives `context-maintainer audit
   [--structure-only|--full]`, which stages Repomix (structure pass without
   file contents, then optionally a compressed full pass with logs/diffs)
   and writes raw output to `.context-maintainer/cache/` (git-ignored).
4. The skill reads that structured evidence plus direct file reads (README,
   manifests, CI, git log) and git history, synthesizes a model, and grades
   each claim.
5. The skill writes/edits the Markdown context documents directly via its
   own file tools — the CLI never writes document *content*, only scaffolds
   placeholder structure (`init`) and validates structure (`doctor`).
6. `context-maintainer sync --finalize` / `rebuild --finalize` advances the
   checkpoint commit recorded in `.context-maintainer/manifest.json`, so the
   next `sync` diffs from there rather than re-scanning everything.

CONFIRMED: README "How it works", "Commands"; SKILL.md workflow sections.

## Persistence

Everything is flat Markdown/JSON files committed to the host repository —
there is no database, cache service, or external store:

- `AGENTS.md`, `CLAUDE.md` — router + rules, at repo root.
- `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md` — the
  content documents this file is part of.
- `.context-maintainer/manifest.json` — machine metadata only (schema
  version, init mode, checkpoint commit, timestamps, tool versions); unknown
  keys are rejected specifically to keep product knowledge out of it.
- `.context-maintainer/cache/` — raw audit artifacts (Repomix output, etc.),
  git-ignored, never the canonical output.

CONFIRMED: README "The context contract", `contract.py`, `.gitignore`.

## Integrations

- **Git** — required, invoked as a subprocess (`gitutil.py`); no Git library
  dependency. CONFIRMED.
- **Repomix** (optional, MIT, needs Node ≥22) — external CLI invoked in
  stages for audit evidence; `--no-security-check` is never passed (an
  automated test asserts this). Unavailable in this environment during this
  audit — Repomix is not installed here, so this audit itself ran in
  **degraded mode** (see Evidence Level). CONFIRMED: README "How Repomix is
  used", `repomix.py`, and this session's own
  `context-maintainer audit --structure-only --json` reporting
  `degraded_mode: true`.
- **mcp-language-server** (optional, BSD-3-Clause) — wraps real language
  servers (gopls, pyright, etc.) as MCP tools so the skill can *confirm*
  call-graph claims (`definition`/`references`/`hover`/`diagnostics`) instead
  of inferring them from grep. Not configured in this environment.
  CONFIRMED: README "Structural code analysis", `mcp_companion.py`.
- **Claude Code and Codex** — the two host agents this tool integrates with.
  Claude Code reads `CLAUDE.md` (which imports `@AGENTS.md`) and loads the
  plugin via `.claude-plugin/`; Codex reads `AGENTS.md` natively and loads
  its plugin via `.agents/plugins/` / `.codex-plugin/`. CONFIRMED: README
  "How Claude Code and Codex share context".
- Explicitly rejected integration: `DeusData/codebase-memory-mcp` as a
  structural-analysis backend — evaluated and turned down on documented
  security grounds (see `docs/context/DECISIONS.md`, DEC-002). CONFIRMED:
  README "A security note worth reading", CONTRIBUTING.md.

## Entry Points

- Console script `context-maintainer` → `context_maintainer.cli:main`
  (`pyproject.toml` `[project.scripts]`).
- `python3 -m context_maintainer` and `skill/context-maintainer/scripts/cm.sh`
  (tries the console script, falls back to the module) — both fallbacks for
  when the package isn't on `PATH`.
- Claude Code slash command: `/context-maintainer:context-maintainer` (bare
  `/context-maintainer` also works unless another command claims the name —
  see README's note on command names, since the plugin manifest makes this a
  namespaced plugin command).
- Codex: `$context-maintainer`.
- Host-invoked entry point (not user-facing): `hook session-start`, called by
  the `SessionStart` hook via `hooks/session-start.sh`. Always exits 0.
- CI entry points, both in `.github/workflows/ci.yml`: a `test` job running
  `pytest -q` on Python 3.9 and 3.12, and a `context-check` job (added
  v0.3.0) that runs `context-maintainer doctor --verify --strict` — the
  enforcement half of claim verification, so a contradicted or drifted
  context document fails this repository's own build. See `docs/CI.md` for
  which checks that job can fail on versus which stay advisory.

CONFIRMED: pyproject.toml, README "Commands"/"Troubleshooting", CI workflow,
`docs/CI.md`.

## Evidence Level

This audit ran **degraded**: Repomix is not installed in this environment
(`context-maintainer audit --structure-only --json` → `degraded_mode: true`,
`repomix.available: false`), and no `mcp-language-server` companion is
configured. No structural code-intelligence pass (call-graph verification)
was performed — the module responsibilities above are stated at the level
the README and direct file listing support, not verified via
`definition`/`references`.

Confidence is otherwise high despite the degraded audit, because this
project's own README and CONTRIBUTING.md are unusually thorough,
self-describing, and specific (they document their own architecture,
Contributing.md documents the doctor-check and contract-change conventions),
and the test suite (415 passing, run directly via `pytest -q` on 2026-08-24)
corroborates the documented behavior rather than merely asserting it.
Where a claim rests only on documentation without independent corroboration,
it is marked INFERRED above; everything else cited to a specific file or
command output is CONFIRMED.
