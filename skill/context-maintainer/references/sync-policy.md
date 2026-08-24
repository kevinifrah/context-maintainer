# Sync policy

`sync` runs often, so its default answer is "nothing needs updating". Context
churn destroys trust in these documents as surely as staleness does: if every
commit rewrites them, nobody can tell what actually changed.

## Procedure

1. `context-maintainer sync --json` for commits and files changed since the
   checkpoint.
2. Classify the changes (below).
3. For each document you believe is affected, **read the relevant section
   first**. Never rewrite from memory.
4. `context-maintainer review --json`, and rule on every claim it lists.
5. Edit only sections that are genuinely now wrong.
6. `context-maintainer sync --finalize`, then `context-maintainer doctor
   --verify`.

Finalize even when nothing changed — that is what keeps the next `sync` cheap.

## Change-driven is not enough

Steps 1–3 are driven by what changed. That catches everything a commit makes
wrong, and nothing else — which leaves a whole category untouched: a claim in a
section no commit happened to touch, resting on a file that quietly moved on. A
test count. A "there is no release workflow" note written before someone added
one. Nothing in the diff points at these, so no amount of care in step 3 finds
them.

That is what step 4 is for, and why it is not optional. `review` lists the
claims whose evidence has moved since anyone confirmed them, and the ones that
rot in silence by construction — counts and assertions of absence. Rule on each:
correct it, or read the cited file and satisfy yourself it still holds.
Finalizing re-stamps what survived, so the same findings do not come back.

A claim you re-confirmed without reading the evidence is indistinguishable from
one you never looked at. That is the failure this step exists to prevent, and
the only person who can tell the difference is you.

## The context log

`--finalize --note "..."` appends one short entry to
`.context-maintainer/log.md`: the timestamp, the commit, which context files
changed (the CLI works that out itself), and your one-line reason.

Write the note as *why*, not *what* — the file list already says what.
"Storage moved to Postgres; ARCHITECTURE and DECISIONS updated" is useful;
"updated ARCHITECTURE.md" is not.

The log is capped at 20 entries and older history stays in Git, so it can never
become the sprawling changelog `STATE.md` is forbidden from being. If no context
file changed and you pass no note, nothing is recorded — a routine no-op sync
should leave no trace.

## What affects what

| Change | Usually update |
| --- | --- |
| CSS tweak, copy edit, formatting, lint fix | nothing |
| Dependency bump, no behaviour change | nothing (unless it forced a workflow change) |
| Refactor within a component | nothing (unless boundaries moved) |
| New service, module, or component | ARCHITECTURE, STATE |
| New external integration or API | ARCHITECTURE, STATE |
| Storage or persistence change | ARCHITECTURE, STATE, DECISIONS |
| Framework or language migration | ARCHITECTURE, STATE, DECISIONS, possibly WORKFLOWS |
| Auth model change | ARCHITECTURE, STATE, usually DECISIONS |
| Test, build, or lint command changed | WORKFLOWS |
| New deployment target or CI pipeline change | WORKFLOWS, sometimes ARCHITECTURE |
| Milestone completed | STATE |
| Work started on something new | STATE |
| Blocker hit or cleared | STATE |
| Product direction or scope change | PROJECT, STATE |
| Documented approach deliberately reversed | DECISIONS (supersede, never delete) |

This table is guidance, not a lookup table to apply mechanically. A one-line
change can be architecturally significant; a thousand-line change can be
cosmetic. Judge the change, not its size.

## STATE.md

Most syncs touch only this file, and it is a snapshot:

- Overwrite `Phase`, `Objective`, `Implemented`, `In Progress`, `Blockers`,
  and `Next`. Do not append.
- Never turn it into a changelog. If you find yourself adding dated entries,
  stop — that belongs in Git.
- Keep it short enough to read in under a minute.

## DECISIONS.md

- Append a new `## DEC-NNN:` entry, taking the next free number.
- Never edit history to make it look tidier.
- When a new decision replaces an old one, mark the old entry `Superseded` and
  link forward to the replacement.
- Only record decisions worth preserving. A decision worth recording is one a
  future contributor would otherwise reverse by accident.

## When incremental is not enough

If the changes since the checkpoint amount to a pivot, a large migration, or a
rewrite, incremental patching produces a document that is subtly wrong
throughout. Say so, and recommend `context-maintainer rebuild` rather than
attempting to patch section by section.

## Cost discipline

- Never re-scan the whole repository during `sync`. That is what `rebuild` is
  for.
- Prefer `git diff` and targeted reads over a fresh Repomix pass.
- Run `context-maintainer audit` during a sync only when a change is large
  enough that you genuinely cannot understand it from the diff.
