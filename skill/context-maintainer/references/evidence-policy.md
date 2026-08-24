# Evidence policy

A context document is only useful if it can be trusted. That means every claim
carries a confidence level, and an unknown is stated rather than filled in.

## The three levels

### CONFIRMED
Directly supported by strong, current evidence:

- source code that is actually reachable and current
- a dependency manifest or lockfile
- tests that exercise the behaviour
- current configuration or infrastructure definitions
- CI/CD definitions
- explicit current documentation that the code corroborates
- Git history

Cite where it came from — a path, a command, or a commit.

### INFERRED
Strongly suggested by several pieces of evidence, but never stated outright.
Label it. "INFERRED: the service is deployed to Fly.io (a `fly.toml` exists and
CI runs `flyctl deploy`, but no deployment documentation confirms it)."

One weak signal is not an inference. It is unknown.

### UNKNOWN
Cannot be responsibly determined from available evidence. Say so, and say what
you looked at. "UNKNOWN: no test command found — no test runner in
`pyproject.toml`, no CI test step, no `tests/` directory."

An honest UNKNOWN is more valuable than a plausible guess, because the next
agent will act on whatever is written.

## Resolving contradictions

Investigate rather than average. The usual resolution order:

1. Current source code and configuration
2. Tests
3. Git history (especially migration commits)
4. Documentation

Worked example. README says MongoDB. `requirements.txt` has `psycopg2`. The
source opens Postgres connections. Git history contains "migrate MongoDB to
PostgreSQL". Conclusion: the database is **PostgreSQL (CONFIRMED)**; the
project previously used MongoDB (historical note, worth a DECISIONS entry); the
README is stale and worth flagging.

Never copy stale documentation forward just because it is written down.

## Cite so the claim can be re-checked later

A grade without a citation cannot be re-examined by anyone, including you next
month. Cite a path, a command, or a commit — and prefer the path, because
`context-maintainer review` resolves cited paths and tells you when one of them
has changed since the claim was written. That is the whole mechanism by which a
claim gets a second look; an uncited claim silently opts out of it.

Two things make a claim especially perishable, and both are worth avoiding
unless the exact wording earns its keep:

- **Counts.** "415 tests pass" is true the day it is written and nothing edits
  that sentence when the number changes. Cite what produced the count, or write
  the claim so the figure is not load-bearing.
- **Assertions of absence.** "There is no release workflow" can never be
  re-confirmed by finding something, and nothing announces itself when someone
  adds one. Say what you checked, so the next reader can check the same place.

## Two vocabularies, two different questions

Do not confuse the grade you write with the verdict the CLI reports. They
answer different questions and are not interchangeable:

| | Written by | Question it answers |
| --- | --- | --- |
| CONFIRMED / INFERRED / UNKNOWN | You, in the prose | How strong is the evidence I actually have? |
| CONFIRMED / UNVERIFIED / CONTRADICTED | `doctor --verify` | Could a machine check this against the repository? |

An UNVERIFIED verdict is not a criticism of a CONFIRMED grade: plenty of true
claims rest on evidence no fingerprint can see. A CONTRADICTED verdict is
different — it means the repository actively disagrees, and the honest
resolutions are to correct the claim or to reword it so it is no longer
asserted as current fact. Deleting it to make the check pass is not one of them.

## Secrets

Inventory mechanisms; never read values.

- Fine: "configuration comes from `.env`, with `.env.example` listing
  `DATABASE_URL` and `STRIPE_KEY`."
- Not fine: opening `.env` to see what those values are.
- Never write a discovered credential into a context document, a commit
  message, or a cache file. If you encounter one incidentally, do not record
  it, and tell the user where it is exposed.

Excluded by default from audit passes: `.env` and `.env.*` (except example and
sample files), private keys and certificates, credential and secret stores,
`node_modules` and other dependency directories, virtualenvs, build outputs,
caches, generated binaries, and `.git` object contents.

## Degraded audits

If Repomix is unavailable, or a structural-analysis companion is not
configured, or the audit was interrupted — record that in ARCHITECTURE.md's
"Evidence Level" section, and downgrade affected claims accordingly.

Never describe an audit as complete when it was not. A document that overstates
its own confidence is worse than one that admits a gap, because it removes the
next reader's reason to check.
