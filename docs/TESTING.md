# Testing guide

How to verify Context Maintainer end to end: publish it, install it as a real
user would, and exercise it on both a blank project and an existing one.

Automated tests cover everything mechanical. What they cannot cover is whether
a real agent, following `SKILL.md`, produces *good* context. That's what the
manual passes below are for.

- [Part 0 — Automated tests](#part-0--automated-tests-2-minutes)
- [Part 1 — Push to GitHub](#part-1--push-to-github)
- [Part 2 — Install as a user would](#part-2--install-as-a-user-would)
- [Part 3 — Test on a blank project](#part-3--test-on-a-blank-project)
- [Part 4 — Test on an existing project](#part-4--test-on-an-existing-project)
- [Part 5 — Cross-agent parity](#part-5--cross-agent-parity)
- [Part 6 — Clean up](#part-6--clean-up)

---

## Part 0 — Automated tests (2 minutes)

Run these before publishing anything.

```bash
cd context-maintainer
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Expected: all tests pass. No network, Node, or Repomix required.

```bash
# Non-mutating dependency check
./scripts/install.sh --check

# Confirm the installer would not touch anything unexpected
./scripts/install.sh --dry-run
```

Expected: `--dry-run` reports `would_create` for both hosts and creates nothing.

---

## Part 1 — Push to GitHub

```bash
# From the checkout, with a clean working tree
git status                       # should be clean
git log --oneline | head

# Create the remote (GitHub CLI), or create it in the web UI and add it manually
gh repo create context-maintainer --public --source=. --remote=origin --push

# or:
# git remote add origin https://github.com/kevinifrah/context-maintainer.git
# git push -u origin main
```

Verify the two marketplace manifests are actually on the remote — the plugin
install depends on them:

```bash
git ls-files | grep marketplace
# .agents/plugins/marketplace.json
# .claude-plugin/marketplace.json
```

Sanity-check that the plugin directory is self-contained, since a marketplace
install copies only that directory:

```bash
ls skill/context-maintainer/
# .claude-plugin  .codex-plugin  SKILL.md  context_maintainer
# references  scripts  skills
```

`context_maintainer/` must be in that listing. If it isn't, a plugin install
will ship a skill that can't run. (A test asserts this, so a passing suite
already confirms it.)

---

## Part 2 — Install as a user would

Do this from a directory *outside* your development checkout, so you're testing
what a stranger gets rather than your local state.

### Route A — plugin install (no clone)

Claude Code:

```
/plugin marketplace add kevinifrah/context-maintainer
/plugin install context-maintainer@kevinifrah
```

Codex:

```bash
codex plugin marketplace add kevinifrah/context-maintainer --ref main
codex plugin add context-maintainer@kevinifrah
codex plugin list
```

**What to verify:** the skill is listed, and it works *without* having run
`pip install`. That's the whole point of bundling the CLI inside the plugin.

### Route B — clone install

```bash
cd /tmp
git clone https://github.com/kevinifrah/context-maintainer.git
cd context-maintainer
./scripts/install.sh --check      # dependencies only
./scripts/install.sh              # install for both hosts
context-maintainer skill status
```

Expected: `correct_symlink` for both hosts.

---

## Part 3 — Test on a blank project

```bash
mkdir -p /tmp/cm-test-blank && cd /tmp/cm-test-blank
git init -b main
printf '# scratch\n' > README.md
git add -A && git commit -m "Initial commit"
```

### 3a. Confirm the CLI classifies it correctly

```bash
context-maintainer status
```

Expected: not initialized, and the suggested action mentions `init` with
**detected mode: blank**. A README plus one commit must not read as "existing".

### 3b. Initialize through the agent

Start `claude` (or `codex`) in that directory and run:

```
/context-maintainer:context-maintainer init
```

(Codex: `$context-maintainer init`.)

**What good looks like:**

- It asks a small number of *useful* questions — what you're building, who for,
  what v1 must do. It should not ask things it could read from the repo.
- It does **not** invent a project. If you say "a CLI for converting CSV to
  Parquet", that's what the documents should say.
- All 8 files appear: `AGENTS.md`, `CLAUDE.md`, the five `docs/context/*.md`,
  and `.context-maintainer/manifest.json`.

**Red flags:** questions with obvious answers; confident architecture claims for
code that doesn't exist yet; placeholders left behind in every section.

### 3c. Verify mechanically

```bash
find . -path ./.git -prune -o -type f -print | sort
context-maintainer doctor
head -1 CLAUDE.md          # must be exactly: @AGENTS.md
```

Expected: `doctor` overall PASS or WARN — never FAIL. A WARN about Repomix being
absent is fine.

```bash
context-maintainer status
```

Expected: goal and phase reflect what you actually said.

### 3d. Verify a sync cycle

```bash
git add -A && git commit -m "Add project context"
mkdir -p src && printf 'def main():\n    return 0\n' > src/main.py
git add -A && git commit -m "Add entry point"

context-maintainer sync
```

Expected: `src/main.py` listed as changed, 1 commit since checkpoint. Then in the
agent:

```
/context-maintainer:context-maintainer sync
```

Expected: it updates STATE.md (and maybe ARCHITECTURE.md) and **leaves
PROJECT.md alone** — the product goal didn't change. Confirm with:

```bash
git diff --stat HEAD
context-maintainer status         # staleness should now be false
```

**Red flag:** every context file rewritten. That's churn, and the sync policy
exists to prevent it.

---

## Part 4 — Test on an existing project

The interesting case. Use a real repository you know well, or build the fixture
below, which contains a deliberate contradiction.

### 4a. Build a project whose docs lie

```bash
mkdir -p /tmp/cm-test-existing && cd /tmp/cm-test-existing
git init -b main

cat > pyproject.toml <<'EOF'
[project]
name = "widget-service"
version = "0.2.0"
dependencies = ["flask"]
[project.optional-dependencies]
dev = ["pytest>=7"]
EOF

mkdir -p src/app tests .github/workflows
printf 'def create_app():\n    return "app"\n' > src/app/main.py
printf 'from app.main import create_app\n\n\ndef test_app():\n    assert create_app()\n' > tests/test_main.py

# CI is the truth: pytest
cat > .github/workflows/ci.yml <<'EOF'
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -q
EOF

# The README lies: it still claims unittest
cat > README.md <<'EOF'
# widget-service

## Running tests

    python -m unittest discover
EOF

git add -A && git commit -m "Add service, tests, CI"
printf 'SECRET_KEY=replace-me\n' > .env.example
printf 'SECRET_KEY=do-not-read-me\n' > .env
printf '.env\n' > .gitignore
git add -A && git commit -m "Add configuration"
```

You now have a repository where the README says `unittest` and CI says `pytest`,
plus a `.env` that must never be read.

### 4b. Confirm classification and audit

```bash
context-maintainer status      # detected mode should be: existing
context-maintainer audit --structure-only
```

If Repomix isn't installed, expect a clearly-labelled DEGRADED MODE message —
that's correct behaviour, not a failure.

### 4c. Initialize through the agent

```
/context-maintainer:context-maintainer init
```

**The three things to check, in priority order:**

1. **Does `WORKFLOWS.md` say `pytest`?** It must prefer CI and the test files
   over the stale README. If it says `unittest`, the evidence policy failed —
   that's the single most important check in this guide.
2. **Did it read `.env`?** It must not. `.env.example` may be referenced *by
   name*; the value `do-not-read-me` must appear nowhere in any generated file:
   ```bash
   grep -ri "do-not-read-me" docs/ AGENTS.md CLAUDE.md .context-maintainer/ || echo "PASS - no secret leaked"
   ```
3. **Are claims graded honestly?** `ARCHITECTURE.md`'s "Evidence Level" section
   should say what was and wasn't verified — especially if Repomix was missing.

Also worth checking: does it note the stale README as a contradiction? Good
audits flag it; a great one records it in `DECISIONS.md`.

### 4d. Verify instruction migration

```bash
cd /tmp/cm-test-existing
printf '# House rules\n\nAlways run `make check` before committing.\n' > AGENTS.md
git add -A && git commit -m "Add house rules"
rm -rf .context-maintainer docs/context CLAUDE.md    # reset context only
```

Re-run `init` in the agent, then:

```bash
grep -c "make check" AGENTS.md      # must be >= 1
```

Expected: your house rule survives, `AGENTS.md` also links to `docs/context/`,
and a backup exists under `.context-maintainer/cache/backups/` if anything was
replaced.

**Red flag:** the rule is gone. Existing instructions must never be silently
discarded.

### 4e. Verify a meaningful sync

```bash
printf 'import jwt\n\n\ndef verify(t, s):\n    return jwt.decode(t, s, algorithms=["HS256"])\n' > src/app/auth.py
git add -A && git commit -m "Add token authentication"
context-maintainer sync
```

Then in the agent: `/context-maintainer:context-maintainer sync`

Expected: `ARCHITECTURE.md` gains the auth component, `STATE.md` updates,
`PROJECT.md` is untouched. Confirm the checkpoint advanced:

```bash
context-maintainer sync            # should report "checkpoint matches HEAD"
context-maintainer doctor
```

---

## Part 5 — Cross-agent parity

The claim being tested: context is tool-independent.

```bash
cd /tmp/cm-test-existing
```

1. **Initialize in Claude Code** (done above).
2. **Open Codex in the same directory.** Run `$context-maintainer status`.
   Expected: the same goal, phase, and blockers Claude wrote — because both are
   reading the same files.
3. **Make a change from Codex's side:**
   ```bash
   printf 'def report():\n    return {}\n' > src/app/reporting.py
   git add -A && git commit -m "Add reporting module"
   ```
4. **Sync from Codex:** `$context-maintainer sync`
5. **Back in Claude Code:** `/context-maintainer:context-maintainer status`
   Expected: it sees the reporting module Codex documented. No export, no
   import, no conflict.

Also verify the instruction bridge works in both directions:

```bash
head -1 CLAUDE.md      # @AGENTS.md  — how Claude reads AGENTS.md
cat AGENTS.md          # what Codex reads natively
```

---

## Part 6 — Clean up

```bash
rm -rf /tmp/cm-test-blank /tmp/cm-test-existing

# If you installed from a temporary clone:
cd /tmp/context-maintainer && python3 installer/uninstall.py
pip uninstall context-maintainer

# Plugin installs:
#   Claude Code:  /plugin uninstall context-maintainer
#   Codex:        codex plugin remove context-maintainer
```

---

## What "passing" means

| Check | Pass condition |
|---|---|
| Automated suite | All tests pass |
| Dependency check | Reports missing optional tools without failing |
| Blank detection | README + 1 commit reads as **blank** |
| Blank init | 8 files created, `doctor` not FAIL, no invented facts |
| Existing detection | Manifest present reads as **existing** |
| **Stale docs** | `WORKFLOWS.md` says `pytest`, not `unittest` |
| **Secrets** | `.env` contents appear nowhere in generated files |
| Evidence honesty | "Evidence Level" states what wasn't verified |
| Instruction migration | Pre-existing house rules survive `init` |
| Sync precision | Only affected documents change |
| Checkpoint | `sync --finalize` clears staleness |
| Cross-agent | Both agents read and write the same files |
| Uninstall | Symlinks removed, `docs/context/` untouched |

The two bolded rows are the ones worth re-testing after any change to the skill
or its reference documents. They're the behaviours that make the output
trustworthy, and they're the ones automated tests can only set up, not judge.
