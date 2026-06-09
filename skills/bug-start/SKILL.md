---
name: bug-start
description: Quick start workflow for investigating or implementing a Firefox bug
argument-hint: <bug-id>
allowed-tools: [Read, Write, Edit, Grep, Glob, Bash, TaskCreate, AskUserQuestion]
---

# Bug Start Workflow

**🔗 MANDATORY: Every reference to a source file, function, or line number in the investigation file MUST be a clickable searchfox hyperlink:**
```
[`path/to/file.cpp:NNN`](https://searchfox.org/mozilla-central/source/path/to/file.cpp#NNN)
```
A file reference without a link is incomplete. Do not write any code reference without the link. This applies to every section: Root Cause, Code Analysis, Call Chain, Patch Details — everywhere.

You are helping start work on a Firefox bug. Follow these steps systematically:

📁 **Storage location**: investigation files live in the **investigation
directory** — `$FX_BUG_INVESTIGATION_DIR` if set, otherwise the default
`~/.fx-bug-toolkit/bug-investigation/`. Shell snippets below expand it safely as
`${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}` so the
path is never empty. The directory is created in step 5 if it doesn't exist.

⚠️ **CRITICAL REQUIREMENT**: After completing investigation (steps 1-4), you MUST create `${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md` using the Write tool. DO NOT skip this step. DO NOT just discuss findings without creating the file.

## Gotchas

1. **Always create the investigation file** — the #1 failure mode. After steps 2-4, use the Write tool to create `${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md`. Do not just discuss findings.
2. **All code references must be searchfox hyperlinks** — every mention of a file, function, or line number must use the format `[file:line](searchfox URL)`. Plain text references (e.g. "DecodedStream.cpp:809") are not acceptable. Use `searchfox-cli` to find exact line numbers before writing.
3. **Classify intermittent vs. consistent first** — analyzing code before knowing failure rate wastes time. Check the bug title/comments for "intermittent", "flaky", or failure percentages before diving into code.
4. **Label every unverified claim `[Assumption]`** — do not state hypotheses as facts. Read the code before making any claim about code behavior.
5. **Evaluate proposed fixes independently — never adopt them verbatim** — if the bug has a proposed patch or fix in comments (from a reviewer, contributor, or another engineer), read the actual code and verify every step of that fix yourself. A proposed fix may have subtle errors (wrong argument type, missed edge case, incorrect invariant). Adopt the structural approach only after confirming each detail against the code. Never write "fix from comment N" as the authoritative solution.
6. **Do not update `investigation.md` during exploratory discussion** — it is a stable checkpoint. Only update when the user explicitly signals ("update investigation.md", "document this").
7. **Private bug history log**: when logging to `history.log`, ONLY write the bug number for private bugs. Never log any title, component, description, or root cause details.
8. **Security bugs MUST include a Security Rating section** — if the bug has any `sec-*` keyword (sec-high, sec-moderate, sec-low, sec-critical, etc.) or is in a security group, you MUST add a `## Security Rating` section. See template below.

## Invocation Modes

This skill has two modes. The default is **deep mode**. `/triage` dispatches
parallel subagents in **triage mode** so each one stays fast.

### Deep mode (default)
Invocation: `/bug-start <bug-id>` (no flags) or `/bug-start <bug-id> --force`.

Produces the full investigation document — every section in the template
at section 6, including Implementation Plan, Patch Arrangement, Mechanism
Replacement, Test Strategy, and exhaustive code citations. Spend up to
15–20 minutes per bug. This is what you run when you're about to start
writing patches.

### Triage mode (`--triage-mode`)
Invocation: `/bug-start <bug-id> --triage-mode`.

Used exclusively by `/triage`'s parallel dispatch. Produces a shorter
investigation focused on root cause + affected area + a proposed-solution
sketch — **no** patch arrangement, **no** test plan, **no** code
archaeology beyond signal-level. Spend up to 5 minutes per bug.

Triage mode writes a different template (see section 6.5 below). The YAML
frontmatter is mandatory in both modes; in triage mode it gains a
`depth: triage` field so the dashboard can render a "shallow investigation
— re-run for full" affordance.

The user (or `/triage`) re-runs `/bug-start <bug-id>` (deep mode) later
when ready to actually implement the fix; that overwrites the triage-mode
file with a full investigation.

## 1. Check for Existing Investigation

**FIRST, check if an investigation file already exists:**
```bash
ls -la ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md 2>/dev/null
```

### Skip-if-current rule (non-interactive)

When called from `/triage` (parallel mode) there's no human in the loop, so
this skill MUST be non-interactive. The rule is:

| File state | Bug `last_change_time` vs file `investigated_at` | Action |
|---|---|---|
| File missing | — | Run full investigation (proceed to step 2) |
| File current | `last_change_time <= investigated_at + 1h` | **Skip silently**, exit 0 — do NOT reinvestigate, do NOT prompt |
| File stale | `last_change_time > investigated_at + 1h` | Re-run and overwrite |

The 1-hour grace window avoids re-running while the bug is being actively
edited during triage.

**`--force` flag override**: if the user (manual invocation only) appends
`--force` to the invocation, ignore skip-if-current and rerun
unconditionally. `/triage`'s parallel dispatch never sets `--force`.

If the YAML frontmatter is missing (pre-schema file) treat the file as
stale and re-run — that's how we upgrade old investigations.

**If investigation does NOT exist** (or is stale / forced):
- ⚠️ You MUST create it after completing investigation research (step 6)
- Continue with step 2 to gather information
- **DO NOT forget to create the file in step 6** — this is a BLOCKING requirement

## 2. Fetch Bug Details

First, try the MCP tool:
```
mcp__moz__get_bugzilla_bug(bug_id: {bug_id})
```

**Determine the `Public` attribute from the MCP result:**
- If the MCP tool returns any content (even partial) → **Public: Yes**
- If the MCP tool returns "Bug not found" or an authorization error → **Public: No**

**If that fails** (e.g. security bug — "Bug not found" or authorization error), use `bmo-to-md` instead, which reads `$BMO_API_KEY` from the environment and can access security groups:
```bash
bmo-to-md {bug_id}
```

Extract and summarize:
- Bug title and description
- Component (verify it's Audio/Video related)
- Steps to reproduce (STR)
- Expected vs actual behavior
- Recent comments and discussion
- Related bugs or duplicates
- Assigned status

### Check Duplicate Bugs

If the bug lists any duplicates (bugs marked as duplicates of this one, or this bug is a duplicate of another), **fetch each of them** using the same MCP/bmo-to-md approach:

```
mcp__moz__get_bugzilla_bug(bug_id: {duplicate_id})
# or: bmo-to-md {duplicate_id}
```

Duplicates often contain:
- Additional STR or reproduction scripts not present in the primary bug
- Independent stack traces that confirm or refine the root cause
- Attached testcases (look for `testcase` keyword on duplicates)
- Commenter analysis that narrows the failure condition
- Different affected versions or platforms that constrain the hypothesis

Merge all findings from duplicates into the investigation. If a duplicate adds a meaningfully different perspective (e.g. a cleaner repro, a different crash address, or a different call stack), note it explicitly under **Related Context**.

### Fetch Profiler Profiles (if present)

Scan all bug comments for profiler profile URLs:
- `https://share.firefox.dev/...` — Firefox Profiler share links
- `https://profiler.firefox.com/public/...` — direct public profile links

**Do NOT use WebFetch on these URLs** — they are JavaScript SPAs; WebFetch returns only the CSS shell.

**Do NOT run `profiler-cli` directly** — invoke `/analyze-profile <url>` instead. That skill
runs the full standard query set, checks ALL media threads, pattern-matches against known
signatures, and produces a structured findings report.

Paste the full findings report into the investigation file under **Code Analysis → Profile Analysis**.

If the profile URL is inaccessible or the skill fails, note it explicitly and continue.

### Failure Pattern — Read This Before Any Analysis

**⚠️ CRITICAL: Before forming any hypothesis, determine whether the failure is consistent or intermittent.**

Look for keywords in the bug title or comments: "intermittent", "frequent", "flaky", "single tracking bug", "oranges", failure rate percentages.

| Pattern | What it means | How to approach |
|---------|--------------|-----------------|
| **Always fails** | Feature is broken — the code is wrong or missing | Look for the code path that should handle the case |
| **Intermittent / mostly passes** | A race, resource limit, or missing error-handling path | Do NOT assume the feature is broken. Ask: what happens on the rare occasions it fails? |

#### Step 1: Check Treeherder for failure distribution

For intermittent failures, fetch the Treeherder API to see which platforms/test suites are affected. Use the last 7 days relative to today:

```
https://treeherder.mozilla.org/api/failuresbybug/?startday=YYYY-MM-DD&endday=YYYY-MM-DD&tree=all&bug={bug_id}
```

Use `WebFetch` with this URL (substitute real dates). The response tells you:
- **Which platforms** (e.g. Windows 11 only → OS-specific; Linux+Mac → cross-platform)
- **Which test suite** (e.g. `mochitest-media-wmfme` → Windows Media Foundation Engine; `mochitest-media` → general media pipeline)
- **Build types** (debug/asan/opt)
- **Failure count and trees** (autoland, mozilla-central, try)

The test suite name is often the fastest clue to the root cause area:
- `mochitest-media-wmfme` → Windows Media Foundation Engine (`ExternalEngineStateMachine`, `MFMediaEngine*`)
- `mochitest-media` → general media pipeline (decoders, `MediaDecoder`, `HTMLMediaElement`)
- `mochitest-browser-chrome` → browser chrome / frontend

Document the platform + suite in the investigation file's Problem Description.

#### Step 2: Check whether the existing logs are sufficient

Before diving into code, ask: **do the current failure logs tell you what you need to know?**

For media bugs, the logs often show *that* something failed (error code, HRESULT) but not *which* input triggered it. Common gaps:

- Video URL / filename — passed via IPC to a utility process, not logged at default verbosity
- Which of N concurrent operations failed — when a test runs multiple items in parallel, the log shows the decoder address but not what it was decoding
- Whether the same item always fails or it varies per run

**If the logs are insufficient, improve the test first** before implementing a fix. Add per-item event listeners (`onerror`, `onplaying`) and per-item `ok()` / `info()` calls. The improved test will produce the evidence you need in the next CI run. This is cheaper than guessing at a fix.

#### Step 3: Reason about intermittency

With the platform/suite confirmed and log sufficiency assessed, think in this order:

1. **Test robustness**: Does the test properly handle all error paths? For example, `Promise.all` will hang forever if any promise neither resolves nor rejects. If the test expects success but an error path doesn't reject its promise, the test will time out rather than fail cleanly.

2. **Error propagation gaps**: Does the media pipeline properly reject/resolve all promises on error? A missing `RejectPromises` call can turn a decode error into a silent hang.

3. **Concurrent vs sequential**: Does the test run multiple operations simultaneously (e.g. 4 videos via `Promise.all`)? If only one fails per run, consider **resource contention**: a hardware decoder may have a limited number of concurrent sessions. Test by running items sequentially — if the failure disappears, contention is confirmed.

4. **Platform-specific conditions**: Does the failure only appear on specific hardware, OS version, or driver?

**Never assume** that because a test occasionally fails, the underlying feature is entirely broken. If the test passes 95% of the time, the feature works — something rare is causing the failure, and the fix may be in error handling, not in the feature itself.

#### Step 4: Compare multiple failure instances

Fetch logs from at least 2 different task IDs before forming a root cause hypothesis. Compare:

- Is the same MDSM thread number used? (Note: `MediaDecoderStateMachine #N` is a **thread name**, reused across many decoders — it does not identify a unique decoder. The decoder is identified by `Decoder=<address>`, which changes every run.)
- Does the error fire at a consistent delay after test start across runs? Similar timing → same trigger; variable timing → race
- Is the CDM/utility process in a bad state before the test starts? Look for error codes from the *previous* test's engine in the seconds before `TEST-START`

Document discrepancies between runs — they constrain the hypothesis space.

## 3. Find Relevant Code

**Before any search, state the violated invariant.**

Answer: "The condition that should always be true but wasn't is ___."

Treat this as a falsifiable hypothesis — state it explicitly and revise it if investigation contradicts it. For a spec compliance bug or missing feature, frame it as: "The invariant that *should* exist but doesn't is ___."

### Check the wiki BEFORE reading code

The Firefox Knowledge Wiki (`~/firefox-wiki/`, accessed via the
`/firefox-wiki:lookup` skill) often already contains the answer to a
component's behavior, a known quirk, or a root cause that other
investigations have nailed down. Searching it first can save significant
code-archaeology time.

**Wiki presence gate (REQUIRED when installed).** First check whether the
wiki is set up:
```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo WIKI_INSTALLED
```
- If it prints `WIKI_INSTALLED`: you **MUST** run the lookups below before
  searching code. This is not optional — consulting existing knowledge is
  mandatory whenever the wiki exists.
- If it prints nothing: the wiki is not installed. Skip this entire
  section silently and proceed straight to the code-search steps below.
  Do **not** treat the absence as an error, and do **not** mention it.

When the wiki is installed, run lookups for:
- The component name (e.g. `/firefox-wiki:lookup MediaDecoderStateMachine`)
- The symptom pattern (e.g. `/firefox-wiki:lookup HEVC playback failure`)
- The error code (e.g. `/firefox-wiki:lookup NS_ERROR_DOM_MEDIA_FATAL_ERR`)

If the wiki has the root cause already verified, **cite the wiki page** in
your investigation and skip the corresponding code archaeology. Otherwise
continue with the searches below — and remember to write findings back
to the wiki at the end (see section 6b).

Then ask in order:
1. Where is this invariant **assumed**? (call sites that depend on it being true)
2. Where is it **enforced**? (the place responsible for guaranteeing it)
3. Is every path between enforcement and assumption covered?

Each answer either closes the investigation or opens the next question. Stop when you can explain *why* the invariant failed — not just *where* it manifested. That distinction separates a fix from a workaround.

---

For **architecture or flow questions** (how does X work, what owns Y, how does A connect to B), delegate to the `gecko-navigator` agent with a focused question rather than running raw searches yourself.

For **direct symbol or file lookups** (where is class X defined, find files mentioning keyword Y), use searchfox-cli:
```bash
searchfox-cli --id <keyword> --cpp -l 50
searchfox-cli --define <ClassName>
searchfox-cli -q blob --path dom/media <search-term>
```

Identify 3-5 most relevant files to investigate.

## 4. Check Recent History

For identified files, check recent changes:
```bash
jj log -r 'file(path/to/file)' -l 10
```

Look for:
- Recent related fixes
- Patterns in how similar issues were resolved
- Relevant authors who might have context

---

⚠️ **CHECKPOINT: You have completed research (steps 2-4). Before documenting, complete step 5 (claim verification). Then create the investigation file in step 6.**

---

## 5. Verify Every Claim Before Writing

**⚠️ CRITICAL: Do not write any claim into the investigation file that you cannot back up with direct evidence. Unverified assumptions presented as facts erode trust in the investigation and can misdirect the fix.**

### The two-tier rule

Every statement in the investigation must be classified as one of:

| Tier | Label | Meaning | Requirement |
|------|-------|---------|-------------|
| **Verified** | *(no label needed)* | Confirmed by reading code, logs, or data | Must cite the file:line or log entry that proves it |
| **Assumption** | `[Assumption]` | Plausible hypothesis not yet confirmed | Must be labeled clearly and state what evidence would confirm or refute it |

### Before writing each claim, ask yourself:

1. **Code behaviour claims** — "Function X does Y": Did you read that code? If not, read it now or label it `[Assumption]`.
2. **Causation claims** — "X causes Y": Can you trace the exact call path? If yes, cite the line. If you're inferring, label it `[Assumption]`.
3. **Intermittency / environment claims** — "Fails on some drivers / machines": Do you have log evidence or hardware data? If not, label it `[Assumption: needs log analysis or hardware verification]`.
4. **"Always" / "never" / "only"**: These are strong claims. Read the code to confirm before using them.

### Mandatory verification steps before writing Root Cause

- [ ] Read every function in the call path you describe — do not describe code you haven't read
- [ ] For each error code in the failure log (HRESULT, nsresult), confirm what generates it by tracing to the source
- [ ] If you claim "X never Y" (e.g., "never rejects the promise"), read the function and confirm there is no branch that does Y
- [ ] For intermittency: distinguish between "we know the trigger" (cite evidence) and "plausible explanation" (label assumption)
- [ ] **If a proposed fix exists in bug comments**: verify each step independently. Read the actual API signatures and implementation — not just the proposal — and confirm argument types, field mutability, and edge cases. A proposed fix may be structurally correct but wrong in details (e.g., passing an `AudioDeviceInfo*` where a `CubebUtils::AudioDeviceID` is required, or missing a `RemoveAudioOutput` before `AddAudioOutput`).

### Example

❌ Bad (unverified claim stated as fact):
> The hardware AV1 decoder fails for 4:4:4 chroma because Windows DXVA does not require support for that profile.

✅ Good (verified):
> [`NotifyErrorInternal`](link#1284) takes the `else` branch when `state == RunningEngine`, confirmed by reading lines 1284-1298. No fallback is triggered.

✅ Good (assumption labeled):
> [Assumption] The decode failure may be caused by the hardware AV1 decoder not supporting 4:4:4 chroma subsampling on some CI machines. This has not been confirmed from logs — individual failure logs would be needed to identify which video file triggers the error.

---

## 6. Document Investigation

**🚨 CRITICAL - BLOCKING REQUIREMENT 🚨**

**You MUST create the investigation file using the Write tool RIGHT NOW. Do not proceed to section 7 without creating this file first.**

### File Creation Steps

1. **Resolve + announce the investigation directory, then ensure it exists.**
   Print which directory is being used **and whether it came from
   `FX_BUG_INVESTIGATION_DIR` or the default** — so a misconfigured/unpropagated
   env var (e.g. a Windows User var the shell can't see) shows up as a visible
   "using default" line instead of silently splitting files across two folders:
   ```bash
   INVDIR="${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}"
   if [ -n "${FX_BUG_INVESTIGATION_DIR:-}" ]; then
     echo "Investigation dir: $INVDIR (from \$FX_BUG_INVESTIGATION_DIR)"
   else
     echo "Investigation dir: $INVDIR (default — \$FX_BUG_INVESTIGATION_DIR not set in this shell; see /init if you expected a custom dir)"
   fi
   mkdir -p "$INVDIR"
   ```
2. **Write the "investigating" lock file** so the triage dashboard can show
   an `investigating` status pill while you're still working:
   ```bash
   touch ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigating.lock
   ```
3. **Use Write tool to create**: `${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md`
4. **Verify file was created** with Read tool
5. **Ensure all required sections are present** (see template below)
6. **Delete the lock file** once the investigation file is verified complete:
   ```bash
   rm -f ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigating.lock
   ```
   The dashboard's SSE picks up the unlock and flips the pill to
   `investigated`. If the skill crashes between step 2 and 6, the lock
   stays — that's intentional, so the user knows to retry. The dashboard
   treats locks older than 30 minutes as stale and shows "investigation
   stalled — re-run `/bug-start`".

**IMPORTANT FORMATTING RULES:**
- All sections should be **human-friendly** with clear explanations
- Link to bugzilla for bug references: `[Bug {id}](https://bugzilla.mozilla.org/show_bug.cgi?id={id})`
- Link to specs when mentioning spec behavior: `[spec section](URL)`
- Link to code using searchfox: `[filename:line](https://searchfox.org/mozilla-central/source/path/to/file#line)`
- Add a separate "Implementation Guide" section at the end for Claude-specific instructions
- **DO NOT skip any sections** - fill them all out based on your investigation

### Required Metadata Frontmatter

**Every investigation file MUST begin with a YAML frontmatter block.** The
triage dashboard parses this block to surface investigation findings (root
cause, affected files, regression info) directly on the bug card without
opening the full report. The frontmatter is also how the dashboard detects
when an investigation is stale (`investigated_at` < bug's `last_change_time`).

Field schema:

| Field | Type | Required | Description |
|---|---|---|---|
| `bug_id` | int | yes | Bug number; matches the filename |
| `investigated_at` | ISO 8601 UTC string | yes | When this investigation was completed (or last refreshed) |
| `status` | string | yes | One of: `investigated`, `blocked`, `needs-info`, `no-repro` |
| `root_cause` | string | yes | One-sentence summary of what's actually broken. Empty string if status != `investigated` |
| `affected_files` | list[string] | yes | Searchfox-relative paths. Append `#L<n>` or `#L<n>-L<m>` when you cited a specific line in the body — the dashboard renders that as `file.cpp:42` and anchors the link at the line. Bare paths still work for whole-file references. Empty list when none. Examples: `dom/media/MediaDecoder.cpp` (whole file), `dom/media/MediaDecoder.cpp#L297` (specific line), `dom/media/MediaDecoder.cpp#L297-L304` (range). |
| `regression_range` | string \| null | yes | Git range like `"abc12345-def67890"` if found, else `null` |
| `related_bugs` | list[int] | yes | Bug ids surfaced during investigation (duplicates, regressors, follow-ups); empty list when none |
| `complexity` | string | yes | One of: `low`, `medium`, `high`. Best estimate of fix difficulty |
| `notes` | string | yes | Free-form 1–2 lines for nuance the other fields miss. Empty string when none |

**YAML validity — mandatory (a malformed block breaks the dashboard + viewer):**

- Emit **exactly** the fields above and nothing else. Do **not** improvise
  Bugzilla-style keys such as `component`, `title`, `bug`, `assignee`, `public`,
  `security`, or `keywords` — those belong in the `## Summary` **body**, not the
  frontmatter.
- **Double-quote any string value that contains a colon.** An unquoted `:` (or
  `::`) makes YAML start a nested mapping and the whole block fails to parse
  (*"mapping values are not allowed in this context"*). The Bugzilla component
  `Core :: Audio/Video` is the classic trap — and it goes in the body, never
  here. For any in-schema value that contains a colon (a `summary`, `root_cause`,
  or `notes` mentioning `Foo::Bar`, a ratio, etc.), wrap it in double quotes:
  `summary: "AudioContext::resume bypasses the autoplay gate"`.

The frontmatter sits BEFORE the `# Bug {bug_id} Investigation` H1 — when the
file is rendered to a human, most markdown viewers either skip the
frontmatter or render it as a structured info block; either way the H1 still
appears at the top.

**Required Document Structure (use Write tool with this template):**
```markdown
---
bug_id: {bug_id}
investigated_at: {ISO 8601 UTC timestamp at investigation time}
status: investigated
summary: "{≤90-char plain-language headline of what the bug is — the one-line preview shown in list/browse tools. No 'Bug NNNN' prefix, no trailing period. e.g. Web Audio bypasses autoplay policy under non-default blocking modes}"
root_cause: "{one-sentence what's actually broken}"
affected_files:
  - {searchfox-relative path}#L{specific line you cited in the body}
  - {searchfox-relative path}                              # bare path = whole-file reference
regression_range: null
related_bugs: [{id}, {id}]
complexity: medium
notes: "{1-2 lines of nuance, or empty string}"
---

# Bug {bug_id} Investigation

## Summary

- **Bug**: [Bug {bug_id}](https://bugzilla.mozilla.org/show_bug.cgi?id={bug_id})
- **Title**: {title}
- **Component**: {component}
- **Severity/Priority**: {severity} / {priority}
- **Status**: {status}
- **Public**: {Yes/No}

{2-3 sentence elevator pitch: what is broken, what the confirmed root cause is, and how the fix approach works. Update this whenever the root cause or approach changes.}

---

## Security Rating

> **REQUIRED for security bugs** (any `sec-*` keyword or security group). Omit for non-security bugs.

I'd suggest to have **sec-{level}** because:

- {Primary reason: attacker capability, trigger conditions, preconditions}
- {Exploitation scope: what can an attacker do if they exploit this? content process only, sandbox escape, RCE, info-leak, etc.}
- {Why not higher: what limits the severity — sandbox containment, additional preconditions, limited heap-shaping window, etc.}
- {Why not lower: what makes it more serious than the next level down}

---

## Implementation Plan

> This section captures the proposed fix and patch breakdown. If you have an
> implementation workflow (e.g. `/firefox-implementation`), it consumes this
> section — keep it current as the approach evolves.

### Patch Arrangement

{List each patch in landing order.}

| Patch | Description | Key changes | Depends on |
|---|---|---|---|
| P1 | {description} | {files + what changes} | — |
| P2 | {description} | {files + what changes} | P1 |

{If a patch establishes a new mechanism while the old one is still live, call it out:
"P4 and P5 can be reviewed in parallel but P5 must land after P4."}

{If any patch replaces a public API, note that all callers must be updated in that same patch.}

### Mechanism Replacement (if applicable)

{Omit for simple bug fixes. Use when the fix replaces an existing mechanism rather than patching it.}

**Old path:** `{CallerA} → {CallerB} → {observable effect}`
**New path:** `{CallerC} → {CallerD} → {same observable effect}`

**What to preserve:** {parts that still serve a purpose beyond the indicator role}
**What to remove:** {parts that become dead code}
**Transition strategy:** {can the two paths coexist between patches?}
**Caller audit:** {list all call sites that must be migrated if replacing a public API}

### Test Strategy

- **Type**: WPT / Mochitest / GTest / Crashtest
- **Location**: `{path/to/test}` (worktree: `~/firefox-{bug_id}/{path}` for new tests)
- **What it covers**: {brief}
- **Rationale**: {why this test type}

---

## Problem Analysis

### Problem Description

{What users experience, what should happen instead, steps to reproduce.
**Failure pattern**: consistent or intermittent? If intermittent:
- Platform(s) affected (from Treeherder `failuresbybug` API)
- Test suite(s) (e.g. `mochitest-media-wmfme`)
- Failure count and trees over last 7 days}

### Root Cause

{WHY the bug occurs. Every claim: verified (cite file:line) or labeled [Assumption].
- Which code path triggers it — [`function`](searchfox URL)
- What condition causes the problem — [`line`](searchfox URL)
- What should happen instead — [`spec section`](URL) if applicable
- Unconfirmed hypotheses MUST be labeled `[Assumption: needs X to confirm]`}

### Code Analysis

#### Key Files

{For EVERY reference, provide a searchfox link with line numbers.}

1. **[`path/to/file.cpp:123`](https://searchfox.org/mozilla-central/source/path/to/file.cpp#123)** — {what it does, why relevant}
2. **[`path/to/file.h:45`](https://searchfox.org/mozilla-central/source/path/to/file.h#45)** — {what it does, why relevant}

#### Current Behavior

{Code flow in plain English. Every reference needs a searchfox link.}

### Specification Compliance (if applicable)

- **Spec**: [Section name](URL)
- **Required**: {behavior}
- **Firefox**: {behavior}
- **Verdict**: ✅ Compliant / ❌ Non-compliant / ⚠️ Unclear

### Related Context

- **Related bugs**: [Bug {id}](https://bugzilla.mozilla.org/show_bug.cgi?id={id})
- **Recent changes**: {commit hashes if relevant}
- **Existing tests**: [`path/to/test`](searchfox URL)

---

## Patch Details

{One section per patch from the Patch Arrangement table. Fill in as the plan solidifies.}

### P1: {description}

**Scope**: {one sentence — what single concern this patch addresses}

| File | Change |
|---|---|
| [`path/to/file.cpp`](searchfox URL) | {what changes and why} |

**Test command**: `./mach test path/to/test --headless`
**Gotchas**: {anything tricky, e.g. thread safety, API contract, caller impact}

### P2: {description}

**Scope**: {one sentence}

| File | Change |
|---|---|
| [`path/to/file.cpp`](searchfox URL) | {what changes and why} |

**Test command**: `./mach test path/to/test --headless`
**Gotchas**: {if any}

---

## 🤖 Claude Notes

**Worktree**: `~/firefox-{bug_id}/`
**Build**: `./mach build` / `./mach build faster` (frontend-only) / `./mach build binaries` (C++/Rust-only)
**TDD**: write test first (must FAIL), implement fix, verify it passes.
**Do not commit** — user reviews first.

```

### After Creating Investigation File

**🚨 MANDATORY VERIFICATION - DO NOT SKIP 🚨**

**STOP! Before proceeding, verify you have created the investigation file:**

1. **Confirm file exists with Bash:**
   ```bash
   ls -lh ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md
   ```
   **IF THIS FAILS, GO BACK AND CREATE THE FILE NOW.**

2. **Verify all sections are present with Read tool:**
   - Use Read tool to check the created file
   - Ensure no sections are missing or incomplete
   - Verify all searchfox links are properly formatted
   - Check that bugzilla links work
   - **IF ANY SECTION IS MISSING, THE FILE IS INCOMPLETE. FIX IT NOW.**

3. **Verify the `Public` attribute is correct:**
   - Re-check the MCP result from Step 2: did it return any content, or "Bug not found" / authorization error?
   - If it returned any content → confirm `**Public**: Yes` is set
   - If it returned "Bug not found" / authorization error → confirm `**Public**: No` is set
   - **IF THE VALUE IS WRONG, FIX IT NOW.**

4. **Self-check before presenting:**
   - [ ] Did I use Write tool to create investigation.md?
   - [ ] Does the file exist at ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-{bug_id}-investigation.md?
   - [ ] Are all required sections filled with actual content (not placeholders)?
   - [ ] Do all searchfox links work?
   - [ ] **Every code reference (file, function, line) has a clickable searchfox link — no plain-text references remain**
   - [ ] Is the Implementation Guide section present?
   - [ ] Is `**Public**` set correctly based on the MCP result?
   - [ ] If the bug has a `sec-*` keyword or is in a security group: is the `## Security Rating` section present with a clear rating and rationale?

   **IF ANY CHECKBOX IS UNCHECKED, DO NOT PROCEED. FIX THE ISSUE FIRST.**

4. **Only after file is verified complete, present findings to user:**
   - Summarize the investigation
   - Highlight key findings (root cause, proposed solution)
   - Note any uncertainties or areas needing clarification
   - Wait for user feedback before proceeding

**If you forgot to create the file or it is incomplete:**
- ❌ DO NOT apologize and move on
- ✅ STOP IMMEDIATELY and create/fix the file NOW
- ✅ Use Write tool to create the complete investigation.md
- ✅ Re-run verification steps above
- ❌ Do not proceed to next steps until file is complete and verified
- All sections must have actual content, not just placeholders

## 6.5 Triage-Mode Template (when invoked with `--triage-mode`)

When `--triage-mode` is set, do NOT write the deep template above. Write
this shorter template instead. The frontmatter is still mandatory; it
gains a `depth: triage` field so the dashboard renders a "shallow
investigation — re-run for deep" affordance. Aim for ≤5 minutes per bug.

**Sections to INCLUDE:**
- YAML frontmatter (per the Required Metadata Frontmatter contract;
  add `depth: triage`)
- `# Bug {id} Investigation (triage mode)`
- `## Summary`
- `## Findings`
- `## Proposed Solution`
- `## Notes`

**Sections to EXPLICITLY OMIT in triage mode** — these are deep-mode only:
- ❌ `## Security Rating`
- ❌ `## Implementation Plan`
- ❌ `## Patch Arrangement`
- ❌ `## Mechanism Replacement`
- ❌ `## Test Strategy`
- ❌ `## Patch Details`
- ❌ `## 🤖 Claude Notes`
- ❌ Deep code archaeology, exhaustive call-tree expansion, spec deep-dive

### Required Triage-Mode Structure (Write with this template)

```markdown
---
bug_id: {bug_id}
investigated_at: {ISO 8601 UTC now}
status: investigated
depth: triage
summary: "{≤90-char plain-language headline of what the bug is — the one-line preview shown in list/browse tools. No 'Bug NNNN' prefix, no trailing period.}"
root_cause: "{one-sentence what's actually broken}"
affected_files:
  - {best-guess searchfox-relative path}#L{line, if a specific one is implicated}
regression_range: null
related_bugs: [{id}]
complexity: medium
notes: "{1-2 lines of nuance, or empty string}"
---

# Bug {bug_id} Investigation (triage mode)

## Summary

- **Bug**: [Bug {bug_id}](https://bugzilla.mozilla.org/show_bug.cgi?id={bug_id})
- **Title**: {title}
- **Component**: {component}
- **Current Severity/Priority**: {bugzilla's current S/P, NOT what triage proposes}
- **Status**: {status}

{2–3 sentence elevator pitch: what's broken, what evidence we have, what
this investigation does and doesn't tell us.}

## Findings

### Root cause
{1–2 sentences. Tag explicitly: "**Verified**: …" (with one code-citation
link) or "**Hypothesis**: …" (no code-citation yet — deep mode would
verify).}

### Affected files
{Best guess from observable artifacts only — profile, log, crash signature,
wiki lookup, see-also bugs. Do NOT open files to confirm. List 1–3 most
likely paths as searchfox links.}

- [`path/file.cpp`](https://searchfox.org/firefox-main/source/path/file.cpp)

### Regression range
{If found from bug history or profiler, e.g. `abc12345-def67890`. Else
"none identified".}

### Related context
{Linked bugs, duplicates, see-also entries from Bugzilla + wiki lookup.
Brief — 1 line each.}

## Proposed Solution

{2–4 sentences sketching the fix direction. High level: which subsystem,
what kind of change (e.g. "relax codec check in VideoUtils + wire a
software fallback path on Windows"). Tag "hypothesis" — deep verification
didn't run. NO file-by-file patch breakdown, NO test plan — re-run
`/bug-start {bug_id}` (deep mode) for that.}

## Notes

{Open questions; data gaps; what deep mode would need to verify. If the
root cause is a hypothesis, list the specific evidence deep mode should
gather to confirm it.}

---
*Triage-mode investigation. Re-run `/bug-start {bug_id}` (deep mode) when
ready to implement.*
```

After writing the triage-mode file, skip sections 7–11 (test selection,
TDD setup, task list, viewer, session rename) — those are deep-mode follow-ups.
Jump straight to section 6a (history log).

## 6a. Log Investigation to History

After the investigation file is verified complete, append one line to the history log.

**If Public: Yes** (MCP returned content in Step 2):
```bash
echo "$(date +%Y-%m-%d) | {bug_id} | PUBLIC | {component} | {root_cause_brief}" >> ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/history.log
```

**If Public: No** (MCP returned "Bug not found" / authorization error):
```bash
echo "$(date +%Y-%m-%d) | {bug_id} | PRIVATE" >> ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/history.log
```

Where `root_cause_brief` is 3-5 words (e.g., "missing promise rejection", "race in shutdown", "spec non-compliance").

⚠️ For private bugs: log **only** `YYYY-MM-DD | bug_id | PRIVATE`. No title, component, description, or root cause.

Also check for any prior investigations of this bug:
```bash
grep "| {bug_id} |" ${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/history.log 2>/dev/null
```
If a prior entry exists, report it to the user before presenting findings.

## 6. Review and Iteration Workflow

**After creating the initial investigation.md, enter review mode:**

### Investigation.md as Stable Ground

The investigation.md file serves as the **stable checkpoint** - the last agreed-upon understanding of the bug and solution. During discussion and iteration, this file should remain unchanged until a new approach is settled.

### Workflow States

**State 1: Initial Investigation Complete**
- investigation.md has been created with initial analysis
- Present findings to user
- Wait for feedback

**State 2: Discussion and Exploration**
- User points out corrections or issues with the investigation
- **IMPORTANT: Do NOT update investigation.md during discussion**
- Keep investigation.md as stable reference point
- Explore alternatives through code reading, spec checking, and analysis
- Ask clarifying questions
- Propose new approaches based on new understanding

**State 3: Approach Settled**
- User explicitly indicates approach is correct
- **Triggers for updating investigation.md:**
  - "Update investigation.md"
  - "Document this in the investigation"
  - "OK, write that down"
  - "Update the file with this approach"
  - "That's the right solution, document it"
- Only when user gives explicit signal to update

**State 4: Update Investigation**
- Invoke the `update-investigation` skill — it handles all edits to the file
- The skill will verify claims, apply targeted edits, and report what changed
- Wait for user confirmation of the update before proceeding

**State 5: Ready for Implementation**
- User confirms updated investigation is correct
- Proceed to test writing and implementation (sections below)

### Key Principles

1. **Investigation.md = last stable checkpoint**
   - Only update when approach is settled and confirmed
   - Never update during exploratory discussion
   - User can always refer back to stable state

2. **Discussion is exploratory**
   - Read code, analyze, propose ideas
   - All in conversation, not in file
   - File stays unchanged as reference

3. **Update only on explicit signal**
   - Wait for user to say "update investigation" or similar
   - Show what changed after updating
   - Get confirmation before proceeding to implementation

4. **Iteration is OK**
   - Can go through multiple discussion → update cycles
   - Each update creates a new stable checkpoint
   - Previous version can be seen in git history if needed

### Example Flow

```
Claude: [Creates initial investigation.md]
        "Investigation complete. The root cause is X, and we should fix it by doing Y."

User:   "The root cause is wrong - it's actually in function Z"

Claude: [Reads Z, analyzes, proposes new understanding]
        "Looking at Z, I see that... Should we approach it this way?"

User:   "Yes, but also check how Chrome handles this"

Claude: [Researches Chrome implementation]
        "Chrome does... So our approach should be..."

User:   "Perfect. Update investigation.md with this"

Claude: ✅ [Updates investigation.md]
        "Updated investigation with:
         - Root Cause: Now identifies function Z as the issue
         - Proposed Solution: Modified approach based on Chrome's pattern
         - Added Chrome source reference"

User:   "Looks good, implement it"

Claude: [Proceeds to section 7: Determine Test Type]
```

## 6b. Write Back to Firefox Knowledge Wiki

**Wiki presence gate.** This entire section applies only when the wiki is
installed:
```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo WIKI_INSTALLED
```
If that prints nothing, skip section 6b silently and continue to 6c — there
is no wiki to contribute to. If it prints `WIKI_INSTALLED`, proceed below.

If this investigation discovered a **generalizable, verified** pattern
worth remembering across future investigations, contribute it to the
Firefox Knowledge Wiki via `/firefox-wiki:add`.

**Three-part test — write back only when ALL are true:**

1. **Generalizable**: applies to multiple bugs / situations, not just
   this one. Bug-specific symptoms don't qualify; the underlying mechanism
   does. Examples that qualify:
   - "WMFVideoMFTManager returns NS_ERROR_DOM_MEDIA_FATAL_ERR for HEVC/VP9/AV1
     when HW fails; H.264 has SW fallback so it doesn't" — applies to any
     codec capability question
   - "DXVA slot cap = `media.wmf.dxva.max-videos` (default 8), enforced at
     decoder creation, not at MediaCapabilities check time" — applies to any
     DXVA exhaustion bug
   
   Examples that DO NOT qualify:
   - "Bug 2042320 has 10-bit H.264 misclassified" — bug-specific
2. **Verified**: backed by direct code evidence, not hypothesis. Include
   the searchfox link in the wiki page.
3. **Not already in wiki**: run `/firefox-wiki:lookup` first to make sure
   you're not duplicating an existing page.

**How to add:**
```
/firefox-wiki:add
```
Provide a short title, the verified fact, the source citation
(searchfox URL + the bug id that surfaced it), and the date.

If the criteria aren't met, **skip this section** — half-formed wiki
entries are worse than no entry. Better to write a wiki page on the next
investigation when the pattern is clearer.

## 6c. Investigation File Stays Local

The investigation file lives in `${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/` on your
machine. This toolkit does **not** push it anywhere — investigations are
personal working notes. Curated, reusable knowledge belongs in the shared
wiki (§6b), not in pushed investigation files.

Private bugs (sec-* keyword or in a security group) are especially
sensitive: their contents must never leave the local machine. The history
log records only the bug number for private bugs.

## 7. Determine Test Type (Critical!)

**BEFORE writing any test, determine the correct test type:**

### For Web-Exposed Features (HTMLMediaElement, Web Audio, etc.)

**⚠️ Use /spec-check FIRST:**
```
/spec-check {feature_name}
```

This will:
- Verify if feature is spec-defined
- Check what the spec requires
- Determine if WPT is appropriate

**Decision tree:**
- ✅ **Spec-defined + matches spec**: Write WPT
- ❌ **Spec-defined + doesn't match spec**: Bug might be invalid, check spec first
- ⚠️ **Not in spec / spec unclear**: Write mochitest only
- 🔧 **Internal implementation detail**: Write mochitest or gtest

### For Internal Features (decoders, media pipeline, etc.)

**Skip spec-check, go directly to:**
- Mochitest for integration testing
- GTest for C++ unit testing
- Crashtest for crash bugs

## 8. Write Test First (TDD)

### When NOT to write a test

Before writing any test, ask: **will this test reliably catch regressions?** If the answer is no, skip it — a flaky test adds CI noise without providing a trustworthy regression guard.

**Skip the test (no test at all) when:**
- The bug is a **data race / threading issue** where the race window is narrow and platform-gated. Mochitests are probabilistic in this case and will be flaky.
- The fix is in code that **cannot be exercised from JS** in a standard CI configuration (e.g. gated by `#ifdef` or a Windows-only pref that CI doesn't enable).
- Detection rate in a typical CI run would be well below 50%.

**A crashtest is acceptable (even at ~50% detection) when:**
- The bug causes an **outright crash** (not just memory corruption) in normal (non-ASAN) CI builds.
- The crashtest can run on the platforms where the crash actually occurs.
- It's cheap to write (a simple HTML page that triggers the crash path).

If neither condition is met, document the rationale in the investigation's Test Strategy section and skip the test entirely.

**ALWAYS start by writing a test if possible:**

1. **Evaluate the bug's testcase (if one exists):**
   If the bug has a `testcase` keyword or an attached test file, fetch and read it **before writing anything new**. Pulling the attachment is a file download, so go through the **`/download-guard` rule** (Yes/No `AskUserQuestion`; on Yes it fetches into the one shared folder `~/.fx-bug-toolkit/download-cache/`) — do NOT auto-download. On approval:
   ```bash
   bmo-to-md -a -o ~/.fx-bug-toolkit/download-cache/bug{bug_id} {bug_id}
   # then read the downloaded test file
   ```
   Assess robustness using the same "When NOT to write a test" criteria above. Common issues:
   - Depends on prefs CI doesn't set → can be set via `SpecialPowers.pushPrefEnv` in a mochitest
   - Requires a specific platform or build config → document as skip condition

   **Use the bug's testcase (possibly adapted) if it will be robust. Write from scratch only if the testcase cannot be made robust for CI.**

   #### FuzzingFunctions → SpecialPowers mapping (required when testcase uses `FuzzingFunctions`)

   `FuzzingFunctions` requires `fuzzing.enabled = true` and is not CI-safe as-is. When the testcase calls any `FuzzingFunctions.*` method, you MUST perform a per-call analysis and document the result in the investigation's **Test Strategy** section. For each call, determine:

   1. **What does this call actually do?** Read the `FuzzingFunctions.cpp` implementation (or the fuzzer patch if not yet landed).
   2. **Is there a SpecialPowers or plain-JS equivalent?**
   3. **Does the equivalent reproduce the bug?** (i.e. does it trigger the same IPC/JS code path?)

   Common mappings:

   | `FuzzingFunctions` call | SpecialPowers / plain-JS equivalent | Notes |
   |---|---|---|
   | `FuzzingFunctions.gc()` | `SpecialPowers.exactGC()` (async) | `exactGC` is more reliable than `forceGC` |
   | `FuzzingFunctions.cycleCollect()` | `SpecialPowers.forceCC()` | Synchronous |
   | `FuzzingFunctions.memoryPressure()` | `SpecialPowers.gc()` + observer | Approximate only |
   | `FuzzingFunctions.spinEventLoopFor(ms)` | `await new Promise(r => setTimeout(r, ms))` | Exact |
   | Custom IPC-triggering calls (e.g. `mediaSystemResourceStorm`) | **Requires C++ analysis** | Read the C++ impl; check if the IPC path is reachable from content JS. If it requires direct `ImageBridgeChild` calls or other non-JS infrastructure, it cannot be adapted. |

   **Decision rule**:
   - If ALL `FuzzingFunctions` calls have SpecialPowers/JS equivalents AND the equivalent triggers the same code path → write a mochitest/crashtest using them.
   - If ANY call requires internal C++ IPC APIs unreachable from JS content → the testcase cannot be adapted. Document: which call blocks adaptation, what C++ API it needs, and why no JS equivalent exists.

   **This analysis MUST appear in the investigation file's Test Strategy section.** Do not leave it as "uses FuzzingFunctions, untestable" — that is not sufficient. A downstream implementation workflow (e.g. `/firefox-implementation`, if you have it) uses this analysis to verify the test verdict independently.

2. **Check for existing tests in the tree:**
   ```bash
   searchfox-cli -q "test" -p dom/media/test | grep -i {relevant-keyword}
   searchfox-cli -q "test" -p testing/web-platform/tests | grep -i {relevant-keyword}
   ```

3. **Create or modify test based on spec-check recommendation:**
   - **WPT** (only if spec-compliant): `testing/web-platform/tests/`
   - **Mochitest** (Firefox-specific): `dom/media/test/`
   - **GTest** (C++ unit tests): `dom/media/gtest/`
   - **Crashtest** (crash regressions): `testing/crashtest/`

3. **Write clean tests with minimal comments:**
   - Only add comments when test logic is non-obvious
   - Test code should be self-explanatory
   - Don't over-comment every assertion

4. **Verify test fails** before implementing fix:
   ```bash
   ./mach test path/to/test --headless
   ```

5. **Document test in investigation.md:**
   - For NEW test files: Add relative markdown link `[test_name.html](../../path/to/test_name.html)`
   - For EXISTING test files: Add searchfox link `[test_name.html](https://searchfox.org/...)`
   - Brief description of what it tests
   - DO NOT copy full test content into investigation.md

## 9. Create Task List

Use TaskCreate to track work:
- Document investigation findings
- Write failing test
- Implement fix/feature
- Verify test passes
- Run mach build and test
- Submit for review

The patch arrangement in the investigation file (Proposed Solution → Patch Arrangement) drives
the task list. Each patch in the table becomes a task. When moving to implementation the patch
table carries forward verbatim — no re-planning needed (an implementation workflow such as
`/firefox-implementation`, if you have it, consumes this table).

## 10. Serve the Investigation Viewer

*(Deep mode only — `--triage-mode` parallel dispatch skips sections 7–11, so this
does not run for triage subagents.)*

After the investigation file is written and verified, start the local viewer so
the user can read this write-up in a browser, then end your chat report with a
deep link to this bug:

```bash
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "The viewer needs Python 3, which isn't on PATH (see /init)."
else
  SERVE="$("$PY" - <<'PYEOF'
import os, glob
def first_existing(paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return ""
cands = []
root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if root:
    cands.append(os.path.join(root, "viewer", "serve.py"))
for d in os.environ.get("PATH", "").split(os.pathsep):
    d = d.rstrip("/\\")
    if os.path.basename(d) == "bin":
        cands.append(os.path.join(os.path.dirname(d), "viewer", "serve.py"))
hit = first_existing(cands)
if not hit:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    m = glob.glob(os.path.join(base, "plugins", "cache", "**", "viewer", "serve.py"), recursive=True)
    hit = max(m, key=os.path.getmtime) if m else ""
print(hit)
PYEOF
)"
  if [ -n "$SERVE" ]; then
    echo "Serving viewer from: $SERVE"
    "$PY" "$SERVE" start
  else
    echo "Viewer not started: serve.py not found (is the plugin installed and Claude Code restarted? try /update). Skipping — the investigation file is already written."
  fi
fi
```

`serve.py` (cross-platform) rebuilds the index (so this bug appears) and prints
the base URL (default `http://127.0.0.1:8777/viewer.html`). The launcher finds
`serve.py` itself — `${CLAUDE_PLUGIN_ROOT}` is unreliable in skill Bash
([claude-code#9354](https://github.com/anthropics/claude-code/issues/9354)), so
it falls back to the plugin's `bin/` on `PATH`, then the plugin cache; Python
does the lookup so it behaves the same in bash/zsh/sh. Make the **closing line**
of your report a deep link — append the bug id as a URL fragment:

    View this investigation → http://127.0.0.1:8777/viewer.html#{bug_id}

If it fails or prints nothing, skip silently — the viewer is a convenience, not
a requirement. The server binds to `127.0.0.1` only.

## 11. Rename Session

As the very last step, invoke the `rename` skill to label this session with the bug number and a short description:

```
/rename bug-{bug_id}-{short-description}
```

Where `short-description` is 2-4 words derived from the bug title, hyphen-separated (e.g. `missing-promise-rejection`, `race-in-shutdown`). This must always be the final action of `/bug-start`.

## Notes

**🚨 MOST IMPORTANT: CREATE THE INVESTIGATION FILE 🚨**
- The #1 most common mistake is forgetting to create `bug-{bug_id}-investigation.md`
- After steps 2-4, you MUST use Write tool to create the investigation file
- Verify the file exists with Bash before proceeding
- Read the file back to confirm all sections are present
- DO NOT just discuss findings - WRITE THEM TO THE FILE

**Other notes:**
- If this is a crash bug, look for stack traces in comments
- If this is a spec feature, use /spec-check to research the spec
- If unclear, use AskUserQuestion to clarify the approach
- Don't commit anything - user will review first
- When creating commits, do NOT add "Co-Authored-By" lines
