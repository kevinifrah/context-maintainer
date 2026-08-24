# Project

Why this project exists. See `references/evidence-policy.md` in the context-maintainer skill for how to grade claims here as CONFIRMED, INFERRED, or UNKNOWN.

## Goal

Keep a small, durable, evidence-graded set of Markdown files in a repository
that answer what a project is, why it exists, how it's built, how to work on
it, where it currently stands, and what was decided and why — so that any
coding agent (Claude Code, Codex) starts a session already knowing this,
instead of the user re-explaining it every time. CONFIRMED: README.md "The
problem" / "How it works".

## Problem

Working across more than one coding agent, or across sessions separated by
context compaction, means re-explaining the same project understanding
repeatedly. That understanding usually already exists in the repository, but
scattered across a (often stale) README, commit history, and the user's head,
with no single durable place an agent can read first. CONFIRMED: README.md
"The problem".

## Users

Developers who work on a codebase with one or more AI coding agents,
particularly:
- People switching between Claude Code and Codex on the same repository.
- People whose sessions get interrupted by context compaction or restarts.
- People bringing the tool into a project that predates it (the "existing
  project" audit path exists specifically for this).

INFERRED from the tool's design (dual-host support, blank-vs-existing
detection, `sync` for returning-after-a-break) rather than stated as a
persona anywhere.

## Success Criteria

- `doctor`'s 18 deterministic checks pass (0 FAIL) on a maintained repository;
  since v0.3.0 an optional `--verify` pass also cross-checks documented
  claims against repository evidence, and this repository's own CI (
  `context-check` job) runs it with `--strict` on every push/PR. CONFIRMED:
  README "Commands" / `doctor`, CONTRIBUTING.md, `docs/CI.md`.
- `sync` stays incremental — most changes update nothing, and full repository
  re-scans happen only via the exceptional `rebuild` path. CONFIRMED:
  README "sync", CONTRIBUTING design principle #7.
- The deterministic layer (CLI) is well tested — 415 tests currently pass
  locally via `pytest -q` as of 2026-08-24 (CONFIRMED by running the suite;
  README states "300+ automated tests", which still holds).
- The judgment layer (the skill, running inside a live coding agent) produces
  context that is actually accurate and useful, not merely well-structured.
  The README states this explicitly has **not** yet been proven out: "Status:
  v0.1.0, early release... The parts that depend on a live coding agent — the
  actual quality of generated context — need real-world use to prove out."
  CONFIRMED, and still the open question. The user confirmed (2026-08-24)
  that the next milestone is exactly this: real-world dogfooding to validate
  context quality on actual projects.

## Scope

v0.1.0: a Python 3.9+ CLI with zero runtime dependencies, plus a Claude
Code / Codex Agent Skill, distributed either as a symlinked checkout
(`scripts/install.sh`) or as a marketplace plugin
(`/plugin marketplace add kevinifrah/context-maintainer`). Covers `init`,
`status`, `sync`, `doctor`, `rebuild`, `audit`, and `skill` subcommands, staged
Repomix evidence gathering, and optional `mcp-language-server` structural
verification. CONFIRMED: README "Commands", pyproject.toml, repository layout.

## Non-Goals

Explicitly not: a memory database, a vector store, a task or project
management system, an SDLC methodology, an autonomous coding framework, a
hosted service, a replacement for Git, or a reimplementation of Repomix. It
has one job — keep an accurate, compact, durable description of a project in
the repository itself. CONFIRMED: README "What this is not", CONTRIBUTING.md
"Anti-goals".

## Constraints

- **Zero runtime Python dependencies** — stdlib only; `pytest` is dev-only.
  CONFIRMED: pyproject.toml, README "Third-party dependencies and licenses".
- **Windows is not supported in v1** — installation relies on symlinks; WSL
  works. CONFIRMED: README "Limitations".
- **CLI/skill boundary is non-negotiable**: deterministic mechanics live in
  Python and are tested; judgment (what a change means, grading evidence,
  writing prose) lives only in the skill's Markdown instructions. Enforced by
  a contract test that keeps `contract.py` and
  `references/context-contract.md` in lockstep. CONFIRMED: CONTRIBUTING.md
  "The two rules that matter", README "How it works".
- **No telemetry, no network calls, nothing leaves the machine.** CONFIRMED:
  README "Security model".
- **Monorepos are handled naively** — one context contract per repository
  root; nested `AGENTS.md` files are detected and reported, not merged.
  CONFIRMED: README "Limitations".
- **Design principles are explicitly prioritized**, and conflicts resolve
  toward the earlier one: Reliability > one canonical project context >
  Claude Code + Codex compatibility > simple UX > safe handling of existing
  repos > evidence-based context > incremental maintenance > local/free/OSS >
  low token waste > extensibility. CONFIRMED: CONTRIBUTING.md "Design
  principles, in priority order".
