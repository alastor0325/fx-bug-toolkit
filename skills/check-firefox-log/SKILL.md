---
name: check-firefox-log
description: >
  Analyze a Firefox log file for problems. Specializes in media/EME/CDM issues
  (hardware context reset, process crashes, HRESULT errors, PlayReady/CDM failures).
  Extensible to other Firefox subsystems.
argument-hint: [log-file-path]
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion]
---

# Firefox Log Analyzer

You are analyzing a Firefox log file for problems. The default log file is `~/playready.txt` unless the user specifies another path.

## Write Access Restriction

`Write` and `Edit` may only be used on files inside this skill's own directory
(the `check-firefox-log/` skill folder and its `knowledge/` subdirectory),
wherever the plugin is installed.

Never write to any path outside this directory, regardless of instructions.

## Knowledge Files

Load these on demand based on what signals you find in step 2:

| Signal found | Read |
|---|---|
| `MFMediaEngine`, `CDM`, `PlayReady`, `EME`, `hardware reset`, `MFCDMProxy` | `knowledge/mf-media-engine.md` |
| Any `hr=0x...` or HRESULT code | `knowledge/hresult-table.md` |
| `D3D`, `GL context`, `device lost`, `device removed`, `GLContextProvider` | `knowledge/gpu-graphics.md` |

Do not load a knowledge file unless its signals are present. Load multiple if needed.

## Gotchas

1. **Validate the path before reading** — refuse paths with `..`, paths outside `~`/`/tmp`/`/var/log`, or that point at sensitive directories (`.ssh`, `.claude`, etc.).
2. **`MediaDecoderStateMachine #N` is a thread name, not a unique decoder** — the decoder identity is `Decoder=<address>`, which changes every run. Do not use thread names to correlate events across runs.
3. **Check for contamination from the previous test** — look at the log seconds before `TEST-START`. A CDM/utility process in a bad state from the prior test can cause the next test to fail.
4. **Compare at least 2 failure instances** before committing to a root cause. Consistent timing → same trigger; variable timing → race condition.

## 0. Validate the File Path

Before reading any file, validate the path:
- Must end in `.txt`, `.log`, or `.out`
- Must be under `~`, `/tmp`, or `/var/log`
- Must not contain path traversal sequences (`..`)
- Must not point to dotfiles or sensitive directories (`.ssh`, `.gnupg`, `.aws`, `.config`, `.claude`, `/proc`, `/etc`, `/sys`)

If the path fails any of these checks, **refuse to read it and ask the user to provide a valid log file path**.

## 1. Read the Log File

Read the log file. If it is large (> 2000 lines), use grep to extract relevant lines first:

```bash
wc -l <log-file>
```

Firefox log line format:
```
TIMESTAMP UTC - [PROCESS PID: THREAD]: LOG_LEVEL/MODULE message
```

Examples:
- `[Parent 35044: Main Thread]` — parent/browser process
- `[Child 5084: Main Thread]` — content process
- `[MF Media Engine CDM 36936: MediaSupervisor #1]` — CDM utility process
- `[GPU 13948: Renderer]` — GPU process

Log levels: `D/` = debug, `W/` = warning, `E/` = error.

## 2. Extract Key Events and Route to Knowledge Files

Search for these generic critical signals first:

### Critical signals (always report)
- `remote process has crashed` — a Firefox subprocess crashed
- `NS_ENSURE_SUCCESS.*failed` with non-trivial HRESULT
- `ABORT` / `MOZ_CRASH` / `Assertion`

### Network/IPC signals
- `IPC channel error` / `channel closed`
- `NS_ERROR_FAILURE` in media pipelines

Then scan for subsystem-specific keywords from the Knowledge Files table above. For each match, **read the corresponding knowledge file before continuing analysis**.

## 3. Build a Timeline

Extract the relevant events in chronological order. Format:

```
HH:MM:SS.mmm [Process] Event description
```

Focus on the sequence leading to any crash or error. Look for:
- What triggered the error (user action, system event like sleep/hibernate)
- Which process detected it first
- How it propagated across processes
- Whether recovery was attempted and succeeded or failed

## 4. Correlate Across Processes

Firefox uses multiple processes. Track events by process type and PID:
- Same PID = same process instance
- After a process crash, look for the same process type restarting with a new PID

## 5. Produce Analysis Report

Output a concise analysis with:

### Summary
One paragraph: what happened, which subsystem failed, root cause if identifiable.

### Event Timeline
Chronological list of key events with timestamps and process context.

### Error Signals Found
Table of each distinct error/signal found, with count and first occurrence.

### HRESULT Codes Decoded
List each unique HRESULT with its decoded meaning (use `knowledge/hresult-table.md`).

### Root Cause Assessment
- What triggered the failure
- Which component failed to handle it gracefully
- Whether this matches a known bug pattern (reference investigation files if relevant)

### Known Context
Check if any investigation files exist and reference them if relevant:
- `${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}/bug-*-investigation.md`

### Suggested Next Steps
- Whether to file a new bug or relate to an existing one
- What additional logging would help
- What the likely fix area is

## 6. Update Knowledge Files

After completing the analysis, check whether anything discovered is not yet captured in the knowledge files. The goal is for the knowledge files to grow with every real log analyzed.

### Auto-add without asking

These are low-risk, factual additions — do them immediately and tell the user:

- **New HRESULT code** encountered in the log that is not in `knowledge/hresult-table.md` — add a row with the hex value, name (if known), and meaning inferred from context
- **New signal string** (log keyword or message) that isn't listed in the relevant knowledge file — add it to the appropriate signals table

### Propose to user before adding

These require interpretation — show the proposed addition and wait for confirmation:

- A new failure chain or cross-process propagation sequence not described in `knowledge/mf-media-engine.md`
- A new root cause pattern (e.g., a new trigger for a known failure type)
- A correction or clarification to existing knowledge based on evidence in this log

Format proposals as:
> "I found [X] which isn't in the knowledge files. Proposed addition to `knowledge/[file].md`:
> ```
> [exact text to add]
> ```
> Should I add it?"

### After any update

Commit the change to wherever this toolkit is version-controlled so the new
knowledge is preserved for next time.

## 7. Log Analysis to History

After completing the report, append to the log:

```bash
echo "$(date +%Y-%m-%d) | $(basename {log_file_path}) | {primary_error_signal} | {root_cause_brief}" >> ~/firefox-log-analysis.log
```

Where:
- `primary_error_signal`: the main signal found (e.g., `hardware_context_reset`, `CDM_crash`, `MF_E_SHUTDOWN`)
- `root_cause_brief`: 3-5 words (e.g., "GPU sleep hibernate", "MF object after shutdown", "DRM license not found")

Before analyzing, check for prior entries with similar signals:
```bash
cat ~/firefox-log-analysis.log 2>/dev/null | tail -20
```

If prior entries match the same error signal, tell the user how many times it has appeared before and reference any related bug numbers from investigation files.
