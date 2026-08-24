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

## DEC-005: `doctor --verify --strict` as a CI gate, with environmental checks kept advisory

Status: Accepted

Decision: Add `doctor --verify` (backed by `verify.py`) to mechanically check
documented commands/technologies against repository evidence, and wire
`context-maintainer doctor --verify --strict` into this repository's own CI
as a separate `context-check` job. Within `--strict`, split checks into ones
that fail the build (contract/content integrity, including
`claims_verified`) and `ADVISORY_CHECKS` that never do (Repomix availability,
MCP-companion presence, skill installation, checkpoint/state freshness).

Why: Instructions alone ("keep context current") are not enforcement — they
rely on an agent choosing to follow them. A CI gate makes a contradicted or
drifted context document a build failure instead of a silent lie. But
`--strict` promoting *environmental* warnings (e.g. Repomix not installed on
a CI runner) would make it fail on every run for reasons that say nothing
about whether the documents are correct, so `--strict` needed to distinguish
"the context is wrong" from "the environment is limited" or it would be
useless for the one job it exists to do.

Evidence/context: `CHANGELOG.md` [0.3.0]; `docs/CI.md`; `.github/workflows/
ci.yml` `context-check` job; `context_maintainer/doctor.py`
(`ADVISORY_CHECKS`); `context_maintainer/verify.py`.

Alternatives considered: Rely on `AGENTS.md`/`SKILL.md` instructions alone,
with no mechanical enforcement (the v0.2.0 state — rejected because nothing
caught drift introduced without an agent following the rule); make
`--strict` fail on every WARN including environmental ones (rejected —
would make the gate unusable in a plain CI runner with no Repomix/MCP
companion installed).

Consequences: A future contributor who adds a new `doctor` check must decide
whether it belongs in `CHECKS`'s failing set or `ADVISORY_CHECKS`, and get it
wrong at their peril — an environmental check added to the failing set would
make CI permanently red for reasons unrelated to context correctness.

Date/commit if known: 2026-08-24, 1e3c1aa (tagged v0.3.0 at b3aebed)

## DEC-006: Detect drift by evidence movement, not by judging prose

Status: Accepted

Decision: Add `drift.py` and a `context-maintainer review` command that parse
the citations the evidence policy already requires, resolve them to real
repository paths, and report claims whose cited evidence has moved since the
document was last attested. Record the baseline in a separate ledger,
`.context-maintainer/evidence.json`, keyed **per citation** — the commit each
cited file was last touched by — re-stamped by `sync --finalize`. Surface the
worklist to the agent through `review`, `sync --json`, the session-start hook,
and an explicit adjudication step in `SKILL.md` and `references/sync-policy.md`.

Why: Whether a sentence is true is not mechanically decidable, so v0.3.0's
`doctor --verify` could only check a closed vocabulary of commands and
technologies. That left the drift that actually happens untouched: this
repository shipped a stale test count, a phase that had moved on, and a CI job
described nowhere, all while `doctor --verify --strict` stayed green. Whether a
claim's *evidence has moved* is decidable, and because the documents already
cite their sources, the audit trail needed to compute it already exists. That
converts an undecidable question into a decidable one and — the point — yields a
bounded, localized worklist naming specific sentences, rather than "re-read five
documents", which is advice nobody follows.

Evidence/context: `CHANGELOG.md` [0.4.0]; `context_maintainer/drift.py`;
`doctor.check_context_drift`; `tests/test_drift.py`; the drift found during the
2026-08-24 sync that `--verify --strict` did not catch.

Alternatives considered: Extend `verify.py`'s fingerprint tables (rejected —
it can only ever judge claims whose vocabulary it already knows, and cannot see
an omission at all, because an omission leaves no claim to check); per-claim
content hashes instead of per-document attestation (rejected — any rewording
loses the attestation and the state grows without bound); compute staleness
against the sync checkpoint rather than per citation (rejected — it would flag
every claim on every commit, and a signal that fires constantly is a signal that
gets switched off); fail CI on the whole worklist (tried, and reverted the same day
after this repository's CI demonstrated the flaw: a commit editing `drift.py`
turned eleven claims stale and failed the build, and the cheapest way back to
green was `sync --finalize` with no re-reading — so the gate would have paid
contributors to perform exactly the blind attestation named below as this
design's blind spot. `context_drift` now sits in `ADVISORY_CHECKS`, which
suppresses WARN promotion while leaving its FAIL fully enforcing).

Consequences: Attestation is per document, so an agent *can* re-stamp without
genuinely re-reading each claim; the mechanics localize and demand, but cannot
enforce honesty, and this is the same boundary the rest of the tool sits on.
Mitigated in one respect that matters: finalizing clears staleness and never
clears a defect, so a dangling citation still fails `doctor` after a re-stamp
and cannot be laundered. Claims that cite nothing opt out of drift detection
entirely, which is why the evidence policy now asks for citations that can be
re-checked. `DECISIONS.md` is exempt from current-state detectors, since its
entries describe the moment a decision was taken.

Date/commit if known: 2026-08-24, v0.4.0

