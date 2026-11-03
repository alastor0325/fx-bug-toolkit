# Team profile: Audio/Video (`av`, the default)

The per-bug workflow for Firefox Audio/Video triage. [`../SKILL.md`](../SKILL.md)
owns setup, the queue, pre-flight, drafts, and apply; this file owns everything
from reading a bug to writing its draft.

## Profile settings

- **Components** (product `Core`): `Audio/Video`, `Audio/Video: cubeb`,
  `Audio/Video: GMP`, `Audio/Video: MediaStreamGraph`, `Audio/Video: Playback`,
  `Audio/Video: Recording`, `Web Audio`, `Audio/Video: Web Codecs`.
- **Queue:** `bugzilla-cli fetch --start <14 days ago>` with one `--component`
  flag per component (see SKILL.md → Fetch bugs).
- **Meta bugs:** refresh the live `[meta]` list at setup (SKILL.md → Setup
  check); fallback table in Known Meta Bugs below.
- **Extra pre-flight skip:** bugs filed by non-QA Mozilla employees (below).
- **Investigation:** §1b Fixable=Yes runs `/bug-start`.
- **Comment rules:** the §1a comment voice, ASD-STE100 writing standard, and
  Length discipline.

## Parallel dispatch additions

Append these bullets to the per-bug agent prompt (SKILL.md → Parallel dispatch):

- For §1b Fixable=Yes: invoke `/bug-start {id} --triage-mode`
  synchronously in this subagent. Parallel subagents make wall-clock
  cost ≈ `max(per-bug)` not `sum`, so total /triage time stays
  bounded. Triage mode runs in ~5 min and produces a shallow but
  useful investigation (frontmatter + Summary + Findings + Proposed
  Solution + Notes); see the `/bug-start` skill → Invocation Modes.

  The §1b decision itself is the only gate. Trust /triage's existing
  "Fixable=Yes: enough diagnostic data exists to start analysis"
  judgment — DO NOT require a specific artifact type beyond that.
  Sufficient evidence for §1b includes any of: media-preset profile
  analysis, media log with NS_ERROR / decoder signal, crash ID with
  media stack frame, reporter-identified root cause with source code
  citations, codec / configuration identification with a clear
  cross-browser failure pattern, existing current investigation file,
  and other forms of analyzable evidence. Step 2c's media-vs-generic
  profile check is the safeguard that prevents a non-media profile
  from masquerading as a media profile — that's the only artifact-type
  rule. /bug-start's own skip-if-current rule makes spurious dispatches
  cheap (they exit silently and log `outcome: skipped`).
- **Read-only analysis IS allowed — and profile analysis is MANDATORY, not
  best-effort.** You MUST analyze every Firefox Profiler link in the bug. Do NOT
  skip it because the reporter says the issue is resolved, and do NOT skip it
  because a tool failed — see "Artifact analysis is blocking" in Step 2c. If a
  profile cannot be read, upgrade the tool and retry; if it still cannot be read,
  STOP and report the bug as blocked rather than returning a draft whose analysis
  has a hole in it.
- Current profiler-cli usage (the old `profiler-cli <url> --calltree N` form no
  longer exists): `profiler-cli load <url> --session <id>` with an id unique to this subagent
  (`tr-<bug>-<token>-<run>`, `<run>` being 4 random hex digits), then pass
  `--session <id>` on EVERY subsequent query, e.g.
  `profiler-cli thread functions --session <id> --thread t-N`. The current-session
  pointer is global and a sibling agent's `load` will steal it, so never rely on
  it implicitly and never run `profiler-cli stop --all`. Each session is a
  daemon that never exits on its own: run `profiler-cli stop --session <id>`
  once done with it, including when the analysis fails.

## Extra pre-flight skip: Mozilla employees

**Filed by a non-QA Mozilla employee:**
Bug's `creator` field ends with `@mozilla.com` AND the creator is not QA.
Developer-filed bugs don't need triage; QA-filed bugs do.

Detect QA by any of these signals (OR logic):
- `cf_qa_whiteboard` field is non-empty
- `creator_detail.real_name` contains any of: `QA`, `Quality`, `Test Engineering`, `Testing`
- `/firefox-wiki:lookup qa mozilla accounts {email}` returns a match

If Mozilla employee AND not QA → Print: `Skipping bug {id} — filed by Mozilla employee ({creator}).` Move to next.
If Mozilla employee AND QA → continue with the 6-step workflow.

When a Mozilla employee is confirmed QA via wiki lookup (not by name/whiteboard),
record them: `/firefox-wiki:add` to `triage/qa-mozilla-accounts.md` with their email, name, and date confirmed.

---

## For each bug: 6-step workflow

### Step 1 — Fetch full bug + comments

```bash
bmo-to-md <id>
```

**Stale pending draft check:** before running Steps 2–6, check whether a pending file already exists:

```bash
cat ~/firefox-triage/pending/bug-<id>.json 2>/dev/null
```

If a pending file exists, compare its `created_at` against the bug's `last_change_time` from the fetch output:

- **No new comments** (`last_change_time <= created_at`): re-show the existing draft as-is. Do not re-run Steps 2–6.
- **New comments arrived** (`last_change_time > created_at`): the reporter (or someone else) has posted since the draft was written. **Discard the stale draft** and re-run Steps 2–6 from scratch on the full updated bug.

When re-running after new comments, pay special attention in Step 2c to any diagnostic artifacts in the new comments (profiler links, media logs, crash IDs, about:support). If those artifacts are sufficient to understand the root cause, go directly to §1b — which means invoking `/bug-start {id}` — rather than sending another §1a NI request.

**§1b backfill carve-out** — Even when "No new comments" applies and Steps 2–6
are skipped, **still dispatch `/bug-start {id} --triage-mode` at the end of
this subagent IF**:
1. The existing draft classifies as §1b (severity/priority set in the
   pending JSON), AND
2. No current investigation file exists at
   `$FX_BUG_INVESTIGATION_DIR/bug-{id}-investigation.md` (or it's stale
   per `/bug-start`'s skip-if-current rule).

`/bug-start`'s own skip-if-current rule handles the no-op case
efficiently: if the investigation already exists and is current, the
dispatched subagent exits silently and logs `outcome: "skipped"`. So this
carve-out is safe to apply unconditionally to §1b drafts — the cost is
one quick subagent that exits in seconds when the investigation already
exists.

This carve-out backfills investigations on §1b drafts that were created
before the queue-at-draft-time mechanism existed. Without it, those
drafts would never get `/bug-start` dispatched on a re-/triage run —
the Step 2–6 skip would also skip the dispatch.

### Step 2 — Extract what is already known

Before deciding what to ask, explicitly inventory what is present:

```
Already present:
  ✓ Platform: Windows 11
  ✓ Firefox version: 136.0
  ✓ STR: [clear steps in description]
  ✗ about:support: not provided
  ✗ Media sample or URL: not provided
  ✗ Codec/container: not specified
```

**Always do this step.** Never ask for information that is already in the bug.

**Assume Firefox always.** Bugzilla is a Firefox bug tracker. If the User Agent string shows
Chrome or another browser, treat it as a formatting artifact (reporter filed from a different
profile or copied the wrong UA). Never ask the reporter to confirm whether they are using Firefox
— assume they are and proceed with the triage.

#### Step 2b — Analyze about:support (if present)

If about:support is included in any comment (look for "Application Basics" or "Important Modified Preferences"), extract and analyze the following sections. All findings feed directly into Steps 3–5.

**Re-run Step 2b on every new reporter response** that contains about:support — prefs and state may have changed.

---

**1. Important Modified Preferences**

Find `media.*` prefs that are non-default. Flag any that could explain or contribute to the issue.

Key prefs to watch and their defaults:

| Pref | Default | Risk if changed |
|---|---|---|
| `media.hardware-video-decoding.enabled` | `true` | **Critical** — disabling removes HW decode path entirely |
| `media.ffmpeg.disable-software-fallback` | `false` | **High** — combined with disabled HW decode, leaves no working decode path |
| `media.ffmpeg.enabled` | `false` on macOS/Win, `true` on Linux | Medium — enabling on macOS/Win activates non-default decode path |
| `media.ffvpx-hw.enabled` | `false` | Medium — experimental HW path via ffvpx; only AV1/VPX on macOS/Win (see [[triage/ffvpx-hw-decode-codec-support]]) |
| `media.mediasource.experimental.enabled` | `false` | Medium — experimental MSE features |
| `media.autoplay.default` | `1` | Low — autoplay policy, unlikely to cause failure |

If high-risk prefs are found, that becomes the primary ask in §1a: reset all `media.*` prefs first, then reproduce and capture a media log.

**Important:** after resetting any HW decode prefs, the reporter must **fully close all Firefox instances and restart** before testing — the pref change does not take effect until then. Always include this in the NI comment.

---

**2. Decision Log**

Look for the `HARDWARE_VIDEO_DECODING` and `HARDWARE_VIDEO_ENCODING` entries. They show whether HW decoding is available, and if not, *why* (blocklisted, pref-disabled, driver issue, etc.).

```
HARDWARE_VIDEO_DECODING:
  default: available,
  user: disabled, User disabled via media.hardware-video-decoding.enabled pref
```

Note the failure code — it distinguishes user-disabled from driver blocklist from capability missing.

---

**3. Media — Codec Support Information**

Shows per-codec decode/encode support. Check whether the relevant codec (H.264, AV1, VP9, HEVC, etc.) shows SW and/or HW support. If a codec shows no support at all, the issue may be a missing decoder rather than a configuration problem.

---

**4. Media — Content Decryption Modules (CDM) Information**

Shows installed CDMs (Widevine, OpenH264, WMF CDM / PlayReady). Relevant for EME/DRM bugs. Check if the expected CDM is present and its version. Mostly useful for `Audio/Video: GMP` bugs.

---

**5. Graphics section**

Check:
- **GPU info** — GPU vendor/model, driver version (relevant for HW decode failures)
- **WebRender / compositor** — software vs hardware compositing (can affect playback rendering)
- **Feature flags** — any features listed as BLOCKED or DISABLED that relate to video

Summarize findings as part of the inventory:
```
  ✓ HW decoding:   user-disabled via pref (HIGH RISK)
  ✓ H.264 support: SW available, HW unavailable (blocked)
  ✓ CDM:           Widevine 4.10.x present
  ✓ GPU:           Apple M2, driver N/A
```

#### Step 2c — Analyze diagnostic artifacts (if present)

**Before analyzing artifacts, look up the Firefox Knowledge Wiki for relevant components.**
The wiki (`~/firefox-wiki/components/`) contains known behaviors, quirks, and root
causes for components like `D3D11DXVA2Manager`, `WMFVideoMFTManager`, `MediaCapabilities`,
`MDSM`, etc. Run:
```
/firefox-wiki:lookup <ComponentName>
```
Known facts from the wiki can identify the root cause without reading code. Only read
source code if the wiki doesn't cover the observed symptom.

When the bug or a reporter reply contains links or attachments for profiler captures,
media logs, or crash IDs, **attempt analysis before proceeding to Step 5**. Do not
skip this and assume more data is needed — the artifacts may already be sufficient
for §1b.

**⚠️ Triage scope limit — do NOT inline-investigate code during triage:**
Triage's job is to identify *what kind of problem this is* and whether enough data
exists to start a fix. When you reach §1b (root cause identifiable), **stop** — do
not read source files, trace call stacks, or reason about fix approaches. That work
belongs in `/bug-start`. The correct flow is:
1. Profile/log analysis → identify symptom pattern (e.g. "DXVA failure per scroll")
2. Wiki lookup → check if root cause is already known
3. If yes: root cause confirmed → §1b Fixable=Yes → hand off to `/bug-start`
4. If no: symptom pattern identified but root cause unclear → still §1b if data is
   sufficient to investigate, or §1a if more data needed

The anti-pattern to avoid: seeing a `DXVA failure:` in the profile → reading
`DXVA2Manager.cpp` → checking `sDXVAVideosCount` → checking prefs → reasoning
about capability API mismatches — all during triage. This is `/bug-start` work.

**Firefox Profiler links (`share.firefox.dev/*` or `profiler.firefox.com/public/*`):**
- Do NOT use WebFetch — these are JavaScript SPAs; WebFetch returns only the CSS shell.
- Prefer **`/analyze-profile <url>`**: it runs the full standard query set, checks all
  media threads, pattern-matches against known signatures, and produces a structured
  findings report. Record that report in the inventory, and use its "Sufficient for
  §1b?" field to decide §1a vs §1b rather than judging independently.
- Driving `profiler-cli` directly is acceptable when `/analyze-profile` is unavailable
  or has already failed. Use the current subcommand form — **the `profiler-cli <url>
  --calltree N` and `--log-markers` forms no longer exist**:
  ```bash
  profiler-cli load <url> --session <id>                    # <id>: tr-<bug>-<token>-<run>, unique per run
  profiler-cli profile info --all --session <id>             # threads + CPU by process
  profiler-cli thread list        --session <id>             # every thread's t-N handle
  profiler-cli thread functions   --session <id> --thread t-N --min-self 2
  profiler-cli thread markers     --session <id> --thread t-N --search DXVA
  profiler-cli stop               --session <id>             # always, even on failure
  ```
  Always pass `--session <id>`: the current-session pointer is global and any
  concurrent `load` steals it. Never run `profiler-cli stop --all`. The final `stop`
  is required: the daemon holds the profile in memory and never exits on its own.

**⚠️ Artifact analysis is BLOCKING — never ship an analysis with an unread artifact.**
If an artifact that the conclusion depends on (a profile, a memory report, a log, a
crash dump) cannot be read because of **our** tooling — version too old, unsupported
format, missing binary — that is not a caveat to note and move past. It is a blocker.
Do all of the following, in order:
1. **Fix the tool and retry.** Upgrade or install it (e.g.
   `npm install -g @firefox-devtools/profiler-cli@latest` when profiler-cli reports the
   processed-profile format is newer than it supports), then re-run the analysis.
2. If it still cannot be read, **do not present the draft as complete.** Say plainly
   which artifact is unread, why, and that the analysis is therefore incomplete.
3. Never convert our tooling gap into a reporter ask. Asking someone to re-capture a
   perfectly good profile because our reader is out of date wastes a round trip and
   reads as not having looked.
The reporter-side equivalent (a log emailed to media-alerts, an attachment awaiting
download approval) is genuinely unanalyzable and is recorded as such — that is a
different case from our own tool being stale.

**⚠️ A capture that reproduces on the GOOD version cannot isolate a regression.**
Before drawing regression conclusions from a profile, check *how it was captured*. A
**safe-mode** capture forces software compositing and software decode, so it looks
pathological on every build and tells you nothing about what changed. If the reporter
says the symptom appears in safe mode on both the last-good and first-bad versions,
their safe-mode profile characterises the safe-mode baseline, not the bug: record it as
such in the inventory and ask for a **normal-mode** capture. When the reporter cannot
capture one through the profiler UI, the `about:logging` route (Media Log Instructions
below) is a *different* capture path and often works where the UI failed. Surfaced by
bug 2071427, whose only profile was safe mode while the bug was a 156-only regression.

**Media profile vs generic profile — REQUIRED check before §1b:**
A profile link by itself does NOT prove a media bug is investigatable. The
capture must be a **media-preset profile** (recorded with the "Media" preset
in Firefox Profiler), so it includes the media-specific threads:
`MediaDecoderStateMachine`, `MediaSupervisor`, `MediaPDecoder`, `AudioSink`,
`AudioIPC`, `cubeb`, plus markers like `DXVA` and `NS_ERROR_DOM_MEDIA_*`.
A generic CPU/JS/networking profile will surface none of this signal and
**cannot support a §1b classification** for a media bug — Firefox A/V triage
covers media bugs exclusively.

When `/analyze-profile <url>` runs, scan its output for the media-thread
list. If **none** of the expected media threads (MDSM, MediaSupervisor,
MediaPDecoder, AudioSink, AudioIPC, cubeb) appear, the profile is NOT a
media profile. In that case:
- Record `profile (non-media)` in `inventory_present`.
- Add `media profile` to `inventory_missing`.
- **Do NOT classify as §1b** on the strength of the link alone — fall back
  to §1a with an NI asking the reporter to capture a new profile using the
  "Media" preset (see the NI templates). The existing non-media profile is
  fine to retain for context but it doesn't unlock §1b.

If at least one expected media thread appears in the report, record
`profile (media)` in `inventory_present` and §1b remains open as documented.

This rule exists because a previous bug (2040168) was misclassified §1b on
the strength of a non-media profile alone — the inventory check passed
("profiler link") but the artifact lacked the threads needed to actually
investigate the issue. Inventory items now carry the media-vs-non-media
distinction so this can't recur.

**Media logs attached inline in comments:**
- If log content appears directly in a comment (JSON or text), extract and scan it:
  look for `NS_ERROR_*` codes, decoder selection (`AppleMedia`, `ffvpx`, `VPX`),
  MSE state transitions, network stalls, `MediaDecoderStateMachine` errors.
- Summarize findings in the inventory before deciding §1a vs §1b.

**Media logs emailed to media-alerts@mozilla.com:**
- Record: `✓ Log sent via email — not accessible to triage bot`. Treat as present but
  unanalyzed. Do not ask the reporter to re-send.

**Crash IDs (`bp-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`):**
- Fetch via WebFetch: `https://crash-stats.mozilla.org/api/ProcessedCrash/?crash_id={id}`
- Extract: crash signature, OS, module/frame that crashed, any media stack frames.
- A crash ID with a clear media signature is sufficient for §1b.

**When analyzing a profile, always check ALL media-related threads**, not just `MediaDecoderStateMachine #1`. Run:
```bash
profiler-cli thread markers --session <id> --thread t-N --search "DXVA"
profiler-cli thread markers --session <id> --thread t-N --search "NS_ERROR"
```
Check `MediaSupervisor #N`, `MediaPDecoder #N`, `MediaPDecoder` in the **rdd** process, the GPU process's `Renderer`, and `GeckoMain` in addition to MDSM. Missing a thread means missing the root cause. Read CPU *and* wait state: a decoder thread sitting in `NtWaitForMultipleObjects`/`ZwWaitForAlertByThreadId` with large inter-frame gaps is **starved**, which is a different bug from a decoder that is saturated.

**HW decode failure pattern — always investigate capability API accuracy:**

When the profile contains repeated `DXVA failure:` or `NS_ERROR_DOM_MEDIA_*` entries, ask:
1. **Why does it fail each time?** Common causes:
   - DXVA slot exhaustion: `DXVA failure: D3D11: Too many DXVA videos playing` — Firefox caps concurrent DXVA decoders at `media.wmf.dxva.max-videos` (default 8). Feed-style sites (douyin, TikTok, Instagram) keep many videos alive simultaneously and hit this limit.
   - `CanUseDXVA()` returning false for this specific video's parameters (resolution, color depth, pixel format)
   - D3D11 device creation failure (driver issue, GPU reset)
2. **Does the capability API accurately reflect runtime availability?** `WMFDecoderModule::Supports()` (used by `MediaCapabilities.decodingInfo()`) checks only process-level `sDXVAEnabled` and MFT type presence — it does **not** check the current DXVA slot count. So Firefox can report a codec as `HardwareDecode` supported even when new decoders will immediately fail at runtime.
3. **Does the failing codec have a software fallback?** In WMF: H.264 has SW fallback; HEVC, VP9, AV1, VP8 do **not** (`WMFVideoMFTManager.cpp` returns `NS_ERROR_DOM_MEDIA_FATAL_ERR` if HW fails for these). A capability mismatch is especially impactful for no-fallback codecs — the site gets `NS_ERROR_DOM_MEDIA_METADATA_ERR` and must re-probe with a different codec.

When all three conditions are present (repeated HW failure + no-SW-fallback codec + capability API reports supported), this is §1b — root cause is identified, two separate bugs:
- The DXVA limit or HW failure root cause
- The capability API not reflecting runtime HW availability

**Decision rule:** after Step 2c, update the inventory with artifact findings and use
them — not just checklist presence — to determine §1a vs §1b in Step 6. A bug with
a *media* profiler link (per the media-vs-generic check above) + clean about:support
+ repro URL is likely §1b even if the log content itself is unanalyzable by the
triage bot. A *non-media* profiler link does NOT unlock §1b on its own — the bug
needs a media profile (or another equally-informative media artifact: media log with
NS_ERROR/decoder signal, or a crash ID with a media stack frame) before §1b applies.

### Step 3 — Classify bug type

| Type | Indicators | Typical component |
|---|---|---|
| Crash | "crash", crash-stats URL, crash ID in title/comments | Any |
| Regression | "used to work", "stopped working", "broke in", version comparison | Any |
| Playback failure | video/audio element not playing, codec/container mentioned | Audio/Video: Playback |
| Recording | getUserMedia, MediaRecorder, microphone, camera | Audio/Video: Recording |
| Web Audio | AudioContext, AudioNode, Web Audio API | Web Audio |
| Web Codecs | VideoDecoder, VideoEncoder, AudioDecoder, AudioEncoder | Audio/Video: Web Codecs |
| Performance / audio quality | slow, high CPU, dropped frames, buffering, audio glitch | Audio/Video: Playback, cubeb, MediaStreamGraph |
| GMP / EME | CDM, Widevine, PlayReady, EME, encrypted media | Audio/Video: GMP |
| Build / infra | compile error, test failure, CI | Any |

When a bug is a **Regression** (it used to work, or you identify a regressor),
record the signal in the draft so it's tagged on Bugzilla and surfaces in the
dashboard's `regression` rail tag: add `keywords_add: ["regression"]` and/or a
`see_also` entry labelled `regressor`. Do not leave a known regression with no
regression signal in its draft.

**When the regressor bug is known** (a bisection result, a "regressed by bug N"
note, or your own Step 4 root-cause identifying the causing change), also set
`regressed_by_add: [<regressor_bug_id>]`. This populates Bugzilla's structured
`regressed_by` relation (not just the `regression` keyword) via
`bugzilla-cli set-fields --regressed-by-add`, which apply runs automatically. A
`see_also` regressor label is the soft signal; `regressed_by_add` is the
authoritative relation — set it whenever you actually know the regressor, never
guess an ID.

### Step 4 — Check for duplicates and meta bug match

**4a — Duplicate search:** Search for similar bugs in the in-scope components
using keywords from title/description. Also check the dependency list of any
matching meta bug (Step 4b).

If a likely duplicate is found → propose marking as duplicate (§1c).

**4b — Meta bug match:** Check against the known meta bugs list below. If a
match is found, record the meta bug number to add as a blocker.

### Step 5 — Determine info gaps

Cross-reference extracted inventory against required info per bug type. Only flag
items that are genuinely absent:

| Bug type | Required info |
|---|---|
| Crash | crash-stats URL or crash ID, about:support, STR |
| Regression | first broken / last good build (suggest mozregression), STR |
| Playback failure | media URL or sample file, codec/container, about:support, platform |
| Recording | device info, getUserMedia constraints, repro page or snippet |
| Web Audio | minimal reproducible JS snippet, AudioContext config, about:support |
| Web Codecs | minimal reproducible JS snippet, codec config, about:support |
| Performance / audio quality | `about:logging` capture with media preset (see Media Log Instructions), platform, STR |
| GMP / EME | key system (Widevine/PlayReady), platform, about:support |

### Step 6 — Branch

- **§1a** — info gap detected → needs info path
- **§1b** — enough info → triage path
- **§1c** — duplicate / invalid / not-our-bug → close/reassign path


## §1a — Needs Info Path

P/S is **not changed** when sending NI.

Draft a comment asking only for items identified as missing in Step 5. Always include:
- The specific missing items
- `about:support` if not already provided
- Media log instructions (Loom link) if the issue is audio/video/performance-related
- mozregression hint if it is a regression

**Standard diagnostic questions to consider** (include only what is relevant):

| Question | When to ask |
|---|---|
| Does this happen in Private Browsing mode? | Any playback/recording issue — rules out extensions |
| Does this happen on all videos, or only certain ones? | Playback failures |
| Does this happen on a specific codec only? (H.264, H.265, AV1, VP9) | Playback failures with codec hint |
| Could you please share a public link that shows the problem? | When reported URL requires login |
| If the content is private, send it to media-alerts@mozilla.com. Then set needinfo on the triage owner. | When no public repro is possible |

**Prose budget for a needs-info comment: 60 words, excluding the capture and
mozregression blocks.** Those blocks are procedures and are exempt; they are
quoted verbatim and must not be shortened. The 60 words cover everything else.
Three things that are not instructed anywhere and still appear in most drafts,
all of them prohibited:

- **No praise or restatement paragraph.** One clause at most.
- **No hypothesis.** A guess at the mechanism is for us, not for the reporter,
  who cannot act on it. It also commits us in public before the evidence exists.
- **No justification of the ask.** Do not write a paragraph on why the existing
  artifact is insufficient before asking for the next one.

**At most one narrowing question**, chosen from the table above. Three questions
in one comment lowers the chance that any of them is answered.

**NI targets:** reporter by default; add others who confirmed reproduction if mentioned in comments.

**Email resolution:** BMO's REST API requires the full email address for needinfo flags — the `:alias` shorthand (e.g. `:sotaro`) only works in comment text and the web UI. If you only know someone's alias, look up their email in a recent bug comment or ask the user. Known aliases: `:sotaro` → `sotaro.ikeda.g@gmail.com`.

Write `~/firefox-triage/pending/bug-{id}.json` — including the `bug_context` block populated from Steps 2/2b/2c (see Pending JSON Format below). Then show:

```
─── DRAFT: Bug {id} — {title} ───────────────────────────────
[INTERNAL — not posted]
Already in bug:
  ✓ {item}: {value}
  ✗ {item}: missing → will ask

COMMENT (posted to Bugzilla):
[If about:support analysis found significant findings:]
**Analysis**

{1–3 sentences summarizing relevant findings from about:support, e.g. non-default
prefs detected, HW decode status, codec support gaps. Write for both the reporter
and developers reading later. Do NOT reproduce the ✓/✗ inventory here.}

**Next Steps**

{Ask only for genuinely missing items. One bullet per item. For audio/video/performance
bugs the media-log capture is item 1 by default (see Media Log Instructions) — UNLESS
high-risk prefs were found, in which case lead with the reset + restart and make the
capture the next item.}

[If no about:support or no significant findings, omit the Analysis section and lead
directly with a brief acknowledgement + the Next Steps ask.]

[media-log capture block — the FIRST Next Steps item for A/V/perf issues (or right after
the pref-reset step when high-risk prefs were found)]
[mozregression block if regression]

NI TARGETS: {email1} (reporter)[, {email2}]
META BUG BLOCKER: [bug {n} — {alias}] or [none]
P/S: unchanged

ACTIONS ON APPROVAL (apply {id}):
  POST comment via bot account                      → bugzilla-cli post-comment {id} "..."
  [SET needinfo?({email1})]  (skip if NI already set) → bugzilla-cli set-ni {id} {email1}
  [SET blocks: bug {n}]      (skip if already blocks)  → bugzilla-cli set-fields {id} --blocks-add {n}
  [Owner CC / NI: off by default — toggle "CC me"/"NI me" in the dashboard to add $TRIAGE_OWNER]

Type "apply {id}" to post, "skip {id}" to skip.
─────────────────────────────────────────────────────────────
```

The ✓/✗ inventory is internal triage bookkeeping shown in the terminal only — it
is **never included in the posted comment**. The comment should read as a natural,
human-readable response, not as a checklist.

**Comment voice — the triage account is a bot, not a person. Write advisory, not
volitional.** Never use first-person preference/intention phrasing in a posted
comment: avoid "I'd like to…", "I'll take a look", "I'll start…", "I want to…",
"I personally…", "let me…". Use neutral or advisory phrasing instead:
"We recommend…", "The next step is…", "This looks like…", "We can…". This
applies to **every** posted comment.

**Never state severity or priority in the posted comment.** S/P are Bugzilla
*fields*, set via the dropdowns (`set-fields`) — that is the single source of
truth. Repeating an `S{n}`/`P{n}` label in the comment prose only goes out of
sync the moment someone adjusts the dropdown, so leave it out entirely. Do not
write "marking this S2/P2", "raising severity to S2", "this is a P1", or any
`S{n}`/`P{n}` token in the comment. The **suggested** S/P is **not** dropped — it
still lives in the internal ASSESSMENT block, the ACTIONS ON APPROVAL / dashboard
"Will apply" diff, and the pending JSON's `priority`/`severity`, so apply still
sets it as a field. You may still describe user-facing **impact** in prose
("this is a complete playback failure with no workaround") — just never the S/P
*label*.

**Keep the findings in the comment; make only the Next Steps reporter-clear.**
Do NOT strip the root-cause analysis/findings out of the posted comment to
"simplify" it — the Analysis (including code-level root cause, citations, and
the planned fix direction) is valuable on the bug for developers and shows the
reporter the issue is understood, so keep it. What must be plain and actionable
is the **Next Steps** section the reporter acts on: a clear, numbered workaround
or a concrete "what to capture", not engineering jargon. In short: full Analysis
+ developer detail stays; only the reporter's Next Steps get simplified.

**Writing standard: ASD-STE100 Simplified Technical English.** Every comment
drafted for posting to Bugzilla (§1a, §1b and §1c drafts, and every refine of
them) MUST follow ASD-STE100, together with the comment voice, S/P and
Length discipline rules.

- **Words.** Use simple, common English words with one meaning each. Use a word
  only as the part of speech that STE approves (e.g. "test" as a noun, not "to
  test"). Do not use synonyms for the same thing: if you call it "the decoder"
  once, do not call it "the codec" later.
- **Technical names are allowed.** Function, class, file, pref, API, codec,
  component and product names (`MediaFormatReader`, `media.ffmpeg.enabled`,
  H.264, WebRender, Firefox) and bug numbers stay as they are. Do not simplify
  them.
- **Instructions** (procedural steps the reader follows, such as the capture
  block): imperative, one instruction per sentence, 20 words max: "Open
  `about:logging`.", "Set `media.ffmpeg.enabled` to false, then restart Firefox."
- **Requests to a named person** (a developer we needinfo, a QA person, the
  reporter, or anyone pinged with `:nick`): a polite request, not a bare
  imperative. Use "Could you please …?" or "Would you mind …?", and add "when
  you have time" where it fits. One request per sentence, 25 words max:
  ":stransky, could you please take a look at this Vulkan direct export problem
  on NVIDIA?", ":aosmond, could you please confirm whether …?" The request is
  polite; the numbered steps under it stay imperative.
- **Descriptive sentences:** 25 words max. A sentence over the limit is two
  sentences.
- **Active voice.** Write "The decoder rejects the stream", not "The stream is
  rejected by the decoder".
- **Simple tenses only.** Use present, simple past, or future ("will"). Do not
  use an "-ing" form as the main verb or a perfect tense ("has regressed"
  becomes "regressed").
- **No noun clusters** of more than 3 words. Split them with "of", "for", and
  similar words ("the decode error for hardware video", not "the hardware video
  decode error").
- **Keep articles** ("a", "the") and short connecting words. Do not write in
  telegraph style.
- **No dash or hyphen used as an aside.** Use a comma, a colon, or two sentences.
- **Paragraphs.** One topic per paragraph, 6 sentences max (the comment budgets
  in this skill are stricter, so they win).
- **Warnings first.** If a step carries a risk or a workaround has a side
  effect, put it at the start of the sentence: "Caution: this also resets your
  other `media.*` prefs."
- **Exempt:** code, identifiers, quoted log lines, link text, and the media-log
  capture block (see Media Log Instructions), which is quoted verbatim.

**Length discipline.** Measured across 38 real drafts, the median posted comment
was 296 words and 16 sentences, with a worst case of 1026 words. That is too long
to be read. "Be brief" does not work as an instruction, so these are counted
limits and explicit prohibitions. The sentence limits and the dash rule are in
the writing standard above.

- **Do not restate what the reporter already told you.** They know what they
  reported and what they ruled out. One clause of acknowledgement is the limit.
- **Do not explain why you need an artifact.** Ask for it. A reporter does not
  need a justification before a request.
- **Do not report what you eliminated.** "The reader is not short of input",
  "downstream is regular as well", "pref-backed state is not at risk" answer
  questions nobody asked, and they are the single largest source of length. This
  is **not** in tension with "keep the findings" above: the root cause, the
  citations and the fix direction all stay. What goes is the search path that
  found them.
- **Do not narrate the investigation.** "The piece that was missing", "that is
  the thread worth pulling", "the interesting case is". Open on the conclusion.
- **One measurement per claim.** Cite the number that supports the point, not
  the whole set for every subsystem you looked at.

**Verify a fix attribution before stating it.** Before telling a reporter (or
writing in `ai_reasoning`) that a specific bug/change fixed an issue, check its
landing/build date against the build that still reproduced — *a change already
present in the reproducing build cannot be the fix.* If the issue is reported
fixed but no fixing change landed in the regression window, say the fix is
unconfirmed and recommend `mozregression`; for site-specific issues (e.g.
YouTube) also consider a server-side change.

## §1b — Triage Path

Apply the P/S standard. Check meta bug blocking.

**If Fixable = Yes:**
1. Invoke `/bug-start {id}` first — do NOT set any fields or post any comment before it completes.
2. After `/bug-start` completes, read the investigation file and determine the outcome:
   - **Root cause found** → draft a comment summarising findings + next steps (do **not** state severity/priority in the comment — see the comment-voice rules; write it to the ASD-STE100 writing standard and Length discipline in §1a), then apply the suggested P/S **as fields** and the meta bug blocker in the same `apply` (one atomic action). Do **not** auto-CC or auto-NI the triage owner — that's the owner's per-draft choice via the dashboard's "CC me" / "NI me" checkboxes (default off); a checked "NI me" is the "ready for implementation, owner's attention" signal. **Never include a link to the local investigation file** (`$FX_BUG_INVESTIGATION_DIR/`) in the Bugzilla comment — it is an internal working document, not a public artifact.
   - **Investigation reveals missing info** → fall back to §1a; draft NI comment asking for the specific missing data, with the suggested P/S applied **as fields** in the same `apply` (not stated in the comment).
3. **Never set P/S or meta bug blocker as standalone operations** — always bundle them with a comment so Bugzilla shows a coherent update.

**Asking the reporter for anything = a reporter needinfo.** Even on a §1b draft
(P/S set, root cause investigatable), if the comment requests *any* artifact or
action from the reporter — a media-preset profile, a media log, about:support, a
sample, STR, or a workaround-test result — that is a reporter action: add the
reporter (`bug_context.reporter_email`) to `ni_targets`, and never phrase it as
"no action needed from you". The reporter NI is independent of the owner's "CC
me"/"NI me" choice above. A profile/log request drafted with no NI silently
strips the tracking (the bug never enters Awaiting) — surfaced by bug 2044925,
whose §1b draft said "No action needed from you" while asking for a profile. If
you genuinely need nothing from the reporter, then don't ask — omit the request
entirely rather than leaving a dangling, untracked one.

**If Fixable = No (root cause unknown, more data needed):** skip investigation, go directly to §1a.

### Priority & Severity Standard

**Severity:**

| Severity | Definition | Examples |
|---|---|---|
| S1 | Complete loss of core media functionality; crash; data corruption; security issue | Browser crashes on media playback; camera feed corrupts recorded file |
| S2 | Major feature broken with no workaround; regression from a previous release | Video playback completely broken on a common codec; getUserMedia returns error on all devices after an update |
| S3 | Feature degraded but a workaround exists; regression in Nightly/Beta not yet in release | Playback fails for a specific rare container; audio desync on long files |
| S4 | Minor / cosmetic / low-impact; spec compliance gap with no user-visible breakage; enhancement | Poster frame not shown for 1 frame before play; minor wording in error message |

**Priority:**

| Priority | Definition | Examples |
|---|---|---|
| P1 | Must fix before next release; active regression or crash affecting significant users | S1 bug confirmed on release; regression from a landed patch blocking uplift |
| P2 | Should fix in current cycle; confirmed reproducible bug with known user impact | Playback failure reproducible with clear STR; crash reproducible reliably |
| P3 | Fix when possible; low user impact or hard-to-reproduce edge case | Obscure codec variant; single-reporter issue with no duplicates |
| P4 | Tracking / future work; spec gaps, enhancements, cleanup | Implementing a new codec variant; improving error messaging |

**Decision matrix:**

| Situation | Severity | Priority |
|---|---|---|
| Crash with crash-stats ID, multiple reporters | S1 | P1 |
| Playback regression introduced in current Nightly | S2 | P1 |
| Playback broken on a specific site, no workaround | S2 | P2 |
| Playback broken for a codec/container, another format works | S3 | P2 |
| Recording works but quality is degraded | S3 | P3 |
| CI / test-infra crash (e.g. xpcshell), no user-facing playback impact | S3 | P2 |
| Debug-only assertion (`MOZ_ASSERT`/fuzzing), benign/cosmetic in release | S4 | P3 |
| Feature request / enhancement | S4 | P4 |

Rate severity by **user-facing impact, not crash frequency**. A crash that
only happens in CI / test infrastructure (e.g. an xpcshell `plugin-container`
SIGABRT), however frequent, is **S3** — S2 is reserved for serious user-facing
breakage. Do not let a high CI failure count inflate it to S2/P1.

**Debug-only assertions:** a `MOZ_ASSERT` (or other debug-only assertion,
typically fuzzing/site-scout filed with the `assertion`/`pernosco` keywords)
does **not** exist in release builds, so rate it by its **release-mode
consequence** — what happens when the assertion is compiled out — not by the
fact that an assert fires. If the release behavior is benign or merely
cosmetic (e.g. a transiently wrong `played` TimeRange), it is **S4**. Only
rate it higher when the same code path produces a real release-build crash,
UAF, or data corruption once the assert is gone. Do not default a debug-only
assert to S3.

### Fixability assessment

| Outcome | Meaning | Next action |
|---|---|---|
| Fixable | Root cause is clear or investigatable (enough diagnostic data exists to start analysis) | Show ASSESSMENT + ACTIONS ON APPROVAL; wait for `apply {id}`, then invoke `/bug-start {id}` |
| Root cause unknown, more data needed | Diagnostic info still missing after triage | Back to §1a — NI for specific diagnostic data |
| Root cause unknown, no path forward | All info gathered, still can't locate problem | §1c — add `stalled` keyword + comment |
| Works as intended | Behavior matches spec or design intent | §1c — INVALID/WONTFIX |
| Not our bug | Wrong component, OS/driver, third-party | §1c — component change or INCOMPLETE |
| Already fixed | Matching fix found in recent commits or another bug | §1c — FIXED or DUPLICATE |

Show assessment for all §1b cases. **Never execute Bugzilla writes before user approval** — always
write `~/firefox-triage/pending/bug-{id}.json` — including the `bug_context` block populated from Steps 2/2b/2c — and show the draft, then wait for `apply {id}`:

```
─── ASSESSMENT: Bug {id} — {title} ──────────────────────────
  Severity: S{n} — {one-line rationale}
  Priority: P{n} — {one-line rationale}
  Meta bug blocker: bug {n} ({alias}) [or none]
  Fixable: [Yes — {reason} / No — {reason}]

ACTIONS ON APPROVAL (apply {id}):
  [SET severity → S{n}]  (skip if already S{n})           → bugzilla-cli set-fields {id} --severity S{n}
  [SET priority → P{n}]  (skip if already P{n})           → bugzilla-cli set-fields {id} --priority P{n}
  [SET blocks: bug {n}]  (skip if already blocks)         → bugzilla-cli set-fields {id} --blocks-add {n}
  [POST comment]                                          → bugzilla-cli post-comment {id} "..."
  [SET needinfo?({reporter})] (§1a only)                  → bugzilla-cli set-ni {id} {reporter}
  [Owner CC / NI: off by default — toggle "CC me"/"NI me" in the dashboard to add $TRIAGE_OWNER to cc_add/ni_targets]
  [Fixable=Yes: /bug-start already run before this apply]

Type "apply {id}" to execute, "skip {id}" to skip.
─────────────────────────────────────────────────────────────
```

For Fixable = Yes: after `apply {id}` executes the field changes, invoke `/bug-start {id}` automatically.

---

## §1c — Close / Reassign / Duplicate

| Case | Proposed action | CLI command |
|---|---|---|
| Duplicate of bug {n} | DUPLICATE → bug {n}, add comment explaining the link | `bugzilla-cli set-fields {id} --status RESOLVED --resolution DUPLICATE --dupe-of {n}` |
| Works as intended | INVALID + comment explaining design intent / spec reference | `bugzilla-cli set-fields {id} --status RESOLVED --resolution INVALID` |
| Not reproducible / insufficient info | INCOMPLETE + comment | `bugzilla-cli set-fields {id} --status RESOLVED --resolution INCOMPLETE` |
| Already fixed | FIXED or DUPLICATE of fixing bug | `bugzilla-cli set-fields {id} --status RESOLVED --resolution FIXED` |
| No path forward | Add `stalled` keyword + comment | `bugzilla-cli set-fields {id} --keywords-add stalled` |
| Wrong component | Reassign to correct component + comment | `bugzilla-cli set-fields {id} --product "{product}" --component "{component}"` |

### ⚠️ WORKSFORME — never use prematurely

**WORKSFORME is almost never the right resolution from triage.** Do NOT use it based on:

- The reporter saying "it doesn't reproduce anymore" — intermittent issues come and go; the problem still exists
- Another engineer or user being unable to reproduce — different hardware, bandwidth, or timing can hide the issue
- A profile captured during the issue showing an idle state — the capture window may have missed the active period

**WORKSFORME is only valid when:**
- A specific commit or bug is identified that deliberately fixed it → use FIXED or DUPLICATE instead
- The behavior is confirmed to match design intent → use INVALID instead

**When the reporter provides a profile captured during the issue AND says it no longer reproduces:**
- Analyze the profile for root cause (Step 2c) — the issue was real when the profile was captured
- If the profile reveals a root cause → §1b, pursue investigation
- If the profile is inconclusive → leave the bug open, add a comment acknowledging the profile and noting the intermittent nature; set P3/S3 and add to the relevant meta bug blocker

Show draft in same format as above. The comment follows the §1a comment voice, ASD-STE100 writing standard and Length discipline. Apply dedup check — skip any action whose value is already set. Post only on `apply {id}`.

---

## Known Meta Bugs

The live list is fetched at session start (see Setup check). The table below is a
**fallback** used when the live query fails, and a reference for aliases. Prefer
the live `$META_BUGS` results during Step 4b.

| Alias | Bug | Area |
|---|---|---|
| *(none)* | 1015800 | EME / Encrypted Media Extensions |
| `dropped-frames` | 1416090 | Video frames dropped |
| *(none)* | 1752052 | Media Foundation Playback & CDM Support |
| `video-perf` | 1445470 | Video playback performance (CPU, GPU, power) |
| `webvtt` | 2010319 | WebVTT interop |
| `hw-ffvpx` | 1893427 | HW-accelerated video decoding through ffvpx |
| `wakelock` | 1665980 | Wake lock |
| `media-control` | 1572869 | Media session / OS media controls |
| `mfcdm` | 1806566 | Media Foundation CDM / PlayReady on Windows |
| `autoplay` | 2023365 | Autoplay issues |
| *(none)* | 1790066 | Twitter / X audio/video issues |
| *(none)* | 1904915 | YouTube playback issues |
| *(none)* | 1954546 | Twitch audio/video freezes/stutters |
| *(none)* | 1770250 | Reddit media playback issues |
| *(none)* | 1997593 | Bluesky media issues |
| *(none)* | 1951155 | Audio crackling / chipping |
| *(none)* | 2011679 | Bluetooth device audio/video issues |
| *(none)* | 1676924 | 4K+ video frame drops |
| *(none)* | 1902427 | HDR video playback on Windows |
| *(none)* | 1610199 | Linux VAAPI / ffmpeg video playback |
| *(none)* | 1766429 | Linux playback meta |
| *(none)* | 1648826 | AArch64 macOS media support |
| *(none)* | 1452683 | AV1 playback support |
| *(none)* | 1422891 | MKV / Matroska container support |
| *(none)* | 1884199 | Video startup perf / time to first frame |
| *(none)* | 1746557 | WebCodecs API implementation |
| *(none)* | 2023379 | Media-related sleep/wake issues |
| *(none)* | 2026773 | Remove AudioChannelService / AudioChannelAgent |

Also check the meta bug's open dependency list for existing duplicates of the new bug.

---

## Media Log Instructions

**For audio / video / performance bugs, the media-log capture is the single most useful
diagnostic — make it the FIRST item in "Next Steps"**, with the concrete steps spelled
out (not a vague "use the media preset" line). The only exception: if high-risk `media.*`
prefs were found (see the high-risk-prefs step), lead with the pref reset + restart and
make the capture the **next** item ("If the problem continues after the reset, capture…").
Do not bury the capture as the last bullet.

The capture is driven from `about:logging` using the **"Logging to the Firefox Profiler"**
output mode — it produces a **Firefox Profiler profile that the reporter uploads, and they
give us the share URL**. It is **NOT** a `.moz_log` file, and do **not** send the reporter
to profiler.firefox.com directly to start it — it is started from `about:logging` with the
right preset. Always use an inline hyperlink on the words "instruction video" — never
reference-style `[N]` footnotes. Spell out the steps:

> Please capture a profile:
>
> 1. Open `about:logging`.
> 2. On the **Logging presets** tab, choose the **"Media playback"** preset.
> 3. Under **Logging output**, select **"Logging to the Firefox Profiler"**.
> 4. Click **Start Logging**.
> 5. Reload the page. Then do the steps that show the problem.
> 6. Click **Stop Logging**. The profile opens in the Firefox Profiler.
> 7. Click **Upload Local Profile**. This is the share button.
> 8. Copy the share URL. Add it to this bug.
>
> The [instruction video](https://www.loom.com/share/24ea3a8e3a054c478de94643a0ea8620?sid=87b0ffaa-c4ea-43ce-8107-639f24b747a8)
> shows these steps. If the profile or the media content is private, send it to
> media-alerts@mozilla.com instead.

The steps are numbered, one instruction each, and in the imperative, because many
reporters do not read English as a first language. Keep that shape. Do not collapse
them back into a paragraph, and do not add a dash as an aside.

Use the **Graphics** preset (same flow) instead of / in addition to **Media playback** when
the issue is in the GPU/compositor/overlay path rather than playback. When a pref reset /
workaround precedes the capture (the high-risk-prefs case), prefix it with "If the problem
continues after the reset, …".
