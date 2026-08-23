# Context Maintainer

Durable, evidence-based project context for Claude Code and Codex — no proprietary memory database, no vector store, no hosted infrastructure.

> **Status: early development.** This README is a placeholder scaffold; full documentation (installation, commands, security model, FAQ) lands in the final implementation phase.

## What this is

Context Maintainer keeps a small, inspectable set of Markdown files (`AGENTS.md`, `CLAUDE.md`, `docs/context/*.md`) up to date so that either Claude Code or Codex can rebuild an accurate mental model of a project — across sessions, context compaction, and tool switches — without a separate memory service.

## License

MIT — see [LICENSE](LICENSE).
