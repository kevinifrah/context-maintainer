# Optional structural-analysis companion

Context Maintainer ships **no** code-intelligence backend of its own. Its
baseline evidence is Repomix, Git, and direct file reading, which is sufficient
for a good audit.

For compiler-grade answers to "what calls what", you can optionally configure
[`isaacphi/mcp-language-server`](https://github.com/isaacphi/mcp-language-server)
(BSD-3-Clause). It wraps real language servers — gopls, pyright,
typescript-language-server, rust-analyzer, clangd — and exposes them as MCP
tools, so resolution comes from the same engines editors use rather than from
text matching.

## Using it during an audit

Check whether these tools are present in your own toolset:

`definition` · `references` · `diagnostics` · `hover` · `rename_symbol`

If they are, use them to **verify** structural claims instead of inferring them:

- `definition` / `references` — confirm what actually calls a symbol before
  describing a flow in ARCHITECTURE.md
- `hover` — confirm real types and signatures at a boundary
- `diagnostics` — surface genuine breakage rather than guessing from reading

A call path you verified this way is CONFIRMED. A call path you inferred from
grep is INFERRED. Do not blur the two.

If the tools are absent, say so in ARCHITECTURE.md's "Evidence Level" section
and keep structural claims at INFERRED unless code you read directly settles
them.

`context-maintainer doctor` reports whether the companion is configured, and
`context-maintainer audit --json` includes it under `mcp_language_server`.
Absence is never a failure.

## Configuration (for the user, not for you to run)

Never install or configure this on the user's behalf. It needs a Go toolchain
plus whichever language servers their project requires — too variable to script
safely. Offer the commands; let them decide.

```bash
go install github.com/isaacphi/mcp-language-server@latest
# plus the language server(s) for the stack, e.g.
go install golang.org/x/tools/gopls@latest
npm install -g pyright
npm install -g typescript typescript-language-server
```

Claude Code — `.mcp.json` in the project, or `~/.claude.json`:

```json
{
  "mcpServers": {
    "language-server": {
      "command": "mcp-language-server",
      "args": ["--workspace", "/path/to/project/", "--lsp", "gopls"]
    }
  }
}
```

Codex:

```bash
codex mcp add language-server -- \
  mcp-language-server --workspace /path/to/project/ --lsp gopls
```

Python and TypeScript variants swap the `--lsp` argument:

```text
--lsp pyright-langserver -- --stdio
--lsp typescript-language-server -- --stdio
```

One running instance binds to exactly one language server and one workspace, so
a polyglot repository needs one entry per language.

## Two honest caveats

1. **Maintenance has slowed.** The last merged upstream commit was 2025-06-03,
   and the last release v0.1.1 (2025-05-16). The repository is not archived and
   still receives community issues and PRs, but it is better described as
   dormant-but-usable than actively maintained. Check its current state before
   depending on it.

2. **A previously specified backend was deliberately rejected.**
   `DeusData/codebase-memory-mcp` was evaluated and excluded on security
   grounds: fabricated-looking popularity (~40k stars in 6 months on a
   573-follower account), README text pre-emptively dismissing a Microsoft
   Defender trojan detection as a false positive, self-scored and
   non-verifiable VirusTotal claims, binary-only distribution, an installer
   that writes into dozens of unrelated AI-agent configs, and content that
   triggered prompt-injection defenses during research. Do not reintroduce it,
   and treat any similarly-shaped "codebase memory" package with the same
   suspicion.
