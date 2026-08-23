# context-maintainer

Context Maintainer keeps a small, durable, evidence-graded set of Markdown
files in a repository (`AGENTS.md`, `CLAUDE.md`, `docs/context/*.md`) that
answer what a project is, how it works, how to work on it, and where it
stands — so Claude Code and Codex share one understanding instead of each
session starting from nothing. It splits work between a zero-dependency
Python CLI (deterministic mechanics: detection, git state, scaffolding,
validation) and an Agent Skill (judgment: grading evidence, writing prose).
This repository is the tool's own implementation.

## Project context

Durable project knowledge lives under `docs/context/`. Read these before doing substantial work:

- [docs/context/PROJECT.md](docs/context/PROJECT.md) — why this project exists, goals, users, constraints
- [docs/context/STATE.md](docs/context/STATE.md) — current phase, objective, blockers, next steps
- [docs/context/ARCHITECTURE.md](docs/context/ARCHITECTURE.md) — how the system works
- [docs/context/WORKFLOWS.md](docs/context/WORKFLOWS.md) — how to develop, test, build, and deploy
- [docs/context/DECISIONS.md](docs/context/DECISIONS.md) — durable historical decisions

## Rules for coding agents

- `docs/context/` is the durable source of truth for this project. Do not duplicate its content here or invent a competing summary.
- Do not silently reverse a documented decision in `docs/context/DECISIONS.md`. If reality has changed, record a new decision that supersedes it.
- Do not convert an assumption into a documented fact. Mark uncertain claims as such.
- After a meaningful change, run the Context Maintainer sync workflow (`context-maintainer sync`, or the `context-maintainer` skill's sync behavior) so `docs/context/` stays accurate.
- Only update `docs/context/` when the project reality has actually changed — avoid churn.
