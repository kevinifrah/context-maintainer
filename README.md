# Context Maintainer

**Durable, evidence-based project context for Claude Code and Codex — stored in your repository, not in a database.**

[![CI](https://github.com/kevinifrah/context-maintainer/actions/workflows/ci.yml/badge.svg)](https://github.com/kevinifrah/context-maintainer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

> **Status: v0.4.0, early release.** The deterministic layer is well tested (300+ automated tests, run on every push). The parts that depend on a live coding agent — the actual quality of generated context — need real-world use to prove out. See [Limitations](#limitations).

---

## Table of contents

- [The problem](#the-problem)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Staying current automatically](#staying-current-automatically)
- [The context contract](#the-context-contract)
- [Keeping context cheap to read](#keeping-context-cheap-to-read)
- [How Claude Code and Codex share context](#how-claude-code-and-codex-share-context)
- [How Repomix is used](#how-repomix-is-used)
- [Structural code analysis](#structural-code-analysis)
- [Security model](#security-model)
- [Evidence model](#evidence-model)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Uninstalling](#uninstalling)
- [Limitations](#limitations)
- [Future ideas](#future-ideas)
- [Contributing](#contributing)
- [Third-party dependencies and licenses](#third-party-dependencies-and-licenses)
- [License](#license)

**Also:** [docs/INSTALL.md](docs/INSTALL.md) — per-agent installation · [docs/TESTING.md](docs/TESTING.md) — end-to-end verification · [docs/CI.md](docs/CI.md) — enforcing context in CI

---

## The problem

If you use more than one coding agent on the same project — Claude Code in one terminal, Codex in another — each session starts from nothing. You re-explain what the project is, why it exists, how it's built, what you were in the middle of. Then the context window compacts and you explain it again.

The information that would answer those questions is *mostly* in the repository already, but scattered: some in the README (often stale), some in commit history, some only in your head.

Context Maintainer keeps a small, deliberately compact set of Markdown files in the repository that answer:

- What is this project, and why does it exist?
- Who is it for, and what problem does it solve?
- How is it built, and how do the pieces fit together?
- How do I run, test, build, and deploy it?
- What's done, what's in progress, what's blocked?
- What important decisions were made, and why?
- What should probably happen next?

Because the files live in Git, that understanding survives new sessions, context compaction, switching between agents, different developers, and projects that predate the tool.

**What this is not:** a memory database, a vector store, a task tracker, an autonomous coding framework, or a hosted service. There is no server, no API key, no Docker, and nothing to sign up for. It has one job: keep an accurate, compact, durable description of a project in the repository.

---

## How it works

Context Maintainer separates four concerns that are usually tangled together:

| Concern | Where it lives |
|---|---|
| **How should agents behave?** | `AGENTS.md`, `CLAUDE.md` — a concise router, not a knowledge dump |
| **Why does this project exist, and how does it work?** | `docs/context/PROJECT.md`, `ARCHITECTURE.md`, `WORKFLOWS.md`, `DECISIONS.md` |
| **Where is the project right now?** | `docs/context/STATE.md` — a snapshot, overwritten, never a diary |
| **How is context created and kept accurate?** | The `context-maintainer` skill + CLI |

And it splits work between two layers that are good at different things:

```
┌─────────────────────────────────────────────────────────────┐
│  context-maintainer skill  (runs inside Claude Code/Codex)   │
│  Judgment: what the project IS, what changes MEAN,           │
│  grading evidence, writing the prose                         │
└────────────────────────────┬────────────────────────────────┘
                             │ calls, consumes --json
┌────────────────────────────▼────────────────────────────────┐
│  context-maintainer CLI  (Python, standard library only)     │
│  Mechanics: repo detection, git state, scaffolding,          │
│  validation, checkpoints, evidence gathering                 │
└─────────────────────────────────────────────────────────────┘
```

The CLI never writes prose or interprets meaning. The skill never does by hand what the CLI can do deterministically. That boundary is the core design decision, and it's why the tool is auditable: everything mechanical is testable, and everything judgmental is visible in the documents it produces.

### Repository layout

```
context-maintainer/
├── .claude-plugin/marketplace.json   # so the repo is its own plugin marketplace
├── .agents/plugins/marketplace.json  # same, for Codex
├── skill/context-maintainer/      # THE PLUGIN — self-contained, one canonical copy
│   ├── SKILL.md                   # the skill (also serves plain-skill discovery)
│   ├── references/                # audit protocol, evidence + sync policy…
│   ├── scripts/cm.sh              # launcher: pip console script, else bundled package
│   ├── hooks/hooks.json           # SessionStart: warns when context is stale
│   ├── .claude-plugin/plugin.json
│   ├── .codex-plugin/plugin.json
│   ├── skills/context-maintainer/ # symlinks — Codex's expected plugin layout
│   └── context_maintainer/        # the CLI (stdlib only, zero runtime deps)
│       ├── cli.py                 # argument parsing and dispatch
│       ├── repository.py          # repo root + blank/existing detection
│       ├── gitutil.py             # git wrapper (subprocess, no libraries)
│       ├── manifest.py            # .context-maintainer/manifest.json
│       ├── contract.py            # the contract, as data
│       ├── mdsections.py          # markdown H2 parser
│       ├── scaffold.py            # safe file creation and backups
│       ├── briefing.py            # the `status` report
│       ├── doctor.py              # 19 deterministic health checks
│       ├── verify.py              # documented claims vs repository evidence
│       ├── drift.py               # claims that outlived the evidence they cite
│       ├── repomix.py             # staged evidence gathering
│       ├── mcp_companion.py       # optional companion detection
│       ├── installer.py           # symlink management
│       ├── pluginspec.py          # plugin + marketplace manifests, as data
│       └── templates/             # the seven context templates
├── scripts/install.sh             # one-command install from a checkout
├── installer/{install,uninstall}.py
├── docs/{INSTALL,TESTING}.md
└── tests/                         # 300+ tests, no network required
```

The Python package sits **inside** the plugin directory deliberately: both Claude Code and Codex copy only the plugin subdirectory when installing a plugin, so a package outside it would simply be missing on a user's machine. One canonical copy serves pip installs, symlinked checkouts, and plugin installs alike — and a test asserts it stays there.

---

## Requirements

| Dependency | Required? | Why | Notes |
|---|---|---|---|
| **Python 3.9+** | Required | The CLI | Standard library only — no pip dependencies |
| **Git** | Required | Change tracking is Git-native | Any recent version |
| **Claude Code** and/or **Codex** | Required in practice | Runs the skill that writes the context | The CLI works standalone, but produces templates, not prose |
| **[Repomix](https://github.com/yamadashy/repomix)** | Optional | Broad repository evidence for audits | Needs **Node 22+**. Without it, audits run in a clearly-labelled degraded mode |
| **[mcp-language-server](https://github.com/isaacphi/mcp-language-server)** | Optional | Compiler-grade "what calls what" | Needs Go + a language server. See [Structural code analysis](#structural-code-analysis) |

Nothing is installed on your behalf. Missing optional dependencies degrade capability and say so; they never fail silently or fall back to guessing.

---

## Installation

Full instructions, split by agent, are in **[docs/INSTALL.md](docs/INSTALL.md)**. The short version:

### As a plugin — nothing to clone

**Claude Code:**

```
/plugin marketplace add kevinifrah/context-maintainer
/plugin install context-maintainer@kevinifrah
```

**Codex:**

```bash
codex plugin marketplace add kevinifrah/context-maintainer --ref main
codex plugin add context-maintainer@kevinifrah
```

The Python CLI is bundled inside the plugin, so this needs no `pip install` and no other setup. Both hosts copy only the plugin directory when installing, which is exactly why the CLI lives inside it.

### From a checkout — one command

```bash
git clone https://github.com/kevinifrah/context-maintainer.git context-maintainer
cd context-maintainer
./scripts/install.sh              # both hosts
./scripts/install.sh --claude     # Claude Code only
./scripts/install.sh --codex      # Codex only
./scripts/install.sh --check      # dependency report, changes nothing
```

That checks dependencies, installs the `context-maintainer` CLI, and symlinks this checkout into whichever hosts you chose:

```
~/.claude/skills/context-maintainer   ->  <checkout>/skill/context-maintainer
~/.agents/skills/context-maintainer   ->  <checkout>/skill/context-maintainer
```

Symlinks rather than copies, on purpose: one canonical source, so `git pull` updates both hosts and no stale duplicate can drift.

**Keep the checkout** if you install this way — the symlinks point at it. If you move it, re-run the installer from the new location.

### Installer safety

The installer is idempotent and refuses to destroy anything it doesn't own:

| Situation | Behaviour |
|---|---|
| Nothing at the target path | Creates the symlink |
| Our symlink already there | Reports "already installed", changes nothing |
| Broken symlink | Repairs it |
| **Unrelated skill or directory there** | **Refuses, reports the conflict, exits non-zero** |
| Same, with `--force` | Moves it to a timestamped `.cm-backup-…` sibling first, then installs |

`--dry-run` never touches the filesystem. A conflict on one host still lets the other install.

Check state at any time:

```bash
context-maintainer skill status
```

---

## Quick start

### A brand-new project

```bash
mkdir my-project && cd my-project && git init
claude
```

Then, in Claude Code:

```
/context-maintainer init
```

The skill detects that the repository is effectively blank, asks only for what it genuinely can't infer (what you're building, who for, what problem it solves, what v1 must do, known constraints), then writes the full context structure. Later, from Codex:

```
$context-maintainer status
```

Same files. Same understanding.

### An existing project

```bash
cd my-existing-project
claude
```

```
/context-maintainer init
```

Here `init` behaves very differently: it does **not** write documents first. It audits the repository — structure, manifests, CI definitions, git history, execution flows — builds a model, grades every claim as CONFIRMED / INFERRED / UNKNOWN, and *only then* writes the context. Any existing `AGENTS.md` or `CLAUDE.md` is preserved and merged, never overwritten.

Afterwards, keep it current:

```
/context-maintainer sync          # in Claude Code
$context-maintainer sync          # or in Codex
```

---

## Commands

Same semantics in both hosts. Every command accepts `--json` for structured output.

### `init`

Establishes the context contract. Detects blank vs existing automatically and refuses to run twice — if already initialized, it points you at `sync` or `rebuild`.

```bash
context-maintainer init
context-maintainer init --mode existing   # override detection (debugging)
```

The detection heuristic classifies a repository as **existing** if it has a recognized dependency manifest or any source file, or else at least 3 non-trivial files *and* at least 3 commits. A README, LICENSE, `.gitignore`, `.DS_Store`, empty commits, or Context Maintainer's own output never count as evidence — so a fresh repo with twenty README-only commits is still correctly seen as blank.

### `status`

A fast briefing for someone returning after weeks away: goal, phase, architecture summary, current objective, blockers, recent commits, whether context has gone stale, and suggested next actions. Read-only.

```bash
context-maintainer status
```

### `sync`

Incremental maintenance — the command you run most. It reads the last verified commit from the manifest, compares it to `HEAD`, and reports what changed. The skill then updates **only** the sections that are genuinely now wrong.

```bash
context-maintainer sync                             # what changed since the checkpoint?
context-maintainer sync --finalize --note "why"     # advance the checkpoint, log the update
```

Most changes update nothing. A CSS tweak touches no document; a new auth service updates ARCHITECTURE and STATE; a storage migration also updates DECISIONS. `sync` never re-scans the whole repository — that's what `rebuild` is for.

### Verifying that context is *true*

Every other check validates form — files present, sections present, no
placeholders. That is orthogonal to accuracy: a completely fabricated
`ARCHITECTURE.md` passes all of them.

`--verify` checks claims against the repository:

```bash
context-maintainer doctor --verify
```

It reads documented commands from `WORKFLOWS.md` and technologies from
`ARCHITECTURE.md`, then looks for corresponding evidence — a `Cargo.toml` behind
a `cargo build` claim, a Postgres driver behind a Postgres claim, an `import` in
source behind a standard-library claim.

Three verdicts, and the middle one is the important one:

| Verdict | Meaning |
|---|---|
| **CONFIRMED** | Evidence found |
| **UNVERIFIED** | Named, but nothing to check against. Reported, **never** failed |
| **CONTRADICTED** | Claimed as current, while the repository shows otherwise |

Two deliberate guards, because a false positive costs more trust than a missed
claim:

- **History is exempt.** A line containing "previously", "migrated away", "no
  longer", "superseded" is a statement about the past. Recording migrations is
  something this tool actively asks for, so flagging them would be
  self-defeating.
- **Ignorance is not accusation.** With no recognisable ecosystem to compare
  against, a claim is UNVERIFIED, never CONTRADICTED.

Advisory by default (exit 0). `--strict` makes contradictions fail — see
[docs/CI.md](docs/CI.md).

### Time-based staleness

Code-driven staleness misses the case where *nothing* changed. A project can sit
untouched for a month while `STATE.md` still says "shipping next week".

So `manifest.json` records `state_confirmed_at`, stamped whenever `STATE.md` is
updated at `--finalize`. After 21 days, `doctor` and the session hook ask you to
re-confirm — even with zero commits.

### The context update log

`--finalize --note "..."` appends one short entry to
`.context-maintainer/log.md`:

```markdown
## 2026-08-24T09:14:02+00:00 — 11095042

Updated: docs/context/STATE.md

Added service.py; recorded the new module in STATE.
```

The CLI works out *which* context files changed; the note says *why*. It answers
"when was context last touched, and what for?" without digging through Git.

Three deliberate limits: it is **capped at 20 entries** (older history is in
Git); it lives in `.context-maintainer/` rather than `docs/context/` because it
is tool bookkeeping, not project knowledge; and it records **nothing** when no
context file changed and no note was given, so routine no-op syncs leave no
trace. `status` shows the most recent entry.

This is deliberately not a changelog. `STATE.md` is a snapshot and must never
become a diary — the log exists so that rule can stay strict.

### `review`

Everything above is driven by *what changed*. That catches every claim a commit
makes wrong — and nothing else. It cannot catch a stale test count, a "there is
no release workflow" note written before someone added one, or a CI job that
exists in the repository and in nobody's description of it. No commit
contradicts any of those out loud, so no diff points at them.

`review` is the other half. Every claim in these documents is already required
to cite where it came from. `review` parses those citations, resolves them to
real files, and reports the claims whose evidence has moved since anyone last
confirmed them:

```bash
context-maintainer review
context-maintainer review --json
```

```text
docs/context/ARCHITECTURE.md
  [WARN] STALE_EVIDENCE — Components
      “| `doctor.py` | 19 deterministic health checks (`CHECKS` list) |”
      rests on `…/doctor.py`, which has changed since this was last confirmed (b3aebed → 3010ebe)
      → Re-read the claim against the current file. Correct it, or re-confirm it.
```

It reports eight kinds: `DANGLING_CITATION` (a cited file or commit does not
exist), `VERSION_DRIFT` (the repo is tagged newer than any document describes),
`STALE_EVIDENCE` (the cited file moved), `VOLATILE_NUMBER` (a count that nothing
will correct when it stops being right), `NEGATIVE_CLAIM` (an assertion of
absence, which no positive evidence can ever re-confirm), `COVERAGE_GAP`
(something real that the documents describe none of while describing its
siblings), `UNATTESTED` (no baseline recorded yet), and `COMPLETED_INTENT` (a
plan the repository shows is already done).

`COMPLETED_INTENT` is the odd one, and it exists because the other seven share a
blind spot. All of them work by watching the evidence a claim cites. A plan
cites nothing — it describes the future — so no evidence can move underneath it
and a finished plan sits there looking current forever. This repository's own
`Next` section said "release the accumulated work (tag, marketplace update)"
across three tagged releases while `review` reported zero defects.

The baseline lives in `.context-maintainer/evidence.json`, re-stamped by
`sync --finalize`. It records the commit each cited file was last touched by —
**per citation, not per checkpoint**, which is what keeps this usable: a commit
touching only `README.md` produces no findings at all unless a document cites
`README.md`.

Two properties are deliberate. Finalizing clears *staleness* and never clears a
*defect*, so re-stamping cannot launder a dangling citation into a clean report.
And `review` only ever asks — it is `doctor` that decides whether a build fails.

### `doctor`

19 deterministic checks, no judgment involved: required files present, manifest present / parseable / schema-valid, `CLAUDE.md` → `AGENTS.md` bridge intact, required sections present, decision entries present, leftover placeholders, checkpoint valid, checkpoint not far behind HEAD, cache ignored, context within its size budgets, `DECISIONS.md` index current, `AGENTS.md` not duplicating the context documents, links resolving, Repomix available, MCP companion configured, skill installed correctly, plugin manifests valid, STATE recently confirmed.

```bash
context-maintainer doctor
context-maintainer doctor --verify   # also check claims against the repository
context-maintainer doctor --strict   # treat context warnings as failures (for CI)
```

Exit code is 0 for PASS/WARN and 1 for FAIL. It reports and never repairs.

`--verify` adds two content checks on top of the structural ones:
`claims_verified` (is a documented command or technology contradicted by the
repository?) and `context_drift` (has a claim outlived the evidence it cites?).
`context_drift` fails on unambiguous defects — a citation pointing at nothing, a
release newer than any document — and warns when evidence has merely moved.
The rest of the drift worklist stays in `review`, so a pull request that touched
code does not turn red for claims that are probably still true.

### `rebuild`

The exceptional full re-audit — after a pivot, a large migration, a contract change, or a poor first initialization.

```bash
context-maintainer rebuild --prepare    # back up all context files, then re-audit
context-maintainer rebuild --finalize   # advance the checkpoint when done
```

Decision history is preserved: superseded decisions are marked and linked, never deleted.

### `audit`

Gathers raw repository evidence into `.context-maintainer/cache/` (git-ignored). Read-only with respect to every context file. Normally invoked by the skill rather than by hand.

```bash
context-maintainer audit                  # cheap structure-only pass
context-maintainer audit --full           # + compressed sources, git logs, diffs
```

### `skill`

```bash
context-maintainer skill status
context-maintainer skill install [--force] [--dry-run]
context-maintainer skill uninstall [--force] [--dry-run]
```

---

## Staying current automatically

Context only helps if it is true, and remembering to run `sync` is exactly the
kind of discipline that lapses. So the plugin ships two hooks, at the two
moments understanding goes missing: the start of a session, and compaction.

### At the start of a session

When you open a project, a read-only freshness check runs and — only if
something needs attention — tells the agent:

```
Context Maintainer: this project's recorded context may be out of date —
2 commit(s) and 11 file(s) changed since the last checkpoint. Read
docs/context/PROJECT.md and docs/context/STATE.md before substantial work,
and run the context-maintainer sync workflow if what they say is no longer
true.
```

The agent then reads the context and can offer to sync before doing anything
substantial, instead of trusting stale documents.

### Before the context window compacts

Compaction is the problem this tool exists for: a long session builds up an
understanding of the project, and then most of it is summarised away. Whatever
nobody wrote down is exactly what does not survive.

So a `PreCompact` hook fires just before that happens, and — again, only when
there is something to say — names what has not reached the documents yet:

```
Context Maintainer: this session is about to be compacted with work it has not
recorded: 7 uncommitted files; 2 documented claims resting on evidence that has
since changed. Anything you have learned that is not written down will not
survive. Before continuing, decide whether this work changed project reality —
if it did, run the context-maintainer sync workflow now; if it did not, say so
and carry on. Record any approach you tried and abandoned in
docs/context/DECISIONS.md while you still remember why.
```

That one is addressed to **you**, and it is worth knowing why. Claude Code adds
a hook's plain output to the agent's context for only a few events —
`SessionStart` among them, `PreCompact` not. Typing `/compact` by hand does echo
a `PreCompact` hook's plain output, as part of the slash command's result line,
but that is a property of running the command; when the window fills on its own
there is no command and no echo. So this notice is delivered as a
`systemMessage`, which surfaces to the user however compaction was triggered.

The agent hears about it one moment later. `SessionStart` fires again after a
compaction with its source set to `compact`, and on that source — and only that
source — the same report is injected into the fresh context:

```
Context Maintainer: this session was just compacted with work it has not
recorded: 7 uncommitted files. Whatever it understood and did not write down is
gone. Before continuing, decide whether that work changed project reality — …
```

It is restricted to `source == "compact"` on purpose. Reporting a dirty working
tree at every session start would mean speaking in every repository anyone is
mid-edit in, which is the nagging the first constraint below exists to prevent.

Both notices ignore changes to `docs/context/` and `.context-maintainer/` when
deciding whether to speak, so running a `sync` does not make the next
compaction announce itself.

### Before a turn ends

The other notices inform. This one **stops the turn**:

```
Context Maintainer: this repository has 13 files changed since the context
checkpoint. Before finishing, decide whether this work changed project reality
and state your conclusion. If it did, update only the sections of docs/context/
that are genuinely now wrong and run `context-maintainer sync --finalize`. If it
did not, say "no context update needed" and stop — that is the common answer and
it ends this turn.
```

It is answerable in one sentence, and "no context update needed" is the intended
common answer. This exists because instructions were not enough: `AGENTS.md` has
asked every agent to state that conclusion since v0.2.0, and this repository's
own STATE.md still went three releases stale. Claude Code's documentation draws
the line — instruction files are "context, not enforced configuration… to block
an action regardless of what Claude decides, use a hook instead."

It fires only when a commit has landed past the context checkpoint. Uncommitted
work is deliberately not a trigger: mid-task is the normal state, and a hook
that fired on every edit is the nagging this design has refused twice. Three
guards must all fail before it speaks — it never blocks twice in a turn, never
blocks a turn that already ruled on context, and never blocks when nothing has
been committed past the checkpoint.

**No API key, no CI, no cost.** The agent already in your session does the work.

All four notices share three deliberate constraints:

- **Silent unless it matters.** No notice in projects that never adopted
  Context Maintainer, and none when context is already current. A hook that
  speaks every time gets ignored.
- **Never writes.** Detection only. The prose is still written by the agent,
  in session, where you can see and correct it.
- **Never disrupts a session.** They always exit 0 — a broken environment,
  a corrupt manifest, or a missing interpreter produces silence, not an error.
  The `Stop` hook continues a turn; it never fails one.

Verified on Claude Code. Codex plugin-local hooks may not execute yet
([openai/codex#16430](https://github.com/openai/codex/issues/16430)).

### What it deliberately does not do

There is no hook that rewrites your context unattended — including the
`PreCompact` one, which is the most tempting place to automate. A script could
mechanically advance the checkpoint on every commit, or re-stamp everything
just before compaction, but that would mark context as reviewed when nobody
reviewed it — silently wrong documentation is
worse than visibly stale documentation. Deciding what a change *means* needs
judgment, so it stays with the agent, in a session you can see.

---

## The context contract

Every initialized repository converges on exactly this:

```
project/
├── AGENTS.md                      # concise router + rules for agents
├── CLAUDE.md                      # first line: @AGENTS.md
├── docs/context/
│   ├── PROJECT.md                 # why this project exists
│   ├── ARCHITECTURE.md            # how the system works
│   ├── WORKFLOWS.md               # how to work on it
│   ├── STATE.md                   # where it is right now
│   └── DECISIONS.md               # decisions worth preserving
└── .context-maintainer/
    ├── manifest.json              # machine metadata only
    └── cache/                     # raw audit artifacts (git-ignored)
```

| File | Answers | Required sections |
|---|---|---|
| `PROJECT.md` | Why does this exist? | Goal, Problem, Users, Success Criteria, Scope, Non-Goals, Constraints |
| `ARCHITECTURE.md` | How does it work? | Overview, Components, Data Flow, Persistence, Integrations, Entry Points, Evidence Level |
| `WORKFLOWS.md` | How do I work on it? | Development, Testing, Build, Deploy, Notes |
| `STATE.md` | Where are we now? | Phase, Objective, Implemented, In Progress, Blockers, Next |
| `DECISIONS.md` | What did we decide, and why? | `## DEC-NNN:` entries (ADR-style) |

Three rules keep these files useful rather than bloated:

1. **`AGENTS.md` is a router, not a knowledge base.** It links to `docs/context/`; it never restates it. `doctor` warns if it starts duplicating content.
2. **`STATE.md` is a snapshot, not a log.** It gets overwritten. History belongs in Git; durable rationale belongs in `DECISIONS.md`.
3. **`manifest.json` holds machine metadata only** — schema version, mode, timestamps, last verified commit, tool versions. Unknown keys are rejected specifically to stop project knowledge leaking into it.

---

## Keeping context cheap to read

Context only helps if reading it costs less than the work it informs. Nothing
in the tool measured that until v0.5.0 — the per-file cap was 32 KiB with no
total, so the contract quietly permitted about 190 KiB across the set, roughly
48k tokens, before saying a word.

### Two budgets

| Budget | Limit | Reported at |
|---|---|---|
| Any one document | 24 KiB | 85% |
| All of `docs/context/` | 64 KiB | 85% |

`doctor` reports both. Neither fails a build, including under `--strict`: an
oversized document is expensive, not *wrong*, and the strict gate is reserved
for claims the repository contradicts (DEC-005, DEC-008).

When a budget trips, **cut — do not reorganise**. Splitting five documents into
thirty makes things worse: the agent globs, opens several, and spends more than
it saved. In order of what to lose first:

1. **Prose that cites nothing.** The most expensive text to read and the only
   kind `review` can never check for you. In this repository that was 36% of
   all claim blocks.
2. **Narrative history.** It belongs in Git, which already has it.
3. **Anything appended to a snapshot.** `STATE.md` is meant to be overwritten.

### The `DECISIONS.md` index

`DECISIONS.md` is the only document that grows without limit — the contract
forbids deleting a superseded decision, so it only ever gets longer. Here it is
already the largest file in the set.

But nobody needs to *read* it. They need to check whether a decision exists
before reversing one, which is a lookup being paid for as a full read. So once
the file passes six entries the CLI maintains an index at the top:

```markdown
## Index

<!-- CONTEXT-MAINTAINER: generated from the headings below. Edit those, not this. -->

- DEC-001 (Accepted) — Adopted the Context Maintainer contract
- DEC-002 (Accepted) — Rejected DeusData/codebase-memory-mcp as a backend
- DEC-003 (Superseded) — Marketplace renamed to kevinifrah
```

Roughly 700 bytes standing in for 15 KiB. The agent reads the index and then
one entry.

**An index, not a summary** — the distinction is the whole design. A summary
restates claims, so it can drift on its own and gives `review` two places to
adjudicate every claim instead of one. An index restates only the
`## DEC-NNN:` headings that already exist verbatim below it, so it can never
say anything the document does not. That is also why the CLI generates it
rather than the agent writing it: it is derived structure, not prose.

`sync --finalize` rebuilds it; `doctor` reports it when it is stale. Edit the
headings, never the index.

### What this deliberately is not

There is no vector store, embedding index, or knowledge graph, and there will
not be. Retrieval is what you build once your context has outgrown the window —
the bet here is that a project's durable context fits in 64 KiB, and the budget
is how that bet is kept honest rather than quietly lost.

---

## How Claude Code and Codex share context

The repository is the shared medium — there is no sync protocol, because there's nothing to sync.

| | Claude Code | Codex |
|---|---|---|
| Reads instructions from | `CLAUDE.md` | `AGENTS.md` (natively) |
| Skill installed at | `~/.claude/skills/context-maintainer` | `~/.agents/skills/context-maintainer` |
| Invoked as | `/context-maintainer:context-maintainer` (see note) | `$context-maintainer` |
| Reads context from | `docs/context/*.md` | `docs/context/*.md` |

Claude Code does not read `AGENTS.md` natively, so the generated `CLAUDE.md` starts with a single line:

```
@AGENTS.md
```

That import is Anthropic's documented pattern for exactly this situation, and it's why one set of instructions serves both agents. `doctor` treats a broken bridge as a hard failure.

> **Note on the Claude Code command name.** Because the installed directory contains a `.claude-plugin/plugin.json`, Claude Code loads it as a plugin, so the canonical command is `/context-maintainer:context-maintainer`. Bare `/context-maintainer` also works *unless another command already claims that name*. If you'd rather have an unconditional `/context-maintainer`, delete `skill/context-maintainer/.claude-plugin/plugin.json` and reinstall — it will then load as a plain skill. Codex is unaffected either way.

---

## How Repomix is used

[Repomix](https://github.com/yamadashy/repomix) packages a repository into a single model-readable file. Context Maintainer uses it in **stages**, rather than dumping an entire codebase into a context window:

1. **Structure pass** (`--no-files`) — cheap metadata and tree only. Usually enough to learn the shape of a project.
2. **Full pass** — adds `--compress` (tree-sitter signature extraction, roughly 70% fewer tokens), `--include-logs`, and `--include-diffs`, only when execution flows genuinely need to be understood.

Output goes to `.context-maintainer/cache/` and is git-ignored. The canonical output of an audit is the human-readable documentation — never the raw dump.

If Repomix isn't installed, `audit` reports `degraded_mode: true`, prints installation instructions, and explicitly tells the agent not to describe the audit as complete. It does not silently substitute guesswork.

---

## Structural code analysis

Context Maintainer ships **no** code-intelligence backend. Repomix, Git, and direct file reading are the baseline, and they're sufficient for a good audit.

Optionally, you can configure [`isaacphi/mcp-language-server`](https://github.com/isaacphi/mcp-language-server) (BSD-3-Clause), which wraps real language servers (gopls, pyright, typescript-language-server, rust-analyzer, clangd) as MCP tools. When it's present, the skill uses `definition` / `references` / `hover` / `diagnostics` to *verify* call-graph claims instead of inferring them — which is the difference between a CONFIRMED and an INFERRED statement about your architecture.

```bash
go install github.com/isaacphi/mcp-language-server@latest
go install golang.org/x/tools/gopls@latest      # or pyright, typescript-language-server, …
```

Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "language-server": {
      "command": "mcp-language-server",
      "args": ["--workspace", "/path/to/project/", "--lsp", "gopls"]
    }
  }
}
```

Codex:

```bash
codex mcp add language-server -- \
  mcp-language-server --workspace /path/to/project/ --lsp gopls
```

One instance binds to one language server, so a polyglot repository needs one entry per language. `doctor` reports whether it's configured; absence is never a failure.

> ### A security note worth reading
>
> This project was originally specified to use a different backend, `DeusData/codebase-memory-mcp`. It was **evaluated and rejected on security grounds**, and should not be reintroduced. The evidence:
>
> - ~40,000 GitHub stars accumulated in 6 months on a repository owned by an account with 573 followers — a fabricated-popularity pattern, verified via the GitHub API
> - README text pre-emptively dismissing a Microsoft Defender `Trojan:Script/Wacatac.B!ml` detection as a "known false positive"
> - Self-scored, non-independently-verifiable VirusTotal tables shipped in releases
> - Binary-only distribution, so no source-to-binary verification is possible
> - An installer that writes into 43 different AI-agent tool configurations
> - Repository content that triggered prompt-injection defenses during research, referencing agent permission settings
>
> Treat any similarly shaped "codebase memory" package with the same suspicion. Fabricated stars and a plausible README are cheap; a compiled binary with broad access to your source code and agent configuration is not a reasonable thing to trust on that basis.

---

## Security model

Context Maintainer reads a lot of a repository, so what it *won't* read matters.

**Secrets: inventory, never read.** Recording that `.env` exists and that `.env.example` lists `DATABASE_URL` is useful. Opening `.env` to see the value is not, and the skill is instructed never to do it. Discovered credentials are never written into context documents, commit messages, or cache files.

**Excluded from audit passes** (on top of Repomix's own defaults and `.gitignore`):

`.env` and `.env.*` (except `.env.example` / `.env.sample`) · private keys and certificates (`*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`) · `**/secrets/**` · `**/credentials/**` · `.aws/**` · `.ssh/**` · dependency directories · virtualenvs · build outputs · caches

**Repomix's Secretlint scanning stays enabled.** `--no-security-check` is never passed — there's an automated test asserting it.

**Nothing leaves your machine.** No telemetry, no network calls, no API keys. The CLI has zero runtime dependencies.

**Cache artifacts stay out of Git.** `.context-maintainer/cache/` gets its own `.gitignore`, and `doctor` warns if it's missing.

**Your files are not casually overwritten.** `init` preserves existing `AGENTS.md` / `CLAUDE.md` rather than replacing them. `rebuild` backs up before regenerating. Nothing with uncommitted changes is clobbered, even with `--force`.

---

## Evidence model

Context is only worth having if it can be trusted, so every claim carries a confidence level:

- **CONFIRMED** — directly supported by source, manifests, tests, current config, CI definitions, or Git history. Cite where it came from.
- **INFERRED** — strongly suggested by several signals but not stated outright. Labelled as such. One weak signal is not an inference.
- **UNKNOWN** — cannot be responsibly determined. Say so, and say what you checked.

**Current code beats stale documentation.** The canonical example: the README says MongoDB, `requirements.txt` has `psycopg2`, the source opens Postgres connections, and Git history contains "migrate MongoDB to PostgreSQL". The correct conclusion is PostgreSQL (CONFIRMED), with MongoDB as a historical note worth a `DECISIONS.md` entry — and the stale README flagged.

An honest UNKNOWN is more valuable than a plausible guess, because the next agent will act on whatever is written down.

---

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

300+ tests, no network access, no Node, and no real Repomix required — Repomix is exercised through a stub binary, and every installer test runs against a fake `$HOME` so your real `~/.claude` and `~/.agents` are never touched.

Coverage includes the blank/existing heuristic and its edge cases, Git behaviour (unborn HEAD, renames, deletions), manifest validation, scaffold safety, all 18 doctor checks, the Repomix wrapper and its degraded paths, installer conflict handling, skill and plugin packaging, and full end-to-end lifecycles against two realistic fixtures — one of which deliberately contains stale documentation contradicting its own code, so the "prefer the source" behaviour is actually tested rather than merely documented.

---

## Troubleshooting

**`context-maintainer: command not found`**
Run `pip install -e .` from the checkout. Alternatively use `python3 -m context_maintainer`, or the bundled `skill/context-maintainer/scripts/cm.sh`, which tries both.

**`/context-maintainer` isn't recognized in Claude Code**
Start a new session — skills are discovered at startup. Then check `context-maintainer skill status`. Try the fully-qualified `/context-maintainer:context-maintainer`, and see the [note on command names](#how-claude-code-and-codex-share-context).

**`$context-maintainer` isn't recognized in Codex**
Confirm `~/.agents/skills/context-maintainer/SKILL.md` resolves (`cat` it). Restart Codex. `/skills` lists what it can see.

**`doctor` says the skill symlink points somewhere else**
You likely moved the checkout. Re-run `python3 installer/install.py` from its current location, adding `--force` if a real directory now occupies the path (it gets backed up first).

**Audit says "DEGRADED MODE"**
Repomix isn't installed or isn't runnable. Install it (`npm install -g repomix`, Node 22+) or accept a Git-and-reading-only audit — which works, just with less breadth. Do not let an agent describe such an audit as complete.

**`doctor` reports FAIL on a fresh `init`**
Check *which* check failed. Leftover placeholders are a WARN and are expected until the skill fills the documents in. A FAIL means something structural — a missing file, a broken `@AGENTS.md` bridge, or an invalid manifest.

**Context feels stale but `sync` reports nothing**
`sync` compares against the recorded checkpoint. If someone advanced it without updating the documents, use `rebuild --prepare` for a full re-audit.

**Everything looks wrong after a big migration**
That's what `rebuild` is for. Incremental patching produces documents that are subtly wrong throughout.

---

## Uninstalling

```bash
python3 installer/uninstall.py --dry-run   # preview
python3 installer/uninstall.py             # remove the symlinks
pip uninstall context-maintainer           # remove the CLI
```

Uninstall only removes symlinks that point at your checkout; anything else requires `--force` and is backed up first.

Your context files are just Markdown in your repositories. They keep working — and stay readable by humans and any other agent — whether Context Maintainer is installed or not. Nothing is stranded.

---

## Limitations

Stated plainly, because a tool about honest documentation should be honest about itself.

- **Context quality depends on the agent.** The CLI guarantees structure, not insight. A rushed `init` produces a valid, well-formed, shallow set of documents. `doctor` can detect a missing section; it cannot detect a lazy one.
- **The audit is only as good as its evidence.** Without Repomix, breadth suffers. Without a language server, call-graph claims stay INFERRED. Both are reported, never hidden — but a degraded audit is still degraded.
- **Repomix flags are documented but not yet exercised against a live binary.** They come from Repomix's current documentation and are constructed by unit-tested pure functions; a wrong flag surfaces as a visible non-zero exit rather than silent emptiness. Worth confirming on your first real run.
- **Windows is not supported in v1.** Installation relies on symlinks. WSL works.
- **Monorepos are handled naively.** Nested per-directory `AGENTS.md` files are detected and reported, but not merged intelligently. One context contract per repository root.
- **`sync` is heuristic.** The mapping from "what changed" to "what to update" is guidance for the agent, not a proof. A one-line change can be architecturally significant.
- **The Claude Code command name is conditional.** See the [note above](#how-claude-code-and-codex-share-context).
- **Codex plugin-mode is untested here.** Codex *skill*-mode (`$context-maintainer`) is the supported path. The `.codex-plugin/plugin.json` manifest follows the field set used by all 180 plugins in the public `openai/plugins` marketplace, but marketplace installation itself hasn't been exercised.
- **No conflict resolution between agents.** If Claude Code and Codex edit context simultaneously, that's a normal Git conflict, resolved normally.
- **`doctor`'s staleness warning has an arbitrary threshold.** It warns at 10+ commits behind, to avoid warning constantly during ordinary work. `status` flags *any* drift.

---

## Future ideas

Not promises — directions that seem sensible:

- A `doctor --repair` for narrowly safe fixes (recreating a missing cache `.gitignore`, repairing a broken symlink)
- Real monorepo support: per-package context with a root index
- A pre-commit or CI mode that fails when a change plainly invalidates documented architecture
- An opt-in git `post-commit` warning, for commits made outside an agent session
- Optional additional audit backends behind the same "evidence in, graded claims out" interface
- Marketplace-installable plugin packaging for both hosts
- Windows support via junctions or a copy-based install
- Context contract versioning with automatic migration

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, how to add a `doctor` check, and the project's design principles. Bug reports and feature requests go to [Issues](https://github.com/kevinifrah/context-maintainer/issues).

Security issues — including a dependency that has become untrustworthy — are covered by [SECURITY.md](SECURITY.md).

Two rules matter more than the rest:

1. **Keep the CLI/skill boundary intact.** Deterministic mechanics go in the CLI, with tests. Judgment goes in the skill, as instructions. Don't put reasoning in Python or mechanics in Markdown.
2. **Don't let the tool overstate itself.** If a capability is degraded, it must say so.

---

## Third-party dependencies and licenses

Context Maintainer has **zero runtime Python dependencies** and vendors no third-party source. Optional tools are invoked as external programs:

| Project | License | Role |
|---|---|---|
| [Repomix](https://github.com/yamadashy/repomix) | MIT | Optional — repository packaging for audits |
| [mcp-language-server](https://github.com/isaacphi/mcp-language-server) | BSD-3-Clause | Optional — structural code analysis via MCP |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Development only |

`AGENTS.md` follows the [agents.md](https://agents.md/) convention, now stewarded by the Linux Foundation's Agentic AI Foundation. The skill follows the [Agent Skills](https://agentskills.io/) open standard, which both Claude Code and Codex implement.

---

## License

MIT — see [LICENSE](LICENSE).
