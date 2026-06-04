---
name: update-investigation
description: >
  Update an existing Firefox bug investigation file with new findings, corrected root cause,
  revised proposed solution, or patch arrangement changes. Use when investigation.md needs
  targeted edits — inside or outside of bug-start.
  Triggers on: "update investigation", "update the investigation file", "add to investigation",
  "document this in the investigation", "update bug XXXXXX investigation",
  "correct the investigation", "write that down".
argument-hint: <bug-id>
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion]
---

# Update Investigation File

Make targeted edits to an existing Firefox bug investigation file.

## Rules

1. **Never create a new file** — only edit existing ones. If the file doesn't exist, tell the user and suggest `/bug-start {bug_id}`.
2. **Every new claim must be verified or labeled `[Assumption]`** — same standard as the original investigation. Do not write statements about code behavior without reading the code or labeling it.
3. **All new code references need searchfox links** — `[file:line](https://searchfox.org/mozilla-central/source/path#line)`.
4. **Targeted edits only** — do not rewrite sections that weren't asked to change.
5. **Show what changed** — after editing, report which sections changed and how (old → new).

## Step 1: Find the File

```bash
ls ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md
```

If it doesn't exist, stop: "No investigation file found for bug {bug_id}. Run `/bug-start {bug_id}` to create one."

If no bug ID was given, ask: "Which bug investigation should I update? (provide bug number)"

## Step 2: Read the Current State

Read the full file before making any changes.

## Step 3: Identify What to Update

Map the user's request to sections:

| User intent | Section to update |
|---|---|
| Root cause correction | Problem Analysis → Root Cause |
| New approach / fix strategy | Implementation Plan → Patch Arrangement + Patch Details |
| New code reference | Problem Analysis → Code Analysis → Key Files |
| Patch arrangement change | Implementation Plan → Patch Arrangement table + Patch Details |
| Test strategy change | Implementation Plan → Test Strategy + relevant Patch Details |
| Add gotcha / edge case | Relevant Patch Details section |

If the request is ambiguous, ask: "Which part needs updating — root cause, proposed solution, patch arrangement, test plan, or something else?"

## Step 4: Verify Before Writing

Before editing:
- [ ] All code behavior claims are backed by code you have read, or labeled `[Assumption]`
- [ ] All new code references have searchfox links
- [ ] If Patch Arrangement changes, Patch Details sections are updated to match
- [ ] If Root Cause changes, Summary elevator pitch is updated too

## Step 5: Apply the Edit

Use Edit tool for targeted changes. Use Write only if the structure has fundamentally changed and a full rewrite is clearly cleaner.

## Step 6: Report Changes

After editing, summarize:
- Which sections changed
- Key difference (old → new), one line per section
- Any sections that should be updated next but weren't in scope
