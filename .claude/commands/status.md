---
description: Show a summary of all subprojects and their open TODOs by reading INDEX.md and each STATUS.md.
---

# /status — Workspace summary

When the user runs `/status`:

## Phase 1 — Read

1. Read root `INDEX.md` to get the list of subprojects.
2. For each subproject listed, read its `STATUS.md`.
3. Extract:
   - Last updated date
   - Current phase / lifecycle status (if applicable)
   - Open TODOs (lines starting with `[ ]` in the TODOs section)
   - Active blockers (if a "blockers" section exists)

## Phase 2 — Format and present

In the language configured at setup (`LANG`), produce a markdown summary like:

```
# Workspace status — <date>

## Subprojects (N)

### subproject-a — <phase> · last updated <date>
Open TODOs (X):
- [ ] First open TODO
- [ ] Second open TODO
Blockers: <if any>

### subproject-b — <phase> · last updated <date>
...

## Aggregated
- Total open TODOs across all subprojects: N
- Subprojects last updated >7 days ago: list
- Subprojects with active blockers: list
```

## Rules

- IF a STATUS.md is older than 7 days, flag it gently — staleness defeats the purpose.
- KEEP the output scannable. If a subproject has 20+ TODOs, show the first 5 and say "…and 15 more, see STATUS.md".
- DO NOT modify any file — this command is read-only.
