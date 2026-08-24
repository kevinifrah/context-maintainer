---
name: context-maintainer
description: Create and maintain durable project context (docs/context/PROJECT.md, ARCHITECTURE.md, WORKFLOWS.md, STATE.md, DECISIONS.md plus AGENTS.md and CLAUDE.md) so any coding agent can quickly understand a project. Use for init, status, sync, review, doctor, and rebuild of a repository's context, and whenever project reality has changed enough that the recorded context is now wrong.
license: MIT
---

# Context Maintainer

Keep an accurate, compact, durable understanding of a software project in the
repository itself, so Claude Code and Codex both start from the same truth.

## Division of labour

The `context-maintainer` CLI does everything mechanical. You do everything that
needs judgment.

| CLI (deterministic) | You (semantic) |
| --- | --- |
| Detect repo root, blank vs existing | Decide what the project *is* and why it exists |
| Scaffold files, manage the manifest | Write the prose in each document |
| List commits/files changed since checkpoint | Decide which of those changes actually matter |
| Validate structure (`doctor`) | Grade evidence CONFIRMED / INFERRED / UNKNOWN |
| Gather Repomix evidence (`audit`) | Read that evidence and synthesise a model |
| List claims whose evidence moved (`review`) | Rule on whether each is still true |

Never ask the CLI to reason. Never do by hand what the CLI already does.

Run the CLI as `context-maintainer <command>`. If that is not on PATH, use
`python3 -m context_maintainer <command>`, or `scripts/cm.sh <command>` from
this skill directory. Add `--json` when you want structured output to reason
over.

## Before anything else

Run `context-maintainer status --json`. It tells you whether the repository is
initialized, what the context currently claims, and whether it is stale. Let
that decide which command below applies.

## init

Establishes the context contract. Refuses to run twice — if already
initialized, use `sync` or `rebuild` instead.

1. `context-maintainer init --json`. It reports `mode` (blank or existing),
   the detection `evidence`, files `created`, files `preserved`, and any
   `existing_agent_files` it found.
2. **If `mode` is `blank`:** gather what is genuinely missing, then write the
   documents. Reuse anything the current conversation already told you. Ask
   only about what you cannot infer — typically: what are we building, who is
   it for, what problem does it solve, what must v1 do, known constraints.
   Never ask a question the repository or conversation has already answered.
3. **If `mode` is `existing`:** do not write documents yet. Follow
   `references/audit-protocol.md` first, then write them from that evidence.
   The audit tells you what the project *is*; it cannot tell you what is
   *planned* — so confirm intent before writing. See "Confirming intent" below.
4. **If `existing_agent_files` is non-empty:** migrate rather than replace.
   See "Migrating existing instructions" below.
5. Replace every `<!-- CONTEXT-MAINTAINER: PLACEHOLDER -->` marker with real
   content, or an explicit, honest statement of what is unknown.
6. Finish with `context-maintainer doctor` and fix what it reports.

The structure is worthless until the content is real. `init` is not done when
the files exist; it is done when they are true.

## status

Read-only briefing, suitable for someone returning after weeks away.

1. `context-maintainer status --json`.
2. Read `docs/context/PROJECT.md` and `docs/context/STATE.md` for anything the
   summary flattened.
3. Report: goal, current phase, architecture in a sentence or two, current
   objective, blockers, notable recent changes, whether context looks stale,
   and the most sensible next actions.

Change nothing. If the context is stale, say so and recommend `sync` — do not
quietly fix it here.

## sync

Incremental maintenance. This is the command that runs most often, so it must
stay cheap and must not churn the documents.

1. `context-maintainer sync --json` — gives commits and files changed since the
   recorded checkpoint, plus uncommitted work and a `claims_to_adjudicate`
   count.
2. Decide which documents, if any, those changes affect. Follow
   `references/sync-policy.md`. Most changes affect nothing.
3. Read a section before concluding it is unaffected. Do not diff prose from
   memory.
4. **`context-maintainer review --json` — adjudicate every claim it lists.**
   These are claims that may have stopped being true without any commit
   contradicting them, so nothing in step 1 will point at them. See `review`
   below.
5. Edit only the sections that are genuinely now wrong. Leave everything else
   byte-identical.
6. `context-maintainer sync --finalize --note "<one line on what changed
   and why>"` to advance the checkpoint, record the update, and re-stamp the
   evidence each document now rests on.
7. `context-maintainer doctor --verify` to confirm you left the contract valid
   *and* left no claim contradicted or citing something that does not exist.

Never re-scan the whole repository during `sync`. If a change is large enough
that incremental reasoning fails, say so and recommend `rebuild`.

## review

The claims worklist. `doctor` asks whether the documents are well-formed;
`review` asks whether they are still *true*, and hands you the specific
sentences to rule on.

1. `context-maintainer review --json`.
2. **Rule on every finding.** For each one, either correct the claim or satisfy
   yourself it is still true. Read the cited file — this is exactly the moment
   "I'm sure it's fine" produces a wrong document.
3. Re-confirm what survived with `context-maintainer sync --finalize --note
   "..."`. That re-stamps the evidence baseline; until you do, the same
   findings come back next session.

What the findings mean:

| Kind | What it is telling you |
| --- | --- |
| `DANGLING_CITATION` | A cited file or commit does not exist. Always a defect — fix the citation. |
| `VERSION_DRIFT` | The repository is tagged newer than anything the documents describe. |
| `STALE_EVIDENCE` | The file this claim cites has changed since anyone confirmed the claim. It may still be true; nobody has checked. |
| `VOLATILE_NUMBER` | A count ("415 tests"). Nothing edits that sentence when the number changes. |
| `NEGATIVE_CLAIM` | An assertion that something is absent. No positive evidence can ever re-confirm it, and nothing announces itself when it stops being true. |
| `COVERAGE_GAP` | Something real (a CI job) that the documents describe none of, while describing its siblings. |
| `UNATTESTED` | No baseline recorded yet. Finalize once to start tracking. |

Finalizing clears staleness. It never clears a defect — a dangling citation
still fails `doctor` afterwards, on purpose, so re-stamping cannot be used to
make a broken document look clean.

## doctor

1. `context-maintainer doctor --verify --json`. Use `--verify`: without it,
   `doctor` checks only *form*, and a document can pass every structural check
   while being false throughout.
2. Report PASS / WARN / FAIL per check, with the remediation the CLI supplies.
3. Fix only what the user asks you to fix. `doctor` diagnoses; it does not
   silently repair.

A WARN for a missing Repomix or MCP companion is not a defect — it means
reduced capability, and you should say which. Nor is `context_size`: it means
the context is getting expensive to read, and the fix is to cut, never to
reorganise into more files. A tree of small documents costs more to navigate
than a few compact ones.

`decisions_index` means `DECISIONS.md` outgrew a whole-file read. The index is
generated from the `## DEC-NNN:` headings — regenerate it with `sync
--finalize`, and never hand-edit it.

`--verify` adds two checks that judge content rather than structure:
`claims_verified` (is a documented command or technology contradicted by the
repository?) and `context_drift` (has a claim outlived the evidence it cites?).
A CONTRADICTED claim means either the document is wrong or the evidence is not
machine-visible — reword rather than delete, and never delete a claim merely to
make a check pass.

## rebuild

The exceptional full re-audit: after a major pivot, a large migration, a
contract version change, or when the first initialization was poor.

1. `context-maintainer rebuild --prepare --json` — backs up every context file
   first.
2. Re-run the full audit in `references/audit-protocol.md` against current
   evidence.
3. Rewrite the documents from that evidence.
4. **Preserve decision history.** Carry every meaningful entry in
   `DECISIONS.md` forward. Mark what reality has overtaken as `Superseded` and
   link the decision that replaced it. Never delete a decision because it is
   no longer current.
5. `context-maintainer rebuild --finalize --note "<why a rebuild was
   needed>"`, then `doctor`.

## Confirming intent

Evidence in a repository answers "what is this?". It does not answer "where is
this going?". Git history shows what happened, not what was decided to happen
next. So four fields cannot be responsibly derived from code alone:

- `STATE.md` → **Objective** (what is being worked on *now*)
- `STATE.md` → **In Progress**
- `STATE.md` → **Blockers**
- `STATE.md` → **Next**

Plus, often, `PROJECT.md` → Success Criteria and open product questions.

After the audit and before finalising the documents, present what you found and
ask about only those gaps. Keep it short — a handful of specific questions,
informed by the audit, not a questionnaire:

> I audited the repository. Here is what I am confident about:
> — it is a Flask service for turning widget orders into fulfilment jobs
> — tests run with `pytest -q` (CI confirms it; the README is stale and still
>   says unittest)
> — token auth was added recently, in the last few commits
>
> Three things the code cannot tell me:
> 1. What are you working on right now?
> 2. Anything blocking you?
> 3. What is the next meaningful milestone?
>
> I will record your answers in STATE.md. If you would rather not say, I will
> mark those sections UNKNOWN rather than guess.

Rules for this step:

- **Ask about gaps, not about things you already established.** A question with
  an answer visible in the repository wastes the user's attention and damages
  trust in the rest of your questions.
- **Reuse the conversation.** If the user already said what they are building
  or what is next, do not ask again.
- **Never block on it.** If the user does not answer, or says "just do your
  best", write UNKNOWN in those sections. An honest UNKNOWN is correct; an
  invented objective is not.
- **Offer your inference, ask for confirmation.** "Recent commits suggest you
  are mid-way through adding auth — is that the current objective?" is better
  than an open question, and better than silently writing it as fact.
- **Label what came from the user.** Their answers are CONFIRMED (they are the
  authority on intent); your reconstruction from commits is INFERRED.

The same applies, more briefly, during `sync`: if changes since the checkpoint
show a milestone finished or a new direction started, confirm what comes next
rather than inferring it. One question is usually enough.

## Migrating existing instructions

When a repository already has `AGENTS.md`, `CLAUDE.md`, nested agent files, or
rule files such as `.cursorrules`:

- Read them before touching them. `init` preserves them rather than
  overwriting, and reports them to you.
- Keep every instruction that still holds. Losing a real house rule is far
  worse than leaving the file untidy.
- Deduplicate: one rule, stated once, in the right place.
- Cross-agent rules belong in root `AGENTS.md`. Genuinely Claude-specific
  instructions stay in `CLAUDE.md`, below its first line.
- `CLAUDE.md` must begin with `@AGENTS.md` — that import is what lets one set
  of instructions serve both agents.
- Back up before any destructive rewrite; the CLI writes backups under
  `.context-maintainer/cache/backups/`.
- The result should be *cleaner* than the original, not merely longer.

## Report the decision, every time

After any piece of work that touched the repository, decide whether project
reality changed — and **say which**. Either name what you updated, or state
plainly that no context update was needed.

This matters because a skipped check and a completed check look identical from
outside. "No context update needed — this was a refactor within one component"
is a useful sentence. Silence is not.

Most work needs no update. Saying so is the correct outcome, not a failure to
act. The change→document mapping is in `references/sync-policy.md`.

One thing is worth recording even when nothing else is: an approach you
**tried and abandoned**. Git keeps what shipped, not what failed, so the next
session rediscovers the same wall. Put it in the `Alternatives considered:`
field of the decision for what you did ship — but only if it was genuinely
attempted, failed for a reason particular to this project, and someone would
plausibly try it again. `references/sync-policy.md` states those three tests.

## Non-negotiables

- **Evidence over convenience.** Never promote an assumption to a documented
  fact to make a document look finished. See `references/evidence-policy.md`.
- **Current code beats stale documentation.** When a README and the source
  disagree, the source wins and the discrepancy is worth a note.
- **Never read secret values.** Recording that a mechanism exists is fine;
  reading `.env` to see what is in it is not.
- **`STATE.md` is a snapshot, not a log.** Overwrite it. History lives in Git.
- **Context has a budget.** Every document competes for the same attention as
  the work itself. Before adding a paragraph, ask what it displaces. Prose that
  cites nothing is the first thing to cut: it is the most expensive to read and
  the only kind `review` can never check.
- **`AGENTS.md` is a router, not a knowledge base.** It links to
  `docs/context/`; it does not restate it.
- **Do not silently reverse a documented decision.** Record a new one that
  supersedes it.
- **Say when you are degraded.** If Repomix is unavailable or the audit was
  partial, record reduced confidence in ARCHITECTURE.md's "Evidence Level"
  section rather than implying completeness.

## References

- `references/context-contract.md` — every required file and section
- `references/evidence-policy.md` — CONFIRMED / INFERRED / UNKNOWN
- `references/audit-protocol.md` — the existing-project audit, step by step
- `references/sync-policy.md` — which changes affect which documents
- `references/mcp-companion.md` — the optional structural-analysis companion
