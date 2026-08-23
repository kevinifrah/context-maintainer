# Security policy

## Reporting a vulnerability

Open an issue at
[github.com/kevinifrah/context-maintainer/issues](https://github.com/kevinifrah/context-maintainer/issues)
describing the impact and how to reproduce it.

Please **do not** include real credentials, private repository contents, or a
working exploit payload. A description of the mechanism is enough to act on.

If a report would be unsafe to disclose publicly, say so in the issue without
the details and a private channel will be arranged.

## What is in scope

Context Maintainer reads repositories and writes Markdown. The security surface
worth reporting is therefore:

- **Secret exposure** — any path by which `.env` contents, private keys,
  tokens, or credentials end up in a generated context document, a commit
  message, or the cache. Inventorying that a secret mechanism exists is
  intended; reading or recording values is not.
- **Unintended file destruction** — anything that overwrites or deletes user
  content without a backup, or that clobbers a file with uncommitted changes.
- **Installer escalation** — the installer replacing content it does not own
  without `--force`, or escaping the two documented target paths.
- **Command injection** — repository content (a filename, branch, or commit
  message) influencing the arguments of a subprocess call.
- **Prompt injection with real consequence** — repository content that causes
  the skill to take a destructive action or to exfiltrate data. Content that
  merely makes a document inaccurate is a correctness bug, not a
  vulnerability — file it as an issue.

## Untrustworthy dependencies are in scope too

This project depends on external tools, and their trustworthiness is a security
property of this project.

If you find that a tool Context Maintainer recommends has become
untrustworthy — abandoned and hijacked, compromised release artifacts,
fabricated legitimacy signals — that is a valid and welcome report.

There is precedent. During development, the originally specified
code-intelligence backend (`DeusData/codebase-memory-mcp`) was **evaluated and
rejected** after showing: roughly 40,000 GitHub stars accumulated in six months
on an account with 573 followers; README text pre-emptively dismissing a
Microsoft Defender trojan detection as a false positive; self-scored,
non-verifiable VirusTotal tables; binary-only distribution with no
source-to-binary verification; an installer writing into 43 unrelated AI-agent
configurations; and repository content that triggered prompt-injection defenses
during research. The rationale is recorded in the README so the decision is not
quietly reversed later.

Apply the same scrutiny to anything this project suggests, including its
optional tools.

## Design commitments

These are enforced by tests, not just intentions:

- **Secretlint stays enabled.** `--no-security-check` is never passed to
  Repomix. A test asserts it.
- **Secret-bearing paths are excluded** from audit passes: `.env` and `.env.*`
  (except example and sample files), private keys and certificates,
  `**/secrets/**`, `**/credentials/**`, `.aws/**`, `.ssh/**`.
- **No third-party software is installed on your behalf**, and no remote
  installer is ever executed. Missing optional dependencies are reported with
  the command you would run yourself.
- **No network calls and no telemetry.** The CLI has zero runtime
  dependencies.
- **Existing files are never silently replaced.** `init` preserves an existing
  `AGENTS.md` or `CLAUDE.md`; `rebuild` backs up first; a tracked file with
  uncommitted changes is not overwritten even with `--force`.
- **The installer refuses to touch what it does not own** without `--force`,
  and backs up before replacing.

## Supported versions

v0.1.x is the current line and the only one receiving fixes. This is an early
release — pin a tag if you need stability.
