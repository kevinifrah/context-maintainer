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
- Only update `docs/context/` when the project reality has actually changed — avoid churn.

## Keeping context current

Before you finish a piece of work, decide whether it changed project reality,
and **state your conclusion** — either what you updated, or "no context update
needed". Silently skipping this check is indistinguishable from having done it,
which is how context goes stale.

Most changes need nothing: bug fixes, refactors within a component, copy edits,
formatting, dependency bumps, test additions. Say so and move on.

These do need an update:

| Change | Update |
| --- | --- |
| New component, service, integration, or external dependency | ARCHITECTURE, STATE |
| Storage, auth, or data-flow change | ARCHITECTURE, STATE, DECISIONS |
| Dev, test, build, or deploy command changed | WORKFLOWS |
| Milestone finished, work started, blocker hit or cleared | STATE |
| Product direction or scope changed | PROJECT, STATE |
| A documented decision deliberately reversed | DECISIONS — supersede it, never delete |
| **New feature or task agreed** | STATE (Next), and PROJECT (Scope) if it widens the remit |
| **Direction or priority changed** | PROJECT, STATE |
| **Something dropped or deferred** | STATE, and PROJECT (Non-Goals) if it is now out of scope |

The last three matter as much as the first six: a decision about what to
do next is a change to project reality even when no code moved yet.

When one applies, run the Context Maintainer sync workflow
(`context-maintainer sync`, or the `context-maintainer` skill) and update only
the sections that are genuinely now wrong. Read a section before concluding it
is unaffected.

## Claims that go stale without any change

The table above is driven by what you changed. Some claims stop being true
without anyone touching them: a test count, a version, a note that something
does not exist yet. Nothing in a diff points at those.

Run `context-maintainer review` and rule on what it lists — correct the claim,
or read the cited file and satisfy yourself it still holds. Re-confirming a
claim you did not actually check is the one failure this cannot detect.
