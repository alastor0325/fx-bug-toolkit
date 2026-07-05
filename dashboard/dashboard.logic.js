/* Pure, DOM-free logic for the personal dashboard — unit-tested via `node --test`
 * (dashboard/tests/dashboard.logic.test.js). The HTML wires these into the DOM;
 * anything testable lives here, never inline in dashboard.html.
 *
 * Model: the collector emits ONE urgency-ranked `queue` (things that need YOU:
 * needinfos, review requests, and your own revisions to land/fix) plus a
 * secondary `backlog` (bugs assigned to you). The queue is a triage list — the
 * dashboard's job is "what do I unblock first," not "here are four equal lists."
 */

// Queue item types, with display label, glyph, accent (a /theme.css chip color),
// and the Stage-2 action verb. `mine` groups land+fix for filtering.
const TYPE = {
  ni:     { label: "NI",     glyph: "?", accent: "amber", verb: "Draft replies",    group: "ni" },
  review: { label: "REVIEW", glyph: "⌥", accent: "cyan",  verb: "Run /review",      group: "review" },
  land:   { label: "LAND",   glyph: "✓", accent: "green", verb: "Land",             group: "mine" },
  fix:    { label: "FIX",    glyph: "✎", accent: "blue",  verb: "Open for fixes",   group: "mine" },
};

// Top-of-queue filter chips. `match` maps a chip to the types it shows.
const FILTERS = [
  { key: "all",    label: "All" },
  { key: "ni",     label: "Needinfo" },
  { key: "review", label: "Reviews" },
  { key: "mine",   label: "Yours" },
];

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Coarse human age from a day count — the dashboard cares about "how stale," not
// exact hours. Used for the "waiting on you Nd" badge.
function waitingLabel(days) {
  const d = Math.max(0, Math.floor(Number(days) || 0));
  if (d === 0) return "today";
  if (d < 7) return d + "d";
  if (d < 30) return Math.floor(d / 7) + "w";
  return Math.floor(d / 30) + "mo";
}

// Composite urgency score (higher = more urgent). Drives queue order so the #1
// thing to unblock is always on top, regardless of which system it came from.
// Inputs: type (someone-blocked-on-me ranks highest), waiting-on-me age (capped
// so one ancient item can't dominate), security flag, severity, priority, and a
// review re-request (author pushed changes and is waiting again).
function urgencyScore(item) {
  const TYPE_BASE = { ni: 60, review: 50, land: 45, fix: 30 };
  let s = TYPE_BASE[item.type] || 0;
  s += Math.min(Number(item.waiting_days) || 0, 21) * 2;
  if (item.sec) s += 50;
  s += ({ S1: 35, S2: 18, S3: 6 })[item.severity] || 0;
  s += ({ P1: 20, P2: 8 })[item.priority] || 0;
  if (item.is_rerequest) s += 10;
  return s;
}

// Urgency tier for the row's left accent bar. RED ("crit") is reserved for
// "someone/something is genuinely blocked or dangerous" — a security bug, an S1,
// or a person/patch that's been blocked on you a week or more — NOT merely "old."
function urgencyLevel(item) {
  if (item.sec || item.severity === "S1") return "crit";
  const blocking = item.type === "ni" || item.type === "review";
  const w = Number(item.waiting_days) || 0;
  if (blocking && w >= 7) return "crit";
  if (w >= 7 || item.severity === "S2") return "high";
  if (w >= 3) return "med";
  return "low";
}

// Queue sorted most-urgent first (score desc). Stable tiebreak on waiting age so
// order is deterministic (matters for tests + a steady UI across refreshes).
function sortQueue(items) {
  return (items || []).slice().sort((a, b) => {
    const d = urgencyScore(b) - urgencyScore(a);
    return d !== 0 ? d : (Number(b.waiting_days) || 0) - (Number(a.waiting_days) || 0);
  });
}

// Filter the queue to a chip. "mine" = land+fix; a type key matches that type;
// "all" (or anything unknown) passes everything through.
function filterQueue(items, filterKey) {
  if (!filterKey || filterKey === "all") return (items || []).slice();
  return (items || []).filter(it => {
    const g = (TYPE[it.type] || {}).group;
    return it.type === filterKey || g === filterKey;
  });
}

// Top-bar triage summary: how many items are blocking someone else on you, and
// the longest anything has waited. "2 blocking you · oldest wait 9d" beats a bare
// total count — it's a call to action, not a vanity number.
function summarize(queue) {
  const q = queue || [];
  const blocking = q.filter(i => i.type === "ni" || i.type === "review").length;
  const oldestWait = q.reduce((m, i) => Math.max(m, Number(i.waiting_days) || 0), 0);
  return { blocking, oldestWait, total: q.length };
}

// The verb for the sticky action bar, given the selected items. A homogeneous
// selection gets its specific verb ("Draft 2 replies"); a mixed one falls back to
// a generic "Process N selected". Stage 2 wires these to real actions.
function actionVerb(selected) {
  const sel = selected || [];
  if (!sel.length) return "";
  const types = new Set(sel.map(i => i.type));
  if (types.size === 1) {
    const t = TYPE[sel[0].type];
    if (t) return `${t.verb} (${sel.length})`;
  }
  return `Process ${sel.length} selected`;
}

// "3m ago" / "2h ago" / "just now" from an ISO timestamp relative to `now` (ms) —
// the top-bar "updated …" freshness line.
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
    TYPE, FILTERS, escapeHtml, waitingLabel, urgencyScore, urgencyLevel,
    sortQueue, filterQueue, summarize, actionVerb, generatedAgo,
  };
}
