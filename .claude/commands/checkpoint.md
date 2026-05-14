---
description: Force-update the current subproject's STATUS.md based on the current session's work.
---

# /checkpoint — Save current state

When the user runs `/checkpoint`, you (Claude) update the relevant subproject's `STATUS.md` based on what happened in this session. The user shouldn't have to spell out what to write — you should know from context.

## Step 1 — Identify the active subproject

- If the user has been working in a specific subproject directory in this conversation: that's the one.
- If multiple subprojects were touched: ask the user which one to checkpoint, or update each in turn.
- If no clear subproject context exists: ask "Which subproject should I checkpoint?"

## Step 2 — Read current STATUS.md

Open the active subproject's `STATUS.md` and remember its current contents.

## Step 3 — Reconstruct what happened in this session

From the conversation history and any file changes, identify:
- What was completed (mark `[x]` on relevant TODOs).
- What new TODOs surfaced (add to the TODOs section).
- What decisions were made (add to "Key decisions" section with the **why**).
- What new blockers appeared (add to "Blockers" section).
- Any phase/lifecycle change (update the phase line).
- Always update the `Last updated:` date to today.

## Step 4 — Write the updated STATUS.md

- DO preserve sections the user customized.
- DO NOT add noise, redundancy, or trivial entries.
- DO be specific in entries (write `Decided X over Y because Z` not `we made some decisions`).
- DO summarize multiple small things into one entry when appropriate.

## Step 5 — Confirm and offer to commit

Tell the user (in the workspace's configured language):

```
✅ Checkpointed <subproject>/STATUS.md
   - <N> TODOs marked complete
   - <N> new TODOs added
   - <N> decisions logged
   - <other notable changes>

Want me to also commit this with the related code changes?
```

If the user says yes, stage `STATUS.md` plus the relevant code files and create a commit with a descriptive message.

## Rules

- DO NOT touch any other file unless the user explicitly asked.
- DO NOT update STATUS.md if nothing meaningful happened — tell the user "nothing to checkpoint" instead.
- USE the workspace's configured language for all user-facing text.
