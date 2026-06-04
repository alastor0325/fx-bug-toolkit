---
name: analyze-profile
description: Analyze a Firefox Profiler capture (share.firefox.dev or profiler.firefox.com/public links) for performance and media-pipeline issues, producing a structured findings report consumed by bug-start and triage. Triggers on "analyze profile", "analyze this profile", "/analyze-profile", or a Firefox Profiler URL.
argument-hint: <profiler-url>
allowed-tools: [Bash, Read, WebFetch]
---

# /analyze-profile — Firefox Profiler Analysis

Analyze a Firefox Profiler capture for media pipeline issues. Produces a
structured findings report consumed by `/triage`, `/bug-start`, and other skills.

**Invocation**: `/analyze-profile <url>`

Where `<url>` is a `share.firefox.dev/*` or `profiler.firefox.com/public/*` link.

---

## ⚠️ Rules for callers

**All skills that encounter a Firefox Profiler URL MUST invoke this skill instead
of running `profiler-cli` directly.** Do not inline profiler-cli commands in triage,
bug-start, or any other skill. This skill is the single source of truth for profile
analysis.

Do NOT use `WebFetch` on profiler URLs — they are JavaScript SPAs; WebFetch returns
only the CSS shell with no profile data.

---

## Step 1 — Run standard query set

`profiler-cli` is on your `PATH` (the `init` skill installs it via `npm link`).
Always invoke as:
```bash
profiler-cli <url> <flags>
```

Run all of the following in parallel:

```bash
# CPU hotspots
profiler-cli <url> --calltree 20

# Top markers by duration (IPC stalls, GC pauses, long tasks)
profiler-cli <url> --top-markers 20

# All media log markers (about:logging output)
profiler-cli <url> --log-markers
```

Then run targeted keyword searches based on the bug symptom:

| Symptom | Query |
|---|---|
| Buffering / stall | `--log-markers "waiting"` |
| Video freeze / black screen | `--log-markers "blank media"` |
| Audio desync / dropout | `--log-markers "Dropping audio"` |
| Audio clock fallback | `--log-markers "system clock"` |
| MDSM state transitions | `--log-markers "StateChange"` |
| Hardware decode failure | `--log-markers "DXVA"` |
| Codec / decoder errors | `--log-markers "NS_ERROR"` |
| HEVC / codec probe | `--log-markers "METADATA"` |
| MSE / demux issues | `--log-markers "MediaSource"` |

If the symptom is unknown or general, run all keyword queries above.

---

## Step 2 — Check ALL media threads

**Never analyze only one thread.** The media pipeline spans multiple thread types.
After running the queries above, explicitly account for every thread class:

| Thread pattern | Role |
|---|---|
| `GeckoMain` | Main thread — WMF init logs, global state dumps |
| `MediaDecoderStateMachine #N` | MDSM — playback state, buffering decisions |
| `MediaSupervisor #N` | GPU-process decoder supervision — DXVA init/failure |
| `MediaPDecoder #N` | Decoder threads — per-decoder decode loop |
| `AudioSink #N` | Audio output — clock, underruns |
| `BackgroundThreadPool #N` | Demux, network reads |

If findings appear only in `MediaDecoderStateMachine #1`, explicitly check whether
`MediaSupervisor`, `MediaPDecoder`, and `GeckoMain` threads contain relevant markers
before concluding. Missing a thread = missing the root cause.

---

## Step 3 — Look up wiki before pattern matching

**Wiki presence gate (REQUIRED when installed).** First check whether the wiki is set up:
```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo WIKI_INSTALLED
```
- If it prints `WIKI_INSTALLED`: you **MUST** consult the wiki before pattern matching, as below. Not optional.
- If it prints nothing: the wiki is not installed. Skip this step silently and go to Step 4 (pattern matching). Do **not** treat the absence as an error.

**Before interpreting raw output, consult the Firefox Knowledge Wiki for the components
involved.** Known facts there can identify the root cause immediately without reading code.

Based on the threads and log messages found in Step 2, look up relevant component pages:

```
/firefox-wiki:lookup D3D11DXVA2Manager     # DXVA failures, slot limit
/firefox-wiki:lookup WMFVideoMFTManager    # HW/SW fallback, codec-specific behavior
/firefox-wiki:lookup MediaCapabilities     # capability API accuracy
/firefox-wiki:lookup MediaDecoderStateMachine  # MDSM states, buffering
/firefox-wiki:lookup AudioSink             # clock, underruns
/firefox-wiki:lookup MoofParser            # tfdt, AAC encoder delay
/firefox-wiki:lookup TrackBuffersManager   # MSE gaps, inter-segment
```

Only look up pages relevant to what appeared in the output — do not look up all pages
unconditionally. If a wiki page explains the observed symptom, record it in the findings
report and skip the corresponding code-level investigation.

## Step 4 — Pattern match against known signatures

After collecting raw output, check for these known patterns:

### DXVA slot exhaustion
- Signal: `DXVA failure: D3D11:` repeating across `MediaSupervisor #N` threads, one per video
- Confirm: also check for `WMFInit DXVA Status` on `GeckoMain` showing `sDXVAEnabled`
- Meaning: `media.wmf.dxva.max-videos` (default 8) exceeded; feed-style site keeping too many decoders alive
- See: `components/D3D11DXVA2Manager.md` in the wiki

### No-SW-fallback codec failure
- Signal: `NS_ERROR_DOM_MEDIA_METADATA_ERR` or `NS_ERROR_DOM_MEDIA_FATAL_ERR` for HEVC/VP9/AV1/VP8
- Meaning: HW decode failed and no software fallback exists; site had to retry with different codec
- See: `components/WMFVideoMFTManager.md` in the wiki

### Video suspended (blank media)
- Signal: `blank media data decoder` repeating in MDSM thread
- Meaning: video element backgrounded or tab hidden; decoder suspended by `MediaDecoderStateMachine`

### Audio clock drift / loop gap
- Signal: `Dropping audio` markers in `AudioSink` thread
- Meaning: audio sink clock diverged from video PTS; often caused by loop boundary gap or MSE discontinuity

### Audio clock fallback
- Signal: `Fell back to system clock` in `AudioSinkWrapper`
- Meaning: audio device unavailable; clock accuracy degrades

### MSE stall / demux failure
- Signal: `NS_ERROR_DOM_MEDIA_WAITING_FOR_DATA` in MDSM thread
- Meaning: MSE buffer ran dry; network or append-rate issue

### IPC / GC stall on main thread
- Signal: long-duration markers (`> 50ms`) in `--top-markers` output on `GeckoMain`
- Meaning: main thread blocked; can delay media clock ticks and cause A/V desync

### MDSM buffering state
- Signal: `StateChange: DECODING → BUFFERING` without subsequent `BUFFERING → DECODING` within a few seconds
- Meaning: decoder starved; look for network issue or demux failure upstream

---

## Step 5 — Produce structured findings report

Output the report in this format so callers can consume it directly:

```
─── Profile Analysis: <url> ──────────────────────────────────────
Threads checked: GeckoMain, MediaDecoderStateMachine #1–N,
                 MediaSupervisor #1–N, MediaPDecoder #1–N, AudioSink #1–N

Findings:
  ✓ <pattern name>: <what was observed, frequency, thread>
  ✗ <pattern name>: not detected
  …

Key log entries:
  [t=Xms] <ThreadName>: <message>
  …

Errors:
  [t=Xms] <ThreadName>: <NS_ERROR_* or HRESULT>
  …

Assessment:
  Severity:   [Critical / High / Medium / Low / None]
  Root cause: [Identified / Suspected / Unknown]
  Summary:    <2-3 sentences: what the profile shows, what it means for the bug>
  Sufficient for §1b? [Yes / No — reason]
──────────────────────────────────────────────────────────────────
```

**Sufficient for §1b** means: the profile alone (possibly combined with existing
bug context) gives enough evidence to identify the root cause and start a fix,
without needing additional data from the reporter.

---

## Step 6 — Record new patterns in the wiki

**Wiki presence gate.** This step applies only when the wiki is installed:
```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo WIKI_INSTALLED
```
If that prints nothing, skip this step silently — there is no wiki to record into. If it prints `WIKI_INSTALLED`, proceed below.

If the profile revealed a symptom or root cause that is **not already documented** in
the wiki pages consulted in Step 3, add it using `/firefox-wiki:add`. Do not add facts
already present in the wiki — only genuinely new findings with a verifiable source
(profile URL + bug number).

---

## Notes for callers

- **triage (Step 2c)**: replace all inline `profiler-cli` invocations with
  `/analyze-profile <url>`. Use the "Sufficient for §1b?" field to decide §1a vs §1b.
- **bug-start (Step 2)**: replace the profiler fetch block with `/analyze-profile <url>`.
  Paste the full findings report into the investigation file under
  `## Code Analysis → Profile Analysis`.
- If profiler-cli fails (network error, URL expired, unsupported format): note
  `Profile: inaccessible — <reason>` and continue without it. Do not block on it.
