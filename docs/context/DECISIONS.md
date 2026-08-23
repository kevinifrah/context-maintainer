# Decisions

Durable, ADR-style record of decisions worth preserving. Do not manufacture
historical decisions that can't be supported by evidence — label inferred
ones explicitly. Never delete a superseded decision; mark it `Superseded` and
link to the decision that replaced it.

## DEC-001: Adopted the Context Maintainer contract

Status: Accepted

Decision: Use Context Maintainer's standard context contract (`AGENTS.md`,
`CLAUDE.md`, `docs/context/{PROJECT,ARCHITECTURE,WORKFLOWS,STATE,DECISIONS}.md`,
`.context-maintainer/manifest.json`) as this project's durable source of truth.

Why: Keep project understanding portable across sessions, context compaction,
and different coding agents (Claude Code, Codex), without a proprietary
memory store.

Evidence/context: `context-maintainer init` was run to establish this
structure.

Alternatives considered: Ad hoc README notes; no durable context at all.

Consequences: Coding agents are expected to read `docs/context/PROJECT.md`
and `docs/context/STATE.md` before substantial work, and to run
`context-maintainer sync` after meaningful changes.

Date/commit if known: 2026-08-24, 92132b1 (context established during this
`init` run)

## DEC-002: Rejected `DeusData/codebase-memory-mcp` as a structural-analysis backend

Status: Accepted

Decision: Do not use `DeusData/codebase-memory-mcp` for structural code
analysis. Use the optional `isaacphi/mcp-language-server` instead, which
wraps real language servers (gopls, pyright, etc.) as MCP tools.

Why: `DeusData/codebase-memory-mcp` was evaluated and found to show a
fabricated-popularity pattern (~40,000 GitHub stars in 6 months on a
repository owned by an account with 573 followers, verified via the GitHub
API), a README pre-emptively dismissing a Microsoft Defender
`Trojan:Script/Wacatac.B!ml` detection as a known false positive,
self-scored non-independently-verifiable VirusTotal tables, binary-only
distribution (no source-to-binary verification possible), an installer
writing into 43 different AI-agent tool configurations, and repository
content that triggered prompt-injection defenses during research.

Evidence/context: README.md "How Repomix is used" → "A security note worth
reading"; CONTRIBUTING.md "Reporting security issues". Documented in the
repository from early on; the exact original evaluation commit is not
separately identified, so the timing is INFERRED from when the security
note first appears in README history rather than confirmed against a
specific commit.

Alternatives considered: `DeusData/codebase-memory-mcp` (rejected, see
above); no structural-verification backend at all (the current fallback —
Repomix + Git + direct reading is treated as sufficient baseline).

Consequences: The skill only ever gains CONFIRMED-grade call-graph
verification when a user has separately configured `mcp-language-server`
themselves; absence of a backend is never treated as a failure, and any
future "codebase memory" style package proposed for this role should be
evaluated with the same scrutiny (per CONTRIBUTING.md).

Date/commit if known: UNKNOWN — documented in README/CONTRIBUTING as of the
current `HEAD` (92132b1); no dedicated commit isolates the original
evaluation.

## DEC-003: Marketplace renamed to `kevinifrah`, decoupled from the plugin name

Status: Accepted

Decision: The Claude Code / Codex plugin marketplace this project publishes
through is named `kevinifrah`, not `context-maintainer`. The plugin itself
is still named `context-maintainer`, installed as
`context-maintainer@kevinifrah`.

Why: Naming the marketplace after its one current plugin produced
`context-maintainer@context-maintainer`, an awkward stutter, and — more
importantly — misstated scope: a marketplace is a container that can hold
many plugins (real public marketplaces range from 19 to 2,282 entries) and
whose plugin entries can each point at an entirely different source
repository. Changing a plugin's name breaks every existing install, while a
marketplace name has no migration mechanism at all, so the rename was done
while the install base was still one machine rather than later.

Evidence/context: commit `92132b1` ("Rename the marketplace to kevinifrah to
remove the plugin@marketplace stutter"), which followed `e148f7d`'s doctor
fix and `13e1d67`/`59c9982`'s docs updates pointing at real repo coordinates.

Alternatives considered: Leaving the marketplace named `context-maintainer`
(rejected — see stutter/scope reasoning above).

Consequences: Future plugins get added to this same marketplace as
cross-repo entries (`{source: github, repo: ...}`), following the pattern
used by large public marketplaces, rather than each plugin needing its own
marketplace.

Date/commit if known: 2026-08-24, 92132b1

## DEC-004: Automatic staleness detection via SessionStart, not a per-turn Stop hook

Status: Accepted

Decision: Detect stale context with a single `SessionStart` hook, and handle
the per-turn "did this change project reality?" question with instructions in
`AGENTS.md` and `SKILL.md` rather than a hook.

Why: The event that fires after every agent output is `Stop`, whose only
channel to the model is `decision: "block"` — it cannot inform without
preventing the turn from finishing. Since the sync policy's own default answer
is "update nothing", a per-turn prompt would report "nothing needed" most of
the time and train users and agents to dismiss it. Noise does not produce
diligence.

Evidence/context: Claude Code hooks reference (Stop supports `decision`,
`reason`, `systemMessage`; SessionStart adds plain stdout to context). The
non-blocking `asyncRewake` field appears in a shipped Anthropic plugin but not
in public documentation, so it was not relied on. CONFIRMED by reading both
hosts' hook documentation and real shipped `hooks.json` files.

Alternatives considered: a `Stop` hook gated by `once: true` (still interrupts,
and fires at most once so it is not really per-turn); a git `post-commit` hook
that runs `sync --finalize` mechanically (rejected outright — it would mark
context as reviewed when nobody reviewed it, and silently wrong documentation
is worse than visibly stale documentation); headless `claude -p` auto-sync on
commit (writes unreviewed prose into the repository, inverting the premise that
these documents are trustworthy because a human saw them).

Consequences: Staleness introduced *outside* a session (other developers, other
tools, commits made without an agent) is caught automatically at session start.
Staleness introduced *within* a session depends on the agent following
instructions, which is visible but not enforced. A `Stop`-based enforcement
path remains available if instructions prove insufficient.

Date/commit if known: 2026-08-24, c3a5159 and 76721f8

