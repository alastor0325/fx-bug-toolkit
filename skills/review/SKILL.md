---
name: review
description: >
  Review a Firefox patch for correctness, architecture, spec compliance, and code quality.
  Generates a structured review document in ~/firefox-patches-review/.
  Triggers on: "review patch", "review revision", "review D<number>", "review this diff",
  "review my changes", "code review", "review the patch".
argument-hint: <revision-id, "local", or "diff">
allowed-tools: [Agent]
---

# /review — review a Firefox patch

Delegate to the `firefox-review` agent (Opus):

```
Agent tool: subagent_type "firefox-review"
Prompt: "Review patch. Source: {argument}."
```

Where `{argument}` is:
- The revision ID passed to this skill (e.g. `D12345`)
- `local` — committed patches on the current branch
- `diff` — uncommitted local changes
- If none provided, ask the user: "Please provide a revision ID (e.g. D12345), say 'local' for committed branch patches, or 'diff' for uncommitted changes."

The agent reads the patch, verifies its purpose against the relevant specs,
reviews architecture and code-level correctness, and writes a structured review
document to `~/firefox-patches-review/`. When it finishes, relay its verdict and
the file path.
