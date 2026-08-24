# Decisions

Durable, ADR-style record of decisions worth preserving. Do not manufacture
historical decisions that can't be supported by evidence — label inferred
ones explicitly. Never delete a superseded decision; mark it `Superseded` and
link to the decision that replaced it.

## Index

<!-- CONTEXT-MAINTAINER: generated from the headings below. Edit those, not this. -->

- DEC-001 (Accepted) — Adopted the Context Maintainer contract
- DEC-002 (Accepted) — Rejected DeusData/codebase-memory-mcp as a structural-analysis backend
- DEC-003 (Accepted) — Marketplace renamed to kevinifrah, decoupled from the plugin name
- DEC-004 (Accepted) — Automatic staleness detection via SessionStart, not a per-turn Stop hook
- DEC-005 (Accepted) — doctor --verify --strict as a CI gate, with environmental checks kept advisory
- DEC-006 (Accepted) — Detect drift by evidence movement, not by judging prose
- DEC-007 (Accepted) — A PreCompact hook that informs, and never attests
- DEC-008 (Accepted) — Budget the context, and index the one file that grows forever
- DEC-009 (Accepted) — Deliver each hook notice by the channel its event actually has
- DEC-010 (Accepted in part — the CI workflow is superseded by DEC-011) — Detect finished plans, and propose fixes as a pull request
- DEC-011 (Accepted) — Enforce the context ruling with a Stop hook, not a paid CI loop

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
reading"; CONTRIBUTING.md "Reporting security issues". Timing is INFERRED from
when that note first appears in README history, not confirmed against a
commit.

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
gets switched off); fail CI on the whole worklist (tried, and reverted the same day: a
commit editing `drift.py` turned eleven claims stale, and the cheapest way back
to green was `sync --finalize` with no re-reading — the gate would have paid
contributors to perform exactly the blind attestation named below as this
design's blind spot. `context_drift` now sits in `ADVISORY_CHECKS`, which
suppresses WARN promotion while leaving its FAIL enforcing).

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

## DEC-007: A `PreCompact` hook that informs, and never attests

Status: Accepted

Decision: Add a second host hook on the `PreCompact` event, which reports what
this session has not yet written down — uncommitted source work, commits past
the context checkpoint, claims resting on moved evidence — and asks the agent
to decide. It never writes: no re-stamp, no checkpoint advance, no edit.

Why: Compaction is the failure this project was built for, and it was the one
moment nothing watched. `SessionStart` (DEC-004) catches context that went
stale *between* sessions. Nothing caught a session's own understanding being
summarised away — the point at which whatever nobody wrote down is lost, and
the last point at which the agent still remembers enough to write it.

Evidence/context: `skill/context-maintainer/hooks/pre-compact.sh`,
`skill/context-maintainer/hooks/hooks.json`, `cli.pre_compact_notice`,
`tests/test_pre_compact_hook.py`. CONFIRMED by running `context-maintainer
hook pre-compact` against this repository in both the silent and speaking
states.

Alternatives considered: having the hook run `sync --finalize` itself, so
nothing depends on the agent complying. Rejected for the reason DEC-004
rejected a mechanical `post-commit` finalize — it marks context as reviewed
when nobody reviewed it — which binds harder here, not more weakly: mid-task
nothing is settled, so an automatic re-stamp would attest to prose no human
has seen. Also considered emitting on every compaction regardless of state,
and rejected on DEC-004's noise argument: a notice that always fires is a
notice that gets skimmed at the compaction where it mattered.

Consequences: Two hooks now share one contract — always exit 0, never write,
stay silent unless something needs doing — and `hooks.json` is asserted to
register no blocking event. The hook excludes `docs/context/` and
`.context-maintainer/` from what counts as unrecorded work, so a `sync` does
not make the next compaction announce itself. Verified on Claude Code only:
Codex plugin-local hooks may not execute yet (openai/codex#16430), the same
limitation `SessionStart` already carries.

Date/commit if known: 2026-08-24

## DEC-008: Budget the context, and index the one file that grows forever

Status: Accepted

Decision: Give `docs/context/` two reported budgets — 24 KiB per document and
64 KiB across the set, both flagged at 85% — and have the CLI maintain a
generated `## Index` at the head of `DECISIONS.md` once it passes six entries.
Both are reported, never enforced: `context_size` moves into
`ADVISORY_CHECKS`, and `decisions_index` warns rather than fails.

Why: Context only helps if reading it costs less than the work it informs, and
nothing measured that. The per-file cap was 32 KiB with no total, so the
contract silently permitted roughly 190 KiB — around 48k tokens — across the
set before saying a word. Meanwhile `DECISIONS.md` is the only document that
grows without limit: the contract forbids deleting a superseded decision, so it
only ever gets longer, and it was already the largest file here at 14.6 KiB and
30% of the whole context. But nobody ever needs to *read* it — they need to
check whether a decision exists before reversing one. That is a lookup being
paid for as a full read, and an index of the headings turns 14.6 KiB back into
about 700 bytes.

An index, not a summary: it restates only the `## DEC-NNN:` headings that
already exist verbatim below it, so it can never say anything the document does
not. That is why the CLI owns it rather than the agent — it is derived
structure a machine rebuilds exactly. Markup is stripped from the titles so a
backticked path in an index line is not read as a citation by `drift.py`.

Reported and not enforced because DEC-005 reserves the strict gate for claims
the repository contradicts. An oversized document is expensive, not wrong, and
failing a pull request because context grew a kilobyte is exactly the noise
DEC-005 was written to keep out of the gate. DEC-005 anticipated this choice:
it requires every new check to be classified deliberately.

Evidence/context: `context_maintainer/decisionindex.py`,
`context_maintainer/contract.py` (`MAX_CONTEXT_FILE_BYTES`,
`MAX_CONTEXT_TOTAL_BYTES`, `CONTEXT_SIZE_SOFT_RATIO`),
`context_maintainer/doctor.py` (`check_context_files_not_oversized`,
`check_decisions_index_current`), `tests/test_decision_index.py`,
`references/context-contract.md` "Size budgets". Measurements taken directly
from this repository on 2026-08-24.

Alternatives considered: a vector or graph index over the documents (rejected —
it is the retrieval layer this project's non-goals exclude, and retrieval is
what you build once the store has outgrown the context window, which is the
premise being defended, not abandoned); a generated summary at the head of each
document (rejected — it restates claims, so it drifts independently and doubles
what `review` must adjudicate); splitting the documents into a tree of smaller
files (rejected — thirty small files cost more to navigate than five compact
ones; splitting only pays when it separates hot from cold, which archiving
superseded decisions would, and which buys nothing while every decision here is
still `Accepted`); enforcing the budgets in `--strict` (rejected per DEC-005 as
above).

Revised 2026-08-24 (DEC-010): the per-document cap charges an indexed
`DECISIONS.md` its *read* cost — index plus largest entry — not its size on
disk. Adding DEC-010 put the file 1.6 KiB over a cap whose only exits were
deleting reasoning or raising the budget, both argued against above. Charging
bytes nobody reads was the actual error: this document is append-only by
contract, so a fixed byte cap collides with it on a fixed schedule. Every other
document is still charged in full, because they are read whole.

Consequences: Contributors get told when context is getting expensive, early
enough to act, and are never blocked by it. `DECISIONS.md` acquires a block the
CLI owns — hand-editing it is pointless, and `doctor` says so. `sync
--finalize` now writes to a context document, which is new: it is defensible
only because the block is derived from headings and contains no judgment, and
that boundary must hold for anything added here later. If a future document
also grows without limit, it needs the same treatment rather than a bigger
budget.

Date/commit if known: 2026-08-24

## DEC-009: Deliver each hook notice by the channel its event actually has

Status: Accepted

Decision: Choose the output form per hook event rather than per hook.
`SessionStart` prints plain text, which the host adds to the agent's context.
`PreCompact` prints a JSON envelope carrying `systemMessage`, which surfaces to
the user. The agent-facing half of the compaction report moves to
`SessionStart` under `source == "compact"`, and is restricted to that source.

Why: v0.5.0 shipped a `PreCompact` hook that ran correctly and was read by
nobody. Claude Code adds a hook's plain stdout to the agent's context for
`UserPromptSubmit`, `UserPromptExpansion` and `SessionStart` only; for every
other event, including `PreCompact` and `PostCompact`, stdout goes to the debug
log and nowhere else. `PreCompact` accepts `systemMessage` and
`preCompactDecision`, but not `additionalContext` — there is no way to inject
context from that event at all. So the notice had to split: the warning before
compaction can only reach a human, and the agent can only be told afterwards.

The `source == "compact"` restriction is part of the decision, not an
implementation detail. Reporting a dirty working tree at every session start
would speak in every repository anyone is mid-edit in, which is precisely the
noise argument DEC-004 and DEC-007 both turned on.

Evidence/context: `cli._hook_payload`, `cli.cmd_hook`, `cli._compacted_notice`,
`skill/context-maintainer/hooks/pre-compact.sh`,
`tests/test_hook_delivery.py`. The channel rule is CONFIRMED against the hooks
documentation at https://code.claude.com/docs/en/hooks. The `source == "compact"`
re-fire is CONFIRMED by a diagnostic hook that logged
`{"hook_event_name": "SessionStart", "source": "compact"}` for the same
`session_id` that had just been compacted in-session.

Correction: this entry originally claimed v0.5.0's notice had been observed
reaching nobody. It had not. That compaction ran in a session whose hook
registry predated v0.5.0's install, so the hook never ran — the transcript
records a bare `Compacted `. Plain text was never shown to fail; it was never
exercised. The decision rests on the documentation and the auto-compaction case
below, not on that observation.

Alternatives considered: printing plain text from `PreCompact` — shipped in
v0.5.0 and superseded here. It does reach the transcript when a human types
`/compact`, because the slash command echoes hook stdout, but that echo is an
artefact of manual invocation; an automatic compaction issues no command and so
leaves only the debug log. Recorded because it is the obvious implementation, it
looks correct in every unit test, and it appears to work whenever anyone tests
it by hand. Also considered moving the notice
to `PostCompact`, which fires after compaction completes and would have the
right timing for the agent; rejected because its stdout has the same
debug-log-only fate. Also considered dropping the `PreCompact` hook entirely
and reporting only at the next `SessionStart`; rejected because the user
losing a window of work still deserves to be told at the moment it happens,
even when the agent cannot be.

Consequences: The two hooks now share only DEC-007's behavioural contract, not
one output form. That asymmetry is a trap for a future editor, so it is asserted
in `tests/test_hook_delivery.py`, which tests what a host receives rather than
what a notice builder returns. Both hooks read stdin; `_hook_payload` refuses to
read a tty so a hand-run hook cannot hang. The `source == "compact"`
re-fire this design depends on is verified (see Evidence). What remains
unobserved is the v0.5.1 wording arriving during a real compaction, because the
installed plugin is still v0.5.0; STATE.md records that and the one cosmetic
consequence of the envelope.

Date/commit if known: 2026-08-24

## DEC-010: Detect finished plans, and propose fixes as a pull request

Status: Accepted in part — the CI workflow is superseded by DEC-011

Decision: Add a `COMPLETED_INTENT` detector that reports plans and
release-state claims the repository shows are already overtaken, and a
`context-sync` CI workflow that has an agent adjudicate the `review` worklist
and open a **pull request**. The workflow may never push to a branch anyone
reads directly.

Superseded 2026-08-24, same day, by DEC-011. The detector half ships and stands.
The CI workflow was **built, never run, and removed** before release: it costs
money per run, needs an API key, works only on GitHub, and reaches for a fresh
agent while the one that made the change is still in the repository with the
whole task in its context. Recorded rather than deleted because the reasoning
below about *why a pull request is an admissible write* is correct and worth
keeping — it is the argument any future automatic-write proposal must clear.
What was wrong was the actuator, not that reasoning.

Why: This tool detected staleness and could not fix it, so every update
depended on an agent choosing to comply. It also could not see a whole class of
staleness at all. DEC-006 detects drift by evidence movement, which requires a
claim to cite evidence; a `Next` section cites nothing, because it describes the
future. Nothing can move underneath it, so a finished plan sits there looking
current forever. This repository's own STATE.md said "release the accumulated
work (tag, marketplace update)" across three tagged releases, and said v0.5.1
was untagged after it was tagged, while `review` reported zero defects.

The PR is what makes the fixing half admissible. DEC-004 rejected mechanical
writes because they "mark context as reviewed when nobody reviewed it, and
silently wrong documentation is worse than visibly stale documentation". That
still binds — and a pull request satisfies it rather than evading it, because
review is what a PR *is*. Nothing lands unread.

Evidence/context: `drift._detect_completed_intent`, `drift._project_versions`,
`cli.cmd_review` (`--exit-code`), `tests/test_drift.py`. CONFIRMED by running
`review` against this repository: three findings, all true, no false positives,
on prose that had been invisible to every other detector. The workflow this
entry describes was removed before release and is deliberately not cited — see
the supersession note above.

Alternatives considered: flagging any stale-looking intent, not only release
intent (rejected — a release is the one plan a repository records
unambiguously, as a tag; softer intents leave no trace and guessing at them
makes a worklist nobody reads). Block-scoped matching rather than
sentence-scoped and imperative-only (tried, and abandoned the same hour: two of
every three findings were notes that merely contained the word "release", and
the precision cost was measured here before the rule was tightened).
Auto-committing mechanical fixes to `main` (rejected — it is DEC-004's
mechanical `post-commit` finalize wearing a different hat). Gating the workflow
on any finding including INFO (rejected — a negative claim can never be
positively re-confirmed, so it is always listed, and the job would spend tokens
on every run forever).

Consequences: `review` is still not a gate, and `--exit-code` is opt-in so it
stays that way. A latent bug surfaced while building this and is fixed here:
version scanning trusted every `X.Y.Z` in the corpus, so documenting Repomix
`v1.18.0` made it the newest version "any context document mentions" and
silently disabled `VERSION_DRIFT`, a DEFECT-severity check, for this whole
repository. Versions are now filtered to those sharing a major with an existing
tag, which is a heuristic and will collide for a 1.x project citing a 1.x
dependency. The workflow's proposals inherit DEC-006's blind spot exactly: an
agent can re-stamp without re-reading, and a PR whose only diff is
`evidence.json` is both the normal outcome and what blind attestation looks
like. The PR body says so and asks reviewers to spot-check.

Date/commit if known: 2026-08-24

## DEC-011: Enforce the context ruling with a `Stop` hook, not a paid CI loop

Status: Accepted

Decision: Add a `Stop` hook that blocks the end of a turn — `decision: "block"`
with a `reason` the host hands back to the agent — when a commit has landed past
the context checkpoint and the turn has not ruled on whether project reality
changed. The agent already in the repository does the work. The `context-sync`
CI workflow from DEC-010 is demoted to optional.

Why: DEC-010 built the actuator as a GitHub Action driving a fresh agent through
an API key. That is the wrong shape for this tool. It costs money per run,
requires a secret, works only on GitHub, and reaches for a second agent while
the one that made the change is still sitting in the repository with the whole
task in its context. The right actuator is the agent already here.

`Stop` is what makes that enforceable rather than advisory. Claude Code's own
documentation draws the line: instruction files "are context, not enforced
configuration… to block an action regardless of what Claude decides, use a hook
instead." `AGENTS.md` has asked every agent to state a context conclusion since
v0.2.0, and this repository's STATE.md still went three releases stale, which is
the measurement that settles whether instructions alone are sufficient.

This is the path DEC-004 left open ("A `Stop`-based enforcement path remains
available if instructions prove insufficient"), not a reversal of it. DEC-004's
objection was to *asking every turn*, because the sync policy's default answer
is "update nothing" and a hook that says "nothing needed" most of the time
trains dismissal. The trigger here is a commit past the checkpoint — an event
the repository records, which cannot fire mid-edit however long a task runs.

Evidence/context: `cli.stop_notice`, `cli._states_context_conclusion`,
`skill/context-maintainer/hooks/stop.sh`, `hooks/hooks.json`,
`tests/test_hook_delivery.py`. CONFIRMED against the hooks documentation at
https://code.claude.com/docs/en/hooks (`stop_hook_active`, `decision: "block"`,
`last_assistant_message`) and by running `hook stop` against this repository in
both the silent and blocking states.

Alternatives considered: the DEC-010 CI loop as the primary path (superseded
here — kept as an optional extra, because a scheduled sweep still catches the
claims that go stale with no diff at all, which no per-turn hook can see).
Blocking on any uncommitted edit (rejected — that is normal mid-task state and
would fire every turn, which is DEC-004's objection restated). A `PreToolUse`
hook denying `git commit` until context is synced (rejected — it inverts the
order the sync policy actually wants, which is to judge a change after it
exists, and a denied commit is a far worse failure mode than a continued turn).
Detecting the conclusion by prose matching as the *trigger* (rejected — a closed
vocabulary, the failure DEC-006 names; the phrase list is used only to suppress
a block, where a miss costs one extra question and an over-match costs nothing).

Consequences: One registered hook can now block, and the hooks test asserts
exactly which three events are registered so a fourth has to be argued for.

Two guards keep the block from becoming nagging, and the second was learned the
hard way. The host's `stop_hook_active` stops a block repeating *within* a turn.
It does not stop it repeating *across* turns, because the trigger stays true
until someone runs `sync --finalize` — so the first real run blocked, was
answered, and blocked again next turn, with answering it changing nothing. The
fix is a marker in the gitignored cache recording the commit a ruling was given
for; new commits earn a fresh question, the same commit does not.

That marker is the one thing a hook here writes, and it is a narrow, deliberate
exception to DEC-007's "never writes": a disposable file saying "someone was
asked about commit X", never a context document, never the manifest, never an
attestation. It asserts nothing about whether the documents are correct, which
is the thing DEC-007 exists to prevent claiming without review. Deleting the
cache costs one extra question.

The block is answerable in one sentence — "no context update needed" ends it —
and that is the intended common outcome, not a failure. Codex has no `Stop` equivalent
wired, so this is Claude Code only, the same limitation the other hooks carry.
An agent can still satisfy the hook dishonestly by saying the words without
looking; that is DEC-006's blind spot again, and no hook closes it.

Date/commit if known: 2026-08-24
