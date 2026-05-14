# Architecture

The workspace pattern in 4 layers.

## The 4-layer pattern

```
┌─────────────────────────────────────────────────────────────┐
│ Root CLAUDE.md (Anthropic convention, auto-loaded)          │
│ Global workspace philosophy + rules + conventions.          │
├─────────────────────────────────────────────────────────────┤
│ Per-subproject CLAUDE.md (auto-loaded when in that dir)     │
│ Stable conventions for THIS subproject. Stack, patterns.    │
│ Never state, never TODOs.                                   │
├─────────────────────────────────────────────────────────────┤
│ Per-subproject STATUS.md (manual read)                      │
│ Live operational state. TODOs, decisions, blockers, dates.  │
│ Updated in same commits as code changes → always in sync.   │
├─────────────────────────────────────────────────────────────┤
│ Root INDEX.md (manual read)                                 │
│ One-line summary per subproject. Birds-eye view.            │
└─────────────────────────────────────────────────────────────┘
```

## Why these specific files

**`CLAUDE.md`** — Anthropic's official convention. Claude Code auto-loads any file named exactly `CLAUDE.md` based on the directory you're working in. We use it for **stable** stuff (philosophy, conventions) — things that don't change every week.

**`STATUS.md`** — our own convention. The agent reads it manually when you ask "where are we on X?" or when picking up work after a break. Holds **mutable** stuff: current TODOs, decisions you've taken with their *why*, blockers waiting on you.

**`INDEX.md`** — a one-page overview. Useful for you (the human) and for the agent when you say "give me a summary of all my projects."

## Why split CLAUDE.md and STATUS.md

If you mix conventions and state in one file, the file rots fast. Conventions are stable, state changes daily. Mixing them means you either:
- Update the conventions section by accident, OR
- Leave the state section stale because it's hidden among conventions.

Splitting them solves both problems and matches the auto-load semantics: stable goes in `CLAUDE.md`, mutable goes in `STATUS.md`.

## Why "decisions with the *why*"

A TODO list is forward-looking. A decisions log is backward-looking. The most valuable thing in a long-running project is **the reasoning behind past choices** — not just the choices themselves. When the agent asks "why did we go with X instead of Y?" the answer should already be in `STATUS.md`.

Format we recommend:

```markdown
## Key decisions

- **Use Lemon Squeezy instead of Stripe.** Reason: no LLC needed, MoR handles VAT.
  How to apply: keep LS until revenue justifies an LLC.
```

## The skills/commands layer

On top of the file pattern, the workspace can have:

- **`.claude/commands/<name>.md`** — slash commands. Each is a markdown file describing what Claude should do when invoked. Examples: `/setup`, `/new-project`, `/status`.

These are pure Claude Code conventions. They're optional but powerful — they let you encode workflows your future self can re-run.

## Memory (optional, separate from this repo)

Claude Code has a per-project memory folder at `~/.claude/projects/<sanitized-path>/memory/`. Useful for things you don't want to commit but want Claude to remember across sessions (personal preferences, the "why" behind a decision that doesn't fit in code).

This template doesn't manage that — it's per-user and outside git.

## Anti-patterns

- **Don't put TODOs in `CLAUDE.md`** — they go stale and the file becomes noise.
- **Don't put architecture info in `STATUS.md`** — it doesn't belong there and complicates updates.
- **Don't create more than one INDEX file** — one source of truth.
- **Don't skip `STATUS.md` updates** — the value of the system collapses if state is stale. Treat it like an extension of your commit message.
