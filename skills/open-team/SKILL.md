---
name: open-team
description: Open the Firefox review-team dashboards (firefox-review-stats) — per-team review-load distribution, bottleneck/sole-reviewer risk, wait queues, and an LLM-summarized digest of what each component shipped recently. Opens the live, weekly-refreshed GitHub Pages site in the browser — the landing page by default, or a specific team when one is named. Triggers on "/open-team", "open the team dashboard", "team review dashboard", "review stats", "review load", "playback/webrtc/gfx review stats".
argument-hint: "[team] (playback | webrtc | gfx; omit for the landing page)"
allowed-tools: [Bash]
---

# /open-team — open the Firefox review-team dashboards

[firefox-review-stats](https://github.com/alastor0325/firefox-review-stats) publishes
weekly per-team dashboards for Firefox review groups — within-group review-load
distribution, concentration/sole-reviewer risk, a per-revision wait queue, and a
plain-language, LLM-summarized digest of what each component shipped recently.

It's hosted live on **GitHub Pages** and refreshed every Monday by a GitHub Action, so
this skill simply **opens the published site** in the browser. There is nothing to
install, no local server, and no port — it's an external website, always current.

## Step 1 — Resolve which page to open

Open the **landing page** (the team picker) by default. Open a **specific team's page
only when the user explicitly names a team or its review group** — never guess one from
the surrounding context.

Base URL: `https://alastor0325.github.io/firefox-review-stats/`

| If the user names… | Open |
|---|---|
| nothing / "team dashboard" / "review stats" / "review load" | the landing page (base URL) |
| `playback` · `media-playback-reviewers` · dom/media · A/V · audio/video · media | `…/playback/` |
| `webrtc` · `webrtc-reviewers` · web rtc | `…/webrtc/` |
| `gfx` · `gfx-reviewers` · graphics · image · canvas · webgpu | `…/gfx/` |

If they name a team that isn't in this list, open the **landing page** and tell them the
registered teams are `playback`, `webrtc`, and `gfx`.

## Step 2 — Open it

Print the URL (so the user always has it even if a browser can't open here), then open it
in the default browser. Cross-platform — macOS / Linux / Windows (git-bash):

```bash
URL="https://alastor0325.github.io/firefox-review-stats/"   # append "<slug>/" for a team, e.g. ".../playback/"
echo "Opening $URL"
case "$(uname -s)" in
  Darwin) open "$URL" ;;
  Linux)  xdg-open "$URL" >/dev/null 2>&1 & ;;
  MINGW*|MSYS*|CYGWIN*) start "" "$URL" ;;
  *) echo "Open it manually: $URL" ;;
esac
```

It's a public website — no local data, no install, no server. Deep-link states are encoded
in the URL hash, so you can target a view directly when asked: append `#queue` (wait
queue), `#recent/1w` (this week's changes), `#team/3m` (3-month rollup), `#member`, etc.
— e.g. `…/playback/#queue`.
