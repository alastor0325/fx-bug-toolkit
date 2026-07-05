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
  { key: "my_bugs",   label: "Bugs I'm working on",  accent: "blue",  empty: "Nothing in progress." },
];

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Map a tag's `kind` to a shared chip color class ("" = neutral chip). Keeps the
// page's tag palette consistent with /theme.css.
function tagClass(kind) {
  return ({ component: "cyan", severity: "amber", security: "security",
            regression: "red", warn: "amber", good: "green" })[kind] || "";
}

// Coarse human age from a day count.
function waitingLabel(days) {
  const d = Math.max(0, Math.floor(Number(days) || 0));
  if (d === 0) return "today";
  if (d < 7) return d + "d";
  if (d < 30) return Math.floor(d / 7) + "w";
  return Math.floor(d / 30) + "mo";
}

// Patch-status pill for a "my bug" card: {label, cls}.
function patchStatusMeta(status) {
  return ({
    wip:               { label: "WIP",            cls: "blue" },
    "in-review":       { label: "in review",      cls: "cyan" },
    "needs-revision":  { label: "needs revision", cls: "amber" },
    accepted:          { label: "accepted · land", cls: "green" },
    landed:            { label: "landed",         cls: "" },
    none:              { label: "no patch",       cls: "" },
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
  return { id: item.id, type: item.type, action, title: item.title, status: "queued" };
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

// Per-section ordering. Needinfos are sorted oldest-waiting first (the earliest
// dated needinfo — the one that's been on you longest — comes first); other
// sections keep collector order. Pure (returns a new array).
function sortForSection(key, items) {
  const arr = (items || []).slice();
  if (key === "needinfos") {
    arr.sort((a, b) => (Number(b.waiting_days) || 0) - (Number(a.waiting_days) || 0));
  }
  return arr;
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
    SECTIONS, escapeHtml, tagClass, waitingLabel, patchStatusMeta, actionsForItem,
    actionKey, buildQueueEntry, viewMode, totalItems, generatedAgo, sortForSection,
  };
}
