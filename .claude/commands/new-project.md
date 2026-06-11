---
description: Create a new subproject with its CLAUDE.md and STATUS.md, and register it in INDEX.md.
---

# /new-project — Add a new subproject

When the user runs `/new-project <name>`:

## Phase 1 — Validate

1. Check that `_templates/subproject-CLAUDE.md.tmpl` and `_templates/subproject-STATUS.md.tmpl` exist. If not, tell the user to run `/setup` first.
2. Read root `CLAUDE.md` to know the configured `SUBPROJECT_DIR` and `LANG`.
3. If `<name>` was not provided in the command, ask: "What's the name of the new subproject?" Use kebab-case.

## Phase 2 — Create

1. Create directory: `<SUBPROJECT_DIR>/<name>/`
2. Copy `_templates/subproject-CLAUDE.md.tmpl` → `<SUBPROJECT_DIR>/<name>/CLAUDE.md`. Replace `{{NAME}}` placeholder with the subproject name.
3. Copy `_templates/subproject-STATUS.md.tmpl` → `<SUBPROJECT_DIR>/<name>/STATUS.md`. Set the date to today.
4. **Pre-fill from interview** (preset-dependent):
   - **Research preset**: ask "What's the hypothesis?" and put it in STATUS.md hypothesis section.
   - **Product preset**: ask "Brief description (one sentence)?" and put it in STATUS.md state section.
   - **Consulting preset**: ask "Client name and engagement scope?" and put it in STATUS.md.
   - **Knowledge preset**: ask "Topic / one-line summary?" and put it in STATUS.md.
   - **Custom**: just ask "Brief description?" and put in STATUS.md state.
5. Add a row to root `INDEX.md`. The table format is already there — preserve column structure.

## Phase 3 — Confirm

Print to the user (in `LANG` configured at setup):

```
✅ Created <SUBPROJECT_DIR>/<name>/
   - CLAUDE.md (conventions)
   - STATUS.md (live state — keep it updated)
   - Added to INDEX.md

Tip: open the new STATUS.md and customize it. The first entry helps the agent
understand what you're trying to do.
```

Then ask: "Want me to open the STATUS.md for you to fill in more detail now?"

## Rules

- DO NOT create a subproject if name conflicts with an existing one — ask the user to rename.
- DO NOT skip the INDEX.md update — that's how the workspace stays browsable.
- USE the language configured during setup for all user-facing text.
