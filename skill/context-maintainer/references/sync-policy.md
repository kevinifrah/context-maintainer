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
4. Edit only sections that are genuinely now wrong.
5. `context-maintainer sync --finalize`, then `context-maintainer doctor`.

Finalize even when nothing changed — that is what keeps the next `sync` cheap.

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
