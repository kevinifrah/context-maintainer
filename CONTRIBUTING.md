# Contributing to Context Maintainer

Thanks for considering a contribution. This document covers how to work on the
project and, more importantly, the two design boundaries that keep it coherent.

## Development setup

```bash
git clone https://github.com/kevinifrahpro/context-maintainer.git context-maintainer
cd context-maintainer

python3 -m venv .venv
source .venv/bin/activate          # Windows: not supported, use WSL
pip install -e ".[dev]"

pytest -q
```

You need Python 3.9+ and Git. You do **not** need Node, Repomix, a language
server, or network access to run the test suite — Repomix is exercised through
a stub binary, and installer tests run against a fake `$HOME`.

Try the CLI against a throwaway repository rather than a real project:

```bash
mkdir /tmp/scratch && cd /tmp/scratch && git init
git commit --allow-empty -m "Initial commit"
context-maintainer init
context-maintainer doctor
```

## The two rules that matter

### 1. Keep the CLI/skill boundary intact

| Belongs in the CLI (Python) | Belongs in the skill (Markdown) |
|---|---|
| Anything with one correct answer | Anything requiring judgment |
| Detecting repo root, git state | Deciding what a change *means* |
| Creating files, managing the manifest | Writing the prose in them |
| Listing what changed since a checkpoint | Deciding which of it matters |
| Structural validation | Grading evidence confidence |

If you find yourself writing a heuristic in Python that guesses at intent, it
probably belongs in the skill. If you find yourself writing instructions telling
an agent to compute something mechanical, it probably belongs in the CLI.

The CLI must never embed reasoning, and must never require an LLM to run.

### 2. Never let the tool overstate itself

The whole value proposition is that the documents can be trusted. So:

- A missing optional dependency degrades capability **and says so**. It never
  silently falls back to guessing.
- An unknown is recorded as UNKNOWN, not filled in with something plausible.
- If a capability is unverified, the README says it is unverified.

A feature that makes output look more complete than the evidence supports is a
regression, even if every test passes.

## Adding a `doctor` check

`doctor` checks are pure functions of a repository path:

```python
def check_something_specific(root: Path) -> CheckResult:
    """One sentence on what this catches and why it matters."""
    if not_applicable:
        return CheckResult("something_specific", PASS, "Not applicable (…).")
    if broken:
        return CheckResult(
            "something_specific",
            FAIL,
            "What is wrong, concretely.",
            "The exact command or edit that fixes it.",
        )
    return CheckResult("something_specific", PASS, "What was verified.")
```

Then append it to `CHECKS` in `src/context_maintainer/doctor.py` and add tests
covering the PASS, WARN, and FAIL paths.

Guidelines:

- **FAIL means the contract is broken** — a missing file, an invalid manifest, a
  severed `@AGENTS.md` bridge. FAIL means "this repository's context cannot be
  trusted".
- **WARN means degraded or untidy but functional** — leftover placeholders, a
  missing optional dependency, drifting staleness.
- **A missing optional dependency must never FAIL.**
- Always supply actionable remediation. "Something is wrong" is not a check.
- Checks never modify anything. `doctor` diagnoses.
- Update the count in the README if you change how many checks exist — a test
  asserts the two agree.

## Changing the context contract

The contract is defined once, in `src/context_maintainer/contract.py`, and
mirrored in prose in `skill/context-maintainer/references/context-contract.md`.

A test parses the prose and asserts it equals the Python definition, so **you
must change both together**. That guard exists because a contract the code
enforces and the documentation describes differently is worse than either alone.

If you add a required section, also update the corresponding template in
`src/context_maintainer/templates/` — another test asserts every template
satisfies the contract it is generated from.

## Changing the skill

`SKILL.md` stays under ~500 lines; detail goes in `references/`. Use only the
portable frontmatter fields (`name`, `description`, `license`, `compatibility`,
`metadata`, `allowed-tools`) — anything else breaks packaging outside Claude
Code, and a test enforces it.

There is exactly one real `SKILL.md` in the repository. The copy under
`skill/context-maintainer/skills/context-maintainer/` is a symlink, because
Codex expects that nesting and plain-skill discovery expects the root. Do not
replace it with a second file; a test asserts only one real file exists.

## Testing conventions

- Test names state the behaviour, not the function: `test_blank_repo_with_only_readme_license_gitignore_returns_blank_mode`.
- No network, no Node, no real Repomix, ever.
- Never touch the real `~/.claude` or `~/.agents`. Use the `fake_home` fixture.
- No secrets in fixtures, including plausible-looking fake ones. `.env.example`
  with obvious placeholders is fine.
- Prefer asserting on specific paths and messages over counts — counts break for
  uninteresting reasons.

Run the full suite before opening a pull request:

```bash
pytest -q
```

## Pull requests

- One coherent change per PR.
- Include tests for behaviour changes.
- Update the README when you change user-facing behaviour, and the relevant
  `references/*.md` when you change what the skill should do.
- Note in the description if you changed anything about the security posture,
  the CLI/skill boundary, or the contract.

## Reporting security issues

If you find a security problem in Context Maintainer itself, please open an
issue describing the impact without including working exploit details or real
credentials.

Separately: if you find that a dependency this project recommends has become
untrustworthy, that is squarely in scope and worth reporting. This project
already rejected one previously-specified dependency on security grounds (see
the security note in the README), and the same scrutiny should apply to
everything it suggests — including its optional tools.

## Design principles, in priority order

1. Reliability
2. One canonical project context
3. Claude Code + Codex compatibility
4. Simple user experience
5. Safe handling of existing repositories
6. Evidence-based context
7. Incremental maintenance over repeated full scans
8. Local, free, open-source operation
9. Low token waste
10. Extensibility

When two of these conflict, the earlier one wins. Notably: a clever abstraction
that makes v1 harder to understand loses to a simpler design, and extensibility
never justifies adding a layer with no current implementation behind it.

## Anti-goals

Context Maintainer is deliberately **not**: an autonomous coding framework, a
task or project management system, an SDLC methodology, a memory-bank
framework, a hosted service, a vector store, a replacement for Git, or a
reimplementation of Repomix. It maintains an accurate, compact, durable
description of a software project. That is the whole job.
