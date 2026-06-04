# Triage Components

This is the **single source of truth** for which Bugzilla components `/triage`
covers. The skill reads this list at setup time; `bugzilla-cli fetch` and the
meta-bug search are both driven from it (the CLI no longer hardcodes the set —
the caller passes it).

## Default components

Out of the box, `/triage` triages bugs in these eight Firefox Audio/Video
components:

| Component | Area |
|---|---|
| `Audio/Video` | General A/V |
| `Audio/Video: cubeb` | Audio backend (cubeb) |
| `Audio/Video: GMP` | Gecko Media Plugins / EME / CDM |
| `Audio/Video: MediaStreamGraph` | MediaStreamGraph / real-time audio graph |
| `Audio/Video: Playback` | Media playback pipeline |
| `Audio/Video: Recording` | getUserMedia / MediaRecorder |
| `Web Audio` | Web Audio API |
| `Audio/Video: Web Codecs` | WebCodecs API |

## Overriding the set — `$TRIAGE_COMPONENTS`

The default is **optional to change**. To triage a different set (a narrower
subset, or additional components), set the `$TRIAGE_COMPONENTS` environment
variable to a **`;`-separated** list of exact Bugzilla component names:

```sh
export TRIAGE_COMPONENTS="Audio/Video: Playback;Audio/Video: GMP;Web Audio"
```

Rules:

- **Exact names.** Each entry must match the Bugzilla component name exactly
  (case, spaces, and the `Audio/Video: ` prefix all matter).
- **Separator is `;`.** Component names contain spaces, `/`, and `:`, but never
  `;`, so a semicolon is an unambiguous delimiter.
- **Unset = the default eight above.** Leaving `$TRIAGE_COMPONENTS` unset (the
  common case) triages exactly the default set.
- **Narrowing works everywhere.** A subset of A/V components is honored by the
  full `/triage` run (fetch + meta search + scope filter) and by
  `/triage <id>`.
- **Adding non-A/V components** (e.g. a Graphics component) is honored by
  `bugzilla-cli fetch --component …`, the meta-bug search, and the scope filter,
  so a full `/triage` run will pull and triage them.

The first time you run `/triage`, the skill shows this default list and asks
whether to keep it or customize it, then persists your choice to
`~/.fx-bug-toolkit.env.sh` (see the skill's **Setup check**).
