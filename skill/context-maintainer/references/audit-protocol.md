# Audit protocol (existing projects)

Used by `init` on an existing repository, and by `rebuild`. The goal is to
understand the project well enough to write context that is true, before
writing anything.

Do not create or edit context documents until step 7.

## 1. Establish ground truth cheaply

```bash
context-maintainer status --json      # already initialized? what is claimed?
context-maintainer sync --json        # if initialized: what changed since when
```

Read what already exists before forming your own view: `README`, any
`AGENTS.md` / `CLAUDE.md` / rule files, `docs/`, and the dependency manifests.
Treat all of it as *claims to verify*, not facts.

## 2. Structure pass

```bash
context-maintainer audit --structure-only --json
```

Cheap metadata/tree pass, no file contents. Use it to learn the shape of the
repository: top-level layout, where source lives, where tests live, how big the
thing actually is.

If this reports `degraded_mode: true`, Repomix is unavailable. Continue with
Git and direct reading, and remember to record reduced confidence at step 7.

## 3. Manifests, configuration, and CI

Read directly — these are the highest-value-per-token files in any repository:

- dependency manifests and lockfiles → stack, frameworks, real versions
- CI/CD definitions → the commands the project actually runs, which is far
  more reliable than a README's claims
- container, infrastructure, and deployment configuration
- `.env.example` (never `.env`) → what configuration exists, by name only
- test configuration → how tests are meant to run

Most of `WORKFLOWS.md` comes from here. A command in CI is CONFIRMED; a command
only in a README is a claim to check.

## 4. Full pass, when the structure pass is not enough

```bash
context-maintainer audit --full --json
```

Compressed sources plus git logs and diffs. Use it when you need to understand
execution flows rather than just layout. Prefer targeted reading of the files
the structure pass identified as important over dumping everything.

## 5. Git history

```bash
git log --oneline -40
git log --diff-filter=A --oneline -- <important paths>   # when did this arrive
```

History answers questions nothing else can: what is actively being worked on,
what was migrated away from, what was abandoned. Look for migrations, renames,
reverts, and long-lived branches. These are where DECISIONS entries come from —
label anything reconstructed this way as INFERRED.

## 6. Structural verification, if available

If a structural-analysis companion is configured — see
`references/mcp-companion.md` — use its tools (`definition`, `references`,
`hover`, `diagnostics`) to confirm claims about what calls what, rather than
inferring call graphs from grep. This upgrades architecture claims from
INFERRED to CONFIRMED.

If it is not configured, do not pretend to a call graph you have not verified.

## 7. Synthesise, then write

Build the model first, in your head or in notes — not in the documents. It
should cover: project identity and purpose; the evidence for that purpose;
stack; architecture and major components; important execution flows; data
stores; integrations; dev/test/deploy workflows; recent direction; historical
decisions and migrations; current state; unresolved questions; and any
contradictions found.

Then write the documents, applying `references/evidence-policy.md` to every
claim. Grade honestly. State unknowns.

Record in ARCHITECTURE.md's "Evidence Level" section: which passes ran, what
was unavailable, and where confidence is weakest. If Repomix was missing or the
audit was partial, say so there.

## 8. Migrate instructions, do not overwrite them

If `init` reported `existing_agent_files`, follow the migration rules in
`SKILL.md`. Preserve real house rules, deduplicate, put cross-agent rules in
`AGENTS.md`, keep Claude-specific ones in `CLAUDE.md` below the `@AGENTS.md`
import, and never discard something meaningful silently.

## 9. Verify your own work

```bash
context-maintainer doctor
context-maintainer sync --finalize
```

`doctor` catches placeholders left behind, missing sections, a broken
`CLAUDE.md` → `AGENTS.md` bridge, and broken links. Fix what it finds, then
advance the checkpoint so the next `sync` is incremental.

## Keep the cache out of the way

Raw audit artifacts belong in `.context-maintainer/cache/` and stay
git-ignored. The canonical output of an audit is the human-readable context
documentation — never the raw dump.
