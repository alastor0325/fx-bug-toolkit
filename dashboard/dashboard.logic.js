/* Pure, DOM-free logic for the personal dashboard (v3 cards). Unit-tested via
 * `node --test` (dashboard/tests/dashboard.logic.test.js). The HTML wires these
 * into the DOM; anything testable lives here, not inline.
 *
 * The page only DISPLAYS what the generate skill produced (data.json) and its
 * progress (status.json). Card buttons don't call Claude — they POST an action to
 * the local serve.py, which appends it to a queue file the drain skill processes. */

// The three sections, in display order, with a /theme.css accent color each.
const SECTIONS = [
  { key: "needinfos", label: "Needinfos",            accent: "amber", empty: "No open needinfos — you're clear." },
  { key: "reviews",   label: "Review requests",      accent: "cyan",  empty: "No reviews waiting on you." },
  { key: "my_bugs",   label: "My work",              accent: "blue",  empty: "Nothing in progress." },
];


// The section tabs in the user's saved drag order. `saved` is an array of section
// keys; unknown keys are ignored and any section missing from it is appended in
// the default SECTIONS order — so stale storage or a newly added section never
// drops a tab. Pure (new array).
function orderedSections(saved) {
  const byKey = new Map(SECTIONS.map(s => [s.key, s]));
  const out = [], seen = new Set();
  for (const k of saved || []) {
    if (byKey.has(k) && !seen.has(k)) { out.push(byKey.get(k)); seen.add(k); }
  }
  for (const s of SECTIONS) if (!seen.has(s.key)) out.push(s);
  return out;
}

// Reorder a key array by moving `from` to sit before (or after, if `after`) the
// `to` key — the drag-drop drop result. An unknown `to` sends `from` to the end.
// Pure (new array).
function moveKey(keys, from, to, after) {
  const arr = (keys || []).filter(k => k !== from);
  let i = arr.indexOf(to);
  if (i < 0) { arr.push(from); return arr; }
  if (after) i += 1;
  arr.splice(i, 0, from);
  return arr;
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Map a tag's `kind` to a chip color class ("" = neutral). Color is reserved for
// SIGNAL so it actually means something: red = danger (security filled + crash +
// memory-safety), amber = attention (regression, high severity). Component and
// every descriptive/enrichment tag stay neutral grey — context, not noise.
function tagClass(kind) {
  return ({
    security: "security",       // filled red — highest attention
    warn: "red",               // crash → danger
    danger: "red", "memory-safety": "red",
    regression: "amber",       // attention
    severity: "amber",
  })[kind] || "";
}

// Rank a tag by how much it wants attention (filled danger > danger > attention >
// neutral) — used to keep the important chips when we cap the count.
function tagRank(kind) {
  const c = tagClass(kind);
  return c === "security" ? 3 : c === "red" ? 2 : c ? 1 : 0;
}

// The chips a card actually shows: dedup by text (kills the "REGRESSION ×2"
// dupes), signal-first so a cap never drops a security/regression chip, then
// capped so a card stays scannable. Pure (new array).
function displayTags(tags, cap) {
  const seen = new Set(), out = [];
  for (const t of tags || []) {
    const key = String((t && t.text) || "").toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key); out.push(t);
  }
  out.sort((a, b) => tagRank(b.kind) - tagRank(a.kind));
  return out.slice(0, Number(cap) || 3);
}

// Coarse human age from a day count.
function waitingLabel(days) {
  const d = Math.max(0, Math.floor(Number(days) || 0));
  if (d === 0) return "today";
  if (d < 7) return d + "d";
  if (d < 30) return Math.floor(d / 7) + "w";
  return Math.floor(d / 30) + "mo";
}

// Patch-status pill for a "my work" item: {label, cls}. Color carries the state —
// red = ball in MY court (r-), green = ready to land (r+), cyan = waiting on the
// reviewer, blue = drafted (wip).
function patchStatusMeta(status) {
  return ({
    "needs-revision":  { label: "r- revise",  cls: "red" },
    accepted:          { label: "r+ land it", cls: "green" },
    "in-review":       { label: "in review",  cls: "cyan" },
    wip:               { label: "wip",        cls: "blue" },
    landed:            { label: "landed",     cls: "" },
    none:              { label: "no patch",   cls: "" },
  })[status] || { label: status || "unknown", cls: "" };
}

// The action buttons a card offers, given its type + item. NI always offers
// draft-reply + bug-investigate, plus run-/bug-start ONLY when the generation
// gate marked it solvable. Reviews offer run-/review. "my bugs" are display-only
// in the MVP (no buttons). Each: {action, label}.
function actionsForItem(item) {
  if (!item) return [];
  if (item.type === "ni") {
    const a = [
      { action: "draft-reply", label: "Draft reply" },
      { action: "bug-investigate", label: "Bug investigate" },
    ];
    if (item.solvable) a.push({ action: "bug-start", label: "Looks ready → run /bug-start" });
    return a;
  }
  if (item.type === "review") return [{ action: "review", label: "Run /review" }];
  return [];
}

// Stable key for pairing a queued request / a drain result with a card+action.
function actionKey(id, action) {
  return `${id}::${action}`;
}

// A queue entry the page POSTs when a button is clicked (the caller stamps `ts`,
// since Date.now() isn't available/deterministic here).
function buildQueueEntry(item, action) {
  return { id: item.id, type: item.type, action, title: item.title, url: item.url, status: "queued" };
}

// What the page should render, from data.json (or null) + status.json (or null):
//   - processing: first run, nothing generated yet → full-page spinner
//   - empty:      generation done but no items at all
//   - ready:      show the board; `analyzing` true = a regeneration is running
//                 (show the last board + a subtle indicator)
function viewMode(data, status) {
  const running = !!status && status.state === "running";
  if (!data || !data.sections) return { mode: "processing", analyzing: running };
  if (totalItems(data) === 0 && !running) return { mode: "empty", analyzing: false };
  return { mode: "ready", analyzing: running };
}

// Per-section ordering. Needinfos are sorted by date, controlled by `order`:
// "newer" (default) = most recent first (fewest days waited on top); "older" =
// oldest first. Other sections keep collector order. Pure (returns a new array).
function sortForSection(key, items, order) {
  const arr = (items || []).slice();
  if (key === "needinfos") {
    const dir = order === "older" ? -1 : 1;   // default "newer" = ascending waiting_days
    arr.sort((a, b) => dir * ((Number(a.waiting_days) || 0) - (Number(b.waiting_days) || 0)));
  }
  return arr;
}

// Split a section's items into the "act" set (analyzed — has a brief, shown as
// prominent cards) and the "rest" (not analyzed — shown as a demoted ledger).
function analyzedSplit(items) {
  const act = [], rest = [];
  for (const it of items || []) (it && it.brief ? act : rest).push(it);
  return { act, rest };
}

// Display metadata for a queued action: {label, accent (a /theme.css chip color)}.
const ACTION_META = {
  "draft-reply":     { label: "Draft reply",    accent: "amber" },
  "bug-investigate": { label: "Bug investigate", accent: "cyan" },
  "bug-start":       { label: "run /bug-start",  accent: "green" },
  "review":          { label: "Run /review",     accent: "cyan" },
};
function actionMeta(action) {
  return ACTION_META[action] || { label: action || "action", accent: "" };
}

// Days within which a bug counts as actively worked; past this a patch is parked
// and drops to the backlog no matter its status.
const ACTIVE_DAYS = 30;

// Split "my work" (open bugs) into ACTIVE zones + a parked BACKLOG. The axis that
// matters is active-vs-backlog, not raw patch status: a bug I've touched within
// `activeDays` is active work (even a just-filed bug with no patch yet), while an
// accepted patch just sitting is backlog (not going to land it) and a long-idle
// bug is backlog no matter its status.
//   revise  — needs-revision, active: ball in my court → act (r-)
//   waiting — in-review, active: waiting on the reviewer
//   wip     — draft, active: I'm still working it
//   todo    — no patch yet, active: assigned + recently touched, not started
//   backlog — accepted-but-parked (r+, any age), or anything gone dormant
//             (untouched > activeDays). Collapsed, low-signal.
// Pure.
function myBugsZones(items, activeDays) {
  const win = Number(activeDays) || ACTIVE_DAYS;
  const z = { revise: [], waiting: [], wip: [], todo: [], backlog: [] };
  for (const b of items || []) {
    const s = b && b.patch_status;
    const active = (Number(b.last_activity_days) || 0) <= win;
    if (s === "accepted") z.backlog.push(b);                 // parked r+ — not landing it
    else if (active && s === "needs-revision") z.revise.push(b);
    else if (active && s === "in-review") z.waiting.push(b);
    else if (active && s === "wip") z.wip.push(b);
    else if (active && (s === "none" || !s)) z.todo.push(b);
    else z.backlog.push(b);                                  // dormant / landed / unknown
  }
  return z;
}

// The three purpose-driven My-work sections the user places bugs into. Focus is
// deliberately small (soft cap); Next is the queue; Backlog is everything parked.
const MYWORK_SECTIONS = [
  { key: "focus",   label: "Focus",   hint: "Working these now." },
  { key: "next",    label: "Next",    hint: "Queued — pull up when Focus clears." },
  { key: "backlog", label: "Backlog", hint: "Parked. Not now." },
];
const FOCUS_CAP = 5;   // soft cap — if Focus grows past this, its count warns

// Default section for a bug the user hasn't placed, from its patch state alone —
// deliberately dumb + predictable (no recency magic): a patch in the review
// process → focus; a patch not yet in review → next; anything else → backlog.
function defaultSection(bug) {
  const s = bug && bug.patch_status;
  if (s === "in-review" || s === "needs-revision") return "focus";
  if (s === "wip") return "next";
  return "backlog";
}

// Where a bug actually sits: the user's manual placement wins (and persists),
// else the default. Pure.
function sectionOf(bug, placements) {
  const p = (placements || {})[String(bug && bug.id)];
  return (p && MYWORK_SECTIONS.some(s => s.key === p)) ? p : defaultSection(bug);
}

// Group my_bugs into {focus, next, backlog} by sectionOf. Pure (new arrays).
function groupBySection(items, placements) {
  const g = { focus: [], next: [], backlog: [] };
  for (const b of items || []) g[sectionOf(b, placements)].push(b);
  return g;
}

// If a bug's manual placement disagrees with where its status would default it,
// return that default section (the "↳ suggests X" drift hint + reset affordance);
// "" when aligned or unplaced. Never auto-moves — just surfaces the mismatch. Pure.
function driftHint(bug, placements) {
  const placed = (placements || {})[String(bug && bug.id)];
  if (!placed) return "";
  const def = defaultSection(bug);
  return placed === def ? "" : def;
}

// Sort bugs most-recently-active first (smallest last_activity_days on top), so
// the bugs I'm actually moving stay at the top. Pure (new array).
function byRecency(items) {
  return (items || []).slice().sort((a, b) => (Number(a.last_activity_days) || 0) - (Number(b.last_activity_days) || 0));
}

// "X/Y" ready-to-land count for a stacked patch — X parts accepted of Y open
// parts. Only meaningful when there's more than one part (for a single patch the
// state pill already says it all), so "" for a 1-patch bug. This is the signal
// that a bug with an accepted part still isn't ready: "1/2" ≠ ready.
function readyCount(item) {
  const total = Number(item && item.patch_total) || 0;
  const acc = Number(item && item.patch_accepted) || 0;
  return total > 1 ? `${acc}/${total}` : "";
}

// Case-insensitive substring filter over id + title + tag text — for the
// my-bugs ledger search. Pure.
function filterLedger(items, q) {
  const s = (q || "").trim().toLowerCase();
  if (!s) return (items || []).slice();
  return (items || []).filter(it => {
    const hay = [it.id, it.title, ...((it.tags || []).map(t => t.text))].join(" ").toLowerCase();
    return hay.includes(s);
  });
}

// Count across all sections (top-bar summary).
function totalItems(data) {
  if (!data || !data.sections) return 0;
  return SECTIONS.reduce((n, s) => n + ((data.sections[s.key] || []).length), 0);
}

// "3m ago" / "2h ago" from an ISO timestamp relative to `now` (ms).
function generatedAgo(iso, nowMs) {
  const t = Date.parse(iso);
  if (isNaN(t)) return "";
  const mins = Math.max(0, Math.floor((nowMs - t) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + "h ago";
  return Math.floor(hrs / 24) + "d ago";
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    SECTIONS, orderedSections, moveKey, escapeHtml, tagClass, tagRank, displayTags, waitingLabel, patchStatusMeta, actionsForItem,
    actionKey, buildQueueEntry, viewMode, totalItems, generatedAgo, sortForSection,
    analyzedSplit, filterLedger, ACTION_META, actionMeta, myBugsZones, byRecency,
    readyCount, ACTIVE_DAYS,
    MYWORK_SECTIONS, FOCUS_CAP, defaultSection, sectionOf, groupBySection, driftHint,
  };
}
