# Enforcing context in CI

Instructions ask an agent to keep context current. CI is what makes it
non-optional.

## The command

```bash
context-maintainer doctor --verify --strict
```

Exit 1 when the context documents are broken or contradicted by the repository;
exit 0 otherwise.

## What fails the build, and what does not

`--strict` promotes warnings to failures — but only warnings about the
**context itself**. Warnings about the surrounding environment are always true
in CI and say nothing about whether your documents are correct, so promoting
them would make `--strict` useless for the one job it exists to do.

**Fails the build:**

| Check | Why it should block |
|---|---|
| `required_files` | A context document is missing |
| `manifest_present` / `manifest_schema` | Metadata is corrupt |
| `claude_agents_bridge` | `CLAUDE.md` no longer imports `AGENTS.md`, so Claude Code sees nothing |
| `required_sections` | The contract has been broken |
| `no_placeholders` | Context was scaffolded but never filled in |
| `decisions_entries` | No decisions recorded at all |
| `checkpoint_valid` | The recorded commit does not exist (rewritten history) |
| `referenced_paths` | Documents link to files that are gone |
| `no_duplication` | `AGENTS.md` has become a knowledge dump |
| `claims_verified` | **A documented claim is contradicted by the repository** |
| `context_drift` (FAIL only) | **A claim cites a file or commit that does not exist, or the repository is tagged newer than any context document describes.** Its WARN is advisory — see below |
| `plugin_manifests` | Only relevant when developing the tool itself |
| `decisions_index` | `DECISIONS.md` outgrew a whole-file read and its generated index is missing or stale |

**Never fails the build** (`ADVISORY_CHECKS`):

| Check | Why it must not block |
|---|---|
| `repomix_available` | Optional dependency; absent on most CI runners |
| `mcp_language_server` | Optional dependency |
| `skill_installation` | CI has no agent host installed |
| `checkpoint_freshness` | A pull request is legitimately ahead of the last sync |
| `state_freshness` | Punishing an unrelated PR because nobody confirmed STATE recently is the wrong lever |
| `context_size` | Context over budget is expensive, not wrong. Blocking a PR because a document grew 1 KiB is the noise DEC-005 exists to avoid |
| `context_drift` (WARN only) | A claim's evidence moved. Unverified is not wrong — see below |

### What `context_drift` deliberately does *not* fail on

`context_drift` is the only check that appears in both tables, because it emits
both kinds of result. A citation pointing at nothing is a defect and fails the
build. A claim whose evidence merely *moved* is **unverified, not wrong**, and
is listed in `ADVISORY_CHECKS` so `--strict` never promotes it.

That second half is not a concession to noise. If staleness failed the build,
the cheapest way back to green would be `context-maintainer sync --finalize` —
re-stamping the ledger without re-reading a single claim. The gate would then
actively reward the one failure mode this whole mechanism cannot detect (see
DEC-006's Consequences). A check that pays people to lie to it is worse than no
check.

So the split is: `doctor` fails on what is unambiguously broken, `review` asks
about what needs a ruling. If you want to enforce the worklist anyway, run
`context-maintainer review --json` and gate on the counts yourself — but be
aware you are building that incentive.

## GitHub Actions

```yaml
name: Context

on: [push, pull_request]

jobs:
  context:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # doctor needs history to judge the checkpoint
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/kevinifrah/context-maintainer@v0.3.0
      - run: context-maintainer doctor --verify --strict
```

`fetch-depth: 0` matters. A shallow clone has no history, so checkpoint checks
cannot resolve and you get noise instead of signal.

## GitLab CI

```yaml
context:
  image: python:3.12
  variables:
    GIT_DEPTH: 0
  script:
    - pip install git+https://github.com/kevinifrah/context-maintainer@v0.3.0
    - context-maintainer doctor --verify --strict
```

## Pre-commit

Faster feedback, and it catches drift before it reaches CI. Structural only —
verification needs the full repository, which a staged-files hook does not see.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: context-maintainer
        name: Validate project context
        entry: context-maintainer doctor
        language: system
        pass_filenames: false
```

## Rolling it out without a red build on day one

Turning on `--strict` in an established repository usually surfaces real
problems immediately. Two sane approaches:

**Report first.** Run without `--strict` (or with `continue-on-error: true`) for
a week to see what it finds and how many are false positives on your codebase.
Then make it blocking.

**Fix, then enforce.** Run it locally, fix what it reports, and turn on blocking
in the same change. This is what this repository does — its own CI runs
`doctor --verify --strict` as a required job, so its context cannot silently
drift.

## When verification is wrong

It will sometimes be. `--verify` is mechanical: it looks for marker files,
dependency entries, and source usage. A claim can be true while its evidence is
invisible to that — an internal service, a runtime dependency installed by
something CI cannot see.

Two honest fixes, in preference order:

1. **Reword so it is not asserted as current fact.** "Deployed via an internal
   Kubernetes operator (not visible in this repository)" is accurate, and
   parses as UNVERIFIED rather than CONTRADICTED.
2. **Record it as history if that is what it is.** Lines containing
   "previously", "migrated away", "no longer" are exempt by design.

What not to do is delete the claim to make the check pass. The point is accurate
documentation, not a green tick.
