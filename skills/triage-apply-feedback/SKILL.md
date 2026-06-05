---
name: triage-apply-feedback
description: >
  Process queued refine feedback for a single Firefox A/V triage draft.
  Re-draft the pending JSON in response to the human's feedback, then
  REQUIRED: extract any generalizable lesson and propose a wiki addition
  inline so future triage runs avoid the same mistake. Triggered from the
  Process queue drain prompt — never invoked manually.
argument-hint: <bug_id> "<feedback text>" [more feedback strings…]
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion]
user-invocable: false
---

# /triage-apply-feedback — Refine a Draft + Capture the Lesson

This skill processes **one bug's** worth of refine feedback queued from
the dashboard. It is invoked by the drain prompt (`Process queue` button)
once per bug that has refine entries. Do not call it yourself outside
that context.

The skill's reason for existing is the **closed-loop evaluation goal**:
each correction the human makes should reliably feed back into the wiki
or the /triage skill so the next session is less likely to make the same
mistake. Without this step, refine feedback is consumed once and lost.

## Inputs

- `bug_id` — integer Firefox bug id
- `feedback_list` — the array of refine entries from the queue for this
  bug (one or more `{feedback, ts}` items). The drain orchestrator passes
  them inline; do not re-read the queue file.

## Workflow — all steps required

### 1. Read context

```bash
cat ~/firefox-triage/pending/bug-<bug_id>.json
```

Read the entire draft. Note the current `comment`, P/S, blocks, NI,
resolution — anything the feedback might touch.

### 2. Re-draft

Apply all feedback items for this bug as a single revision pass:

- The feedback may direct you to change the comment text, adjust
  severity/priority/resolution, add/remove blocks, NI targets, CC, or
  keywords, or reassign the component. Apply whatever each feedback
  warrants.
- Preserve fields the feedback does not mention.
- Write the updated JSON back to the same path.

Keep a short mental note of **what changed** — you will need it for
step 3.

### 3. Lesson extraction — REQUIRED

This is the core purpose of the skill. After re-drafting, examine the
delta between the original draft and the corrected one. Ask yourself:

> Would a future /triage run, faced with a *similar* bug, make the
> same mistake again?

If **yes**, you have identified a generalizable lesson. Examples of
generalizable patterns worth capturing:

- **Direction errors** — bug was drafted as §1a (NI) but should have been
  §1b (root cause clear from artifacts) or §1c (already a known dup /
  out of scope). A wiki rule should help the next triage classify it
  correctly.
- **Analysis errors** — the comment misread an artifact: profile path
  description was wrong, log line was misinterpreted, codec was
  misidentified. A wiki rule should describe the symptom signature so
  future analyses recognise it.
- **Question-direction errors** — the NI asked for data the reporter
  already provided, or asked the wrong question for the symptom. A
  wiki rule should encode the right question pattern.
- **Routing errors** — wrong component reassignment, wrong meta-bug
  blocker. A wiki rule should map symptom → correct destination.

If **no** (one-off correction, taste-level wording change, typo, etc.),
you do not propose a wiki addition. Record `lesson: null` in step 5
with a one-line reason.

### 4. Add the lesson — decide autonomously (no approval prompt)

When a generalizable lesson is identified, **use your best judgment to
decide whether and where to record it — do NOT ask the user to confirm
each one.** The decisions-log (step 5) is the audit trail, and the user
can veto or correct any entry via a later refine.

**Add to the wiki** (via `/firefox-wiki:add`, which records the usage-log)
only when ALL of these hold:
- **Generalizable** — it would help triage a *future, similar* bug, not
  just this one.
- **Verifiable** — backed by a concrete cited source: a Searchfox
  permalink, a spec section, or a bug number. Never add a fact from
  memory or inference alone.
- **Durable** — not a volatile implementation detail the user flagged as
  likely to change (when in doubt, capture the stable spec/architecture
  fact and omit the volatile code specifics).
- **Not already covered** — if a page already covers it, update that
  page instead of creating a duplicate.

**Route to the `/triage` skill instead of the wiki** when the lesson is
about *how to draft or run triage* — comment voice, comment must be
reporter-facing, capture/Next-Steps ordering, verify-before-attributing
discipline, NI/routing conventions. These are process rules; add or adjust
them in `~/.claude/skills/triage/SKILL.md` (then commit/push), not as a
wiki page.

**Do NOT add anything** for: one-off field/wording/taste changes;
uncertain or speculative claims with no solid source (Low confidence and
no citation); or security-bug details (see the wiki content policy).

When an addition is borderline or Low-confidence, still add it if it has a
real source, but tag it `[Low]` and include a one-line "not verified
end-to-end" disclaimer on the page.

Record what you did in step 5: `wiki_outcome` ∈ `"added"` (+ page),
`"skipped"` (+ reason), `"skill-updated"` (+ which rule/file).

### 5. Append a decisions-log entry — REQUIRED

Append a single line to `~/firefox-triage/decisions-log.jsonl` describing
what happened for this bug. Schema:

```json
{
  "event": "apply-feedback",
  "bug_id": 2042320,
  "ts": "2026-05-31T09:15:00Z",
  "feedback": [
    {"text": "the NI is asking for about:support but they already provided it", "ts": "2026-05-30T22:15:23Z"}
  ],
  "redraft_summary": "Switched NI question from about:support to media log; tightened analysis paragraph.",
  "lesson": "When the reporter has already pasted about:support, /triage should not ask for it again — check the inventory_present block first.",
  "wiki_outcome": "added",
  "wiki_page": "triage/check-inventory-before-ni.md"
}
```

If no lesson was identified:

```json
{
  "event": "apply-feedback",
  "bug_id": 2040167,
  "ts": "2026-05-31T09:18:00Z",
  "feedback": [{"text": "shorten the analysis paragraph", "ts": "..."}],
  "redraft_summary": "Tightened analysis from 4 paragraphs to 2.",
  "lesson": null,
  "lesson_skip_reason": "Taste-level wording change, not a triage pattern.",
  "wiki_outcome": "none"
}
```

Append, do not overwrite. The log is append-only and is the source of
truth for evaluating /triage's reliability over time.

## What this skill does NOT do

- It does NOT touch the queue file (`claude-queue.jsonl`). The drain
  orchestrator handles queue truncation after every refine in the
  batch has been processed.
- It does NOT invoke `bugzilla-cli apply` — or any other Bugzilla write or
  read. It only edits the local pending draft (plus the wiki / decisions-log),
  so it is **mode-independent**: it runs identically in `/triage` read-only and
  reply mode and needs no API key. The write happens later in step 4 of the
  drain prompt (`apply`), which is **reply-mode only** — in read-only mode that
  step is skipped (and `bugzilla-cli apply` refuses without a key anyway).
- It does NOT dispatch `/bug-start`. That happens in step 5 of the
  drain prompt for queued bug-start actions.
- It does NOT lookup the wiki at the start. Pre-session wiki lookup is
  the responsibility of /triage itself.

## Failure modes — what to do

- **Pending JSON missing**: the bug may have been applied or skipped
  since the refine was queued. Skip this bug, log
  `{event: "apply-feedback", bug_id, ts, error: "pending JSON missing"}`
  to decisions-log.jsonl, and continue.
- **Feedback contradicts itself**: apply the most recent direction
  (latest `ts`), note the contradiction in `redraft_summary`. Mention
  it briefly in the redraft so the human sees it on next review.
- **Cannot identify a generalizable lesson AND uncertain**: record
  `lesson: null, lesson_skip_reason: "uncertain"`. Better to skip than
  fabricate a pattern.

## Why autonomous (with an audit trail)

The per-page approval gate was removed (2026-06): confirming every wiki
addition was too high-friction. The skill now decides autonomously using
the step-4 criteria, and the **decisions-log is the audit trail** — every
`added` / `skipped` / `skill-updated` outcome is recorded with its reason,
so the user can review and veto or correct any entry via a later refine.

The wiki shapes future triage, so a bad entry makes /triage *worse*. The
step-4 criteria are the guardrail in place of the prompt: require a real
cited source, prefer the skill for process/drafting rules, never add
security-bug details, and tag borderline entries `[Low]`. When genuinely
unsure whether something meets the bar, skip it and note why in the log —
a missing page is cheaper to fix than a wrong one.
