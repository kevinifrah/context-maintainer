# Context contract

Every initialized repository converges on this structure:

```text
project/
├── AGENTS.md                     # concise router + rules for agents
├── CLAUDE.md                     # first line: @AGENTS.md
├── docs/context/
│   ├── PROJECT.md                # why the project exists
│   ├── ARCHITECTURE.md           # how the system works
│   ├── WORKFLOWS.md              # how to work on it
│   ├── STATE.md                  # where it is right now
│   └── DECISIONS.md              # decisions worth preserving
└── .context-maintainer/
    ├── manifest.json             # machine metadata only
    └── cache/                    # raw audit artifacts, git-ignored
```

`doctor` enforces the required sections below. The list here is kept in
lockstep with `contract.py` by an automated test — if you change one, change
both.

## Required sections

### AGENTS.md
Required sections: Project context, Rules for coding agents

A thin router. One short paragraph on what the project is, links into
`docs/context/`, and the operating rules for agents. It must not restate the
content of the context documents.

### CLAUDE.md
Required sections: (none)

Its first non-empty line must be exactly `@AGENTS.md`. Claude-specific
instructions may follow. Nothing else is required, and AGENTS.md content must
not be duplicated here.

### docs/context/PROJECT.md
Required sections: Goal, Problem, Users, Success Criteria, Scope, Non-Goals, Constraints

Answers *why this project exists*. Product-level only. Implementation detail
belongs in ARCHITECTURE.md unless it is a genuine product constraint. Include
open product questions when they matter.

### docs/context/ARCHITECTURE.md
Required sections: Overview, Components, Data Flow, Persistence, Integrations, Entry Points, Evidence Level

Answers *how the system works*. Capture the mental model needed to change the
system safely: major components and boundaries, important execution and data
flows, persistence, integrations, entry points, infrastructure, architectural
constraints, unusual choices, and important code locations.

Do not reproduce the directory tree — agents can list directories themselves.
Use "Evidence Level" to state honestly how confident the rest of the document
is, and to record when an audit ran degraded (for example, without Repomix or
without a structural-analysis companion).

### docs/context/WORKFLOWS.md
Required sections: Development, Testing, Build, Deploy, Notes

Answers *how to work on this repository correctly*: prerequisites, setup,
environment handling, dev/test/lint/typecheck/build commands, migrations, local
services, deployment, CI/CD, release flow, and durable troubleshooting.

Never invent a command. If it is not confirmed by a manifest, config file, CI
definition, or documentation, mark it unknown and say what you checked.

### docs/context/STATE.md
Required sections: Phase, Objective, Implemented, In Progress, Blockers, Next

Answers *where are we right now*. A current snapshot, updated often and kept
short. Overwrite it — never append a chronological diary. History belongs in
Git; durable rationale belongs in DECISIONS.md.

### docs/context/DECISIONS.md
Required sections: (none — uses `## DEC-NNN: <title>` entries)

Append-only ADR-style log. One entry per decision worth preserving:

```text
## DEC-007: Moved session storage to Postgres

Status: Accepted | Superseded | Reconsidering

Decision: what was decided.

Why: the reasoning.

Evidence/context: what supports this (files, commits, docs). Label an
inferred decision explicitly as inferred.

Alternatives considered: what else was on the table.

Consequences: what this commits the project to.

Date/commit if known: 2026-03-14, a1b2c3d
```

Do not manufacture decisions that evidence cannot support. Never delete a
meaningful decision that was replaced — mark it `Superseded` and link forward.

Because nothing is ever deleted, this is the one document that grows without
limit — every other one is a snapshot you overwrite or is bounded by the
project itself. Once it reaches six entries the CLI maintains an `## Index`
section at the top listing every entry, its status, and its title, so checking
whether a decision exists costs a few hundred bytes instead of the whole file.

That index is **generated**, not written: `sync --finalize` rebuilds it from
the `## DEC-NNN:` headings and `doctor` reports it when it is stale. Edit the
headings, never the index. It is deliberately an index and not a summary — a
summary would restate claims, drift on its own, and give `review` two places to
adjudicate instead of one.

## Size budgets

Context is only useful if reading it costs less than the work it informs. Two
budgets, both reported by `doctor` and neither one a build failure — an
oversized document is expensive, not *wrong*:

- **Per document:** 24 KiB.
- **The whole of `docs/context/`:** 64 KiB.

Both report at 85% so there is room to act before the budget is gone. When one
trips, cut rather than reorganise: overwrite snapshots instead of appending to
them, leave narrative history in Git, and treat a long section that cites
nothing as the cheapest thing to lose — it is both the most expensive prose to
read and the only kind `review` can never check for you.

## manifest.json

Machine metadata only: schema version, init mode, timestamps, last verified
commit, and tool versions. Product knowledge never goes here — the CLI rejects
unknown keys precisely to keep it that way.
