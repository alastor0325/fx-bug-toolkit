---
name: check-firefox-log
description: >
  Analyze a Firefox log file for problems. Specializes in media/EME/CDM issues
  (hardware context reset, process crashes, HRESULT errors, PlayReady/CDM failures).
  Extensible to other Firefox subsystems.
argument-hint: [log-file-path]
allowed-tools: [Read, Bash, Grep, Glob, AskUserQuestion]
---

# Firefox Log Analyzer

You are analyzing a Firefox log file for problems. The log file is given as the
skill argument; if the user didn't specify one, ask which file to analyze.

## Filesystem access

This skill is **read-only** with respect to your files — it never uses `Write`
or `Edit`. New knowledge goes to the shared wiki (§6, when present), never to
the bundled `knowledge/*.md` files. The only thing it writes is appending one
line to the log-analysis history (§7) via the shell.

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

## 6. Capture New Findings

The bundled `knowledge/*.md` files are a **read-only reference floor** that ships
with the plugin — this skill never edits them (in an installed plugin they are
managed/read-only and any local edit would be lost on update).

After completing the analysis, if you discovered something **not** already in the
bundled knowledge — a new HRESULT code, a new signal string, a new failure chain
or cross-process propagation sequence, a new root-cause pattern, or a correction
to existing knowledge — capture it so it compounds for next time:

```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo WIKI_INSTALLED
```

- **If it prints `WIKI_INSTALLED`:** propose adding the finding to the shared
  wiki via `/firefox-wiki:add` (it's shared, versioned, and compounds across the
  team). Show the proposed addition and let the user confirm — e.g.:
  > "I found [X], not in the bundled knowledge. Proposed wiki addition: …"
- **If it does not print (no wiki):** surface the finding in the report under
  *Suggested Next Steps* — e.g. "New: [X] — not in the bundled knowledge;
  consider contributing it to the team wiki or upstream to fx-bug-toolkit." Do
  **not** write it into the bundled files.

## 7. Log Analysis to History

The history file is `$FX_LOG_ANALYSIS_LOG` if set, otherwise the default
`~/.fx-bug-toolkit/log-analysis.log`. After completing the report, append to it
(creating the parent dir if needed):

```bash
HIST="${FX_LOG_ANALYSIS_LOG:-$HOME/.fx-bug-toolkit/log-analysis.log}"
mkdir -p "$(dirname "$HIST")"
echo "$(date +%Y-%m-%d) | $(basename {log_file_path}) | {primary_error_signal} | {root_cause_brief}" >> "$HIST"
```

Where:
- `primary_error_signal`: the main signal found (e.g., `hardware_context_reset`, `CDM_crash`, `MF_E_SHUTDOWN`)
- `root_cause_brief`: 3-5 words (e.g., "GPU sleep hibernate", "MF object after shutdown", "DRM license not found")

Before analyzing, check for prior entries with similar signals:
```bash
tail -20 "${FX_LOG_ANALYSIS_LOG:-$HOME/.fx-bug-toolkit/log-analysis.log}" 2>/dev/null
```

If prior entries match the same error signal, tell the user how many times it has appeared before and reference any related bug numbers from investigation files.
