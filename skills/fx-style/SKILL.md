---
name: fx-style
description: >
  The fx-bug-toolkit visual design system — the single style baseline every
  local web UI in this project (the investigation viewer, the personal
  dashboard, any future page) must follow. Apply BEFORE building or restyling
  any HTML/CSS surface here, and when reviewing UI for consistency. Triggers on
  "/fx-style", "style guide", "design system", "make it match the viewer",
  "theme", "consistent look", building a new viewer/dashboard page.
---

# fx-bug-toolkit design system

One look across the whole toolkit. Every page links the shared stylesheet and
builds on its tokens — no per-page palettes, no re-declared primitives, no drift.

## The rule

**Every local web UI in this repo links `/theme.css` and extends it — never
forks it.** The canonical stylesheet is [`assets/theme.css`](../../assets/theme.css)
at the repo root; each launcher's `serve.py` serves it at the absolute URL
`/theme.css` (see the `/theme.css` route in `viewer/serve.py`). So a page does:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/theme.css">
<style>/* only this page's OWN layout goes here */</style>
```

The IBM Plex font `<link>` stays in each page's `<head>` (it can't be pulled in
reliably from an `@import`). Everything else visual comes from `/theme.css`.

## What lives in the theme (use it, don't redefine it)

- **Design tokens** (CSS custom properties) — always reference these, never
  hardcode a hex value:
  - Surfaces, back-to-front: `--bg` `--rail` `--panel` `--raised`; borders
    `--line` (`--line-soft` for quieter divisions).
  - Text: `--ink` (primary) · `--dim` (secondary) · `--faint` (tertiary/labels).
  - **Accent: `--amber`** is *the* primary accent (selection, focus, active,
    the one thing your eye should land on). `--amber-dim` for hover borders,
    `--amber-wash` for its translucent fill. Use amber sparingly — it only reads
    as "important" because most of the UI is neutral.
  - Semantics: `--cyan` (links / paths), `--green` (good/low), `--red`
    (bad/high/danger), `--blue` (informational).
  - Type: `--mono` (IBM Plex Mono) for chrome, ids, labels, metadata;
    `--sans` (IBM Plex Sans) for prose/titles.
- **Page backdrop** — the faint fractal-noise grain + top amber radial glow
  (`body::before` / `body::after`). Free on every page; don't reinvent it.
- **Typography base** — `body` font, size (14px), line-height, antialiasing.
- **Form controls** — `.search` (with its `⌕` glyph), `select`, `.sortbtn`,
  `.count`. Reuse these classes for filters/search rather than styling inputs
  anew.
- **The chip** — `.chip` is the universal tag primitive: mono, uppercase,
  10.5px, thin border, pill-ish. Add ONE semantic-color modifier for meaning:
  `.chip.amber` `.chip.cyan` `.chip.green` `.chip.blue` `.chip.red`, plus
  `.chip.security` (filled, high-attention). A page's own categories extend
  `.chip` locally (e.g. the viewer's `.chip.depth-deep`, `.chip.folder`).
- **Scrollbars** and **`<kbd>`** — themed globally.
- **Brand mark** — `.brand` (uppercase mono wordmark, amber) for the top-bar
  title, with a dimmed `· fx-bug-toolkit` suffix.

## Recurring patterns (match these)

- **Top bar**: fixed-height (58px) row, `border-bottom:1px solid var(--line)`,
  subtle vertical gradient, `.brand` at the left, controls trailing with
  `margin-left:auto`.
- **Section / panel**: `background:var(--panel)` or `--raised`, `1px solid
  var(--line)` border, **radius 9–10px**. Small radii (5–7px) for chips,
  inputs, buttons.
- **Section label**: mono, uppercase, ~10.5px, `letter-spacing:.14em`, colored
  `--faint` (or `--amber-dim` when it heads an accented block). This is how the
  viewer labels "root cause" / "affected files" — reuse it for any section
  heading so parts read as clearly separated.
- **Selected / active**: `background:var(--amber-wash)` +
  `border-color:rgba(255,180,84,.30)`, often with a 3px amber left-edge bar.
- **Focus ring**: `box-shadow:0 0 0 3px var(--amber-wash)` +
  `border-color:var(--amber-dim)`. Keep it — never remove focus outlines.
- **Links**: `--cyan` with a faint underline that solidifies on hover; external
  links open in a new tab (`target="_blank" rel="noopener"`).
- **Motion**: short (`.12s–.24s`) transitions; a gentle `translateY` rise-in for
  list items is on-brand. Nothing bouncy or slow.

## Layout & density

The system fills the screen. **Use the viewport width — never strand content in a
narrow centered column with big empty gutters.**

- **Width.** Lay pages out full-bleed with *fluid side padding*
  `clamp(16px, 2.5vw, 36px)`. Chrome (top bar, tab bar) uses the **same** side
  padding as the content so left edges align. A `max-width` cap is allowed only to
  stop absurd line lengths on ultra-wide monitors, and then it must be **generous
  (~1600–1800px)** — never a tight 900–1100px column (that's the wasted-gutter
  smell this rule exists to kill).
- **Two layout patterns, both full-width:**
  1. **Master–detail** (the investigation viewer): a fixed-width rail +
     fluid detail that fills the rest — `grid-template-columns: var(--rail-w) 1fr`,
     full viewport height, panes scroll (not the page). Use when you browse one of
     many and read it in place.
  2. **Card grid** (the dashboard): a list of cards is a **responsive grid**, not
     a single column — `display:grid; grid-template-columns: repeat(auto-fill,
     minmax(<min>, 1fr)); gap:10px; align-items:start`. It becomes multi-column on
     wide screens and one column on narrow, with no wasted gutters. Pick a
     readable `min` (~460–520px). `align-items:start` so expanding one card grows
     only that card, not its row-mates.
- **Density matches the item's role.** Things the user *acts on* → prominent
  **cards** (brief, tags, buttons). Things the user *scans or references* →
  compact **one-line ledger rows** (id · a tag or two · trailing meta · truncated
  title). Big lists are always ledger rows (they fill width and stay scannable);
  small action sets are cards. Don't render a 100-item reference list as cards, and
  don't card-ify a backlog nobody triages item-by-item. Separate a section's
  signal (act) from its noise (reference) with a collapsed divider rather than a
  wall of equal-weight cards.
- **Spacing** is a small, consistent scale — card padding ~11–13px, gap between
  cards ~8–10px, ledger row padding ~6px, space between zones ~14–22px. Keep it
  dense and terminal-calm; don't pad regions out with large empty vertical space.
- **Sticky chrome:** top bar sticky at `top:0`; a secondary bar (tabs/filters)
  sticky directly beneath it. Content scrolls under both.
- **Responsive floor** (non-negotiable): usable down to mobile — grids collapse to
  one column, tab/filter bars wrap, and non-essential chrome (e.g. the user email)
  drops out on narrow. Visible keyboard focus; honor `prefers-reduced-motion`.

## Justify every UX change (reason, don't rearrange)

A layout/UX change ships only with a **reliable reason**. State three things, or
don't make the change:

1. **Problem** — the specific thing that's wrong, in the user's terms (e.g.
   "can't find the actionable item among 49 stale ones"), not a vibe.
2. **Mechanism** — *how* the change fixes that problem (the causal link), not just
   that it's different.
3. **Better-than-before** — why it beats the current layout for the user's job,
   and what it costs.

Guard against **rearrangement dressed up as a fix** — moving a control (e.g. tabs
top → side) does **not** reduce content density or help you find the important
item; those are different axes. If a change doesn't attack the stated problem via
its mechanism, cut it.

**"Uses the width" is not automatic.** Horizontal space is only *used* if it
carries content or controls the user actually needs there. A side rail holding a
few nav items is a tall, mostly-empty column — that wastes space just like empty
gutters do. A rail earns its width only when it holds **persistently useful**
controls (filters, search, summary you consult constantly); otherwise keep the
control at the top and give the width to content. Fill width with *structured
content* (e.g. a row that splits into brief + metadata), not with chrome.

## Using `frontend-design` under this system

You may borrow *craft* from the general `frontend-design` skill — information
hierarchy, spacing discipline, layout ideas, screenshot self-critique. But it is
**subordinate to this system**: it must not introduce a new palette, new
typefaces, a second accent, light backgrounds, or a distinct per-page "identity."
Every color, font, and radius still comes from `/theme.css`; every layout follows
the rules above. When `frontend-design`'s "take a distinctive risk" instinct
conflicts with toolkit consistency, **this skill wins.**

## Do / don't

- **Do** reference tokens; **don't** hardcode colors, fonts, or radii.
- **Do** extend `.chip` and the shared controls; **don't** re-declare `:root`,
  the backdrop, scrollbars, or `.chip` base in a page.
- **Do** give each distinct part its own labeled, bordered section with a
  visible header + count; **don't** merge unrelated data into one flat list.
- **Do** keep amber scarce and intentional; **don't** paint whole regions amber.
- **Do** keep it dark, dense, terminal-adjacent, calm; **don't** introduce a
  second accent hue, light backgrounds, drop shadows beyond the existing
  dropdown, or decorative gradients.

## Changing the system

Edit `assets/theme.css` (the source of truth) — every page updates at once. A
token rename or component change is a shipped-viewer change: follow the
fx-bug-toolkit Dev Loop (run the viewer E2Es, `/sync-tutorial`, release). Adding
a genuinely new shared primitive goes in the theme; a one-off that only one page
needs stays inline in that page.
