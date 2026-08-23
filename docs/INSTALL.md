# Installation

Pick the section for the agent you use. If you use both, do both — they're
independent and share the same underlying files.

There are two ways to install, and the right one depends on whether you want to
hack on Context Maintainer or just use it.

| | Plugin install | Checkout install |
|---|---|---|
| Steps | 2 commands, inside the agent | `git clone` + 1 command |
| Needs `pip` | No | Optional (recommended) |
| Needs the repo kept on disk | No | Yes — symlinks point at it |
| Updates | `/plugin update` or `codex plugin upgrade` | `git pull` |
| Best for | Just using it | Contributing, or wanting the `context-maintainer` CLI in your shell |

Both give you the same skill and the same behaviour. The plugin install is
self-contained: the Python CLI is bundled inside the plugin, so nothing else is
required.

---

## Claude Code

### Option A — plugin install (recommended)

Inside Claude Code:

```
/plugin marketplace add <owner>/<repo>
/plugin install context-maintainer@context-maintainer
```

The first command registers this repository as a plugin marketplace; the second
installs the plugin from it. Claude Code will show an install-scope prompt —
choose user-level to have it available in every project.

Then restart your session and check it's there:

```
/plugin
```

> **If `owner/repo` shorthand fails**, Claude Code clones over SSH by default.
> Either set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` in your environment, or pass a
> full URL: `/plugin marketplace add https://github.com/<owner>/<repo>.git`

### Option B — checkout install

```bash
git clone <repository-url> context-maintainer
cd context-maintainer
./scripts/install.sh --claude
```

That checks your dependencies, installs the `context-maintainer` CLI, and
symlinks the skill into `~/.claude/skills/context-maintainer`.

### Invoking it

Start a **new** Claude Code session (skills are discovered at startup), then:

```
/context-maintainer:context-maintainer init
```

Bare `/context-maintainer init` also works, unless another command already
claims that name. Claude may also invoke the skill on its own when you ask
something it matches, e.g. *"set up project context for this repo"*.

> **Why the doubled name?** The plugin is named `context-maintainer` and so is
> the skill inside it, so the fully-qualified command is
> `/context-maintainer:context-maintainer`. If you only ever want the short
> form and don't need plugin packaging, use the checkout install and delete
> `skill/context-maintainer/.claude-plugin/plugin.json` before running the
> installer — it then loads as a plain skill with an unconditional
> `/context-maintainer`.

---

## Codex

### Option A — plugin install

```bash
codex plugin marketplace add <owner>/<repo> --ref main
codex plugin add context-maintainer@context-maintainer
codex plugin list
```

### Option B — checkout install

```bash
git clone <repository-url> context-maintainer
cd context-maintainer
./scripts/install.sh --codex
```

That symlinks the skill into `~/.agents/skills/context-maintainer`, which Codex
scans automatically.

### Invoking it

Restart Codex, then:

```
$context-maintainer init
```

`/skills` lists everything Codex can see, if you want to confirm it registered.

---

## Both agents at once

```bash
git clone <repository-url> context-maintainer
cd context-maintainer
./scripts/install.sh
```

One canonical skill directory, symlinked into both hosts — so a `git pull`
updates both at once and the two can never drift apart.

---

## Checking dependencies without installing anything

```bash
./scripts/install.sh --check      # report what's present, change nothing
./scripts/install.sh --dry-run    # report what would change, change nothing
```

Example output:

```
Context Maintainer — dependency check

  [ok]   Python 3.12.1 (python3)
  [ok]   git version 2.50.1
  [warn] Repomix not found — optional. Audits run in degraded mode.
         Install with:  npm install -g repomix     (needs Node 22+)
  [warn] mcp-language-server not found — optional. Structural claims stay INFERRED.
         Install with:  go install github.com/isaacphi/mcp-language-server@latest
```

Only Python 3.9+ and Git are required. Nothing is ever installed on your behalf,
and no remote installer is ever executed.

---

## Optional dependencies

Neither is needed to use Context Maintainer. Both make audits better, and their
absence is always reported rather than hidden.

**Repomix** — broad repository evidence for audits. Without it, audits fall back
to Git and direct file reading, and clearly report degraded mode.

```bash
npm install -g repomix     # needs Node 22+
```

**mcp-language-server** — compiler-grade "what calls what", which upgrades
architecture claims from INFERRED to CONFIRMED.

```bash
go install github.com/isaacphi/mcp-language-server@latest
go install golang.org/x/tools/gopls@latest        # or pyright, etc.
```

Then register it with your agent — see the
[structural analysis section](../README.md#structural-code-analysis) of the
README for the exact config.

---

## Verifying the install

```bash
context-maintainer --version
context-maintainer skill status
```

`skill status` shows both target paths and whether each is correctly linked:

```
Canonical skill: /path/to/checkout/skill/context-maintainer

- claude  correct_symlink    /Users/you/.claude/skills/context-maintainer
- codex   correct_symlink    /Users/you/.agents/skills/context-maintainer
```

If you used the plugin install and skipped `pip`, the `context-maintainer`
command won't be on your PATH — that's expected. The skill invokes the bundled
CLI itself.

---

## Updating

**Plugin install:** `/plugin update context-maintainer` (Claude Code) or
`codex plugin marketplace upgrade` then `codex plugin add …` (Codex).

**Checkout install:** `git pull`. Symlinks mean there's nothing else to do —
both agents immediately see the new version. Re-run `./scripts/install.sh` only
if you moved the checkout.

---

## Uninstalling

```bash
python3 installer/uninstall.py --dry-run     # preview
python3 installer/uninstall.py               # both hosts
python3 installer/uninstall.py --claude      # one host only
pip uninstall context-maintainer             # if you pip-installed
```

For a plugin install, use `/plugin uninstall` or `codex plugin remove
context-maintainer`.

Uninstalling only removes symlinks that point at your checkout. Anything else
requires `--force`, and gets backed up first.

Your `docs/context/` files are ordinary Markdown in your own repositories. They
keep working — for humans and for any other agent — whether Context Maintainer
is installed or not.

---

## Troubleshooting

**The command isn't recognized.** Start a new session; skills load at startup.
Then `context-maintainer skill status` (or `/plugin` / `codex plugin list`).

**`context-maintainer: command not found` in your shell.** You installed the
plugin without pip. That's fine — the skill still works. For shell access, run
`pip install -e .` from a checkout.

**`doctor` says a symlink points somewhere else.** You moved the checkout.
Re-run `./scripts/install.sh` from its new location, adding `--force` if a real
directory now occupies the path (it gets backed up first).

**Installer reports a conflict.** Something unrelated already occupies
`~/.claude/skills/context-maintainer` or `~/.agents/skills/context-maintainer`.
Inspect it, then re-run with `--force` to move it aside into a timestamped
`.cm-backup-…` directory.

**Windows.** The checkout install needs symlinks, which need Developer Mode or
an elevated shell. Use WSL, or the plugin install, which copies rather than
links.
