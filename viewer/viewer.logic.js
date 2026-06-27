/* viewer.logic.js — pure, DOM-free helpers for the investigation viewer.
 * Loaded as a plain <script> in the browser (defines globals) AND require()-d
 * by the Node unit tests (viewer/tests/viewer.logic.test.js). Keep this file free of
 * any DOM / window references so both work. */

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// dom/media/Foo.cpp#L297-L299  ->  searchfox source URL with a #297-299 anchor
function sfUrl(p) {
  const [path, anchor] = String(p).split("#");
  const a = anchor ? "#" + anchor.replace(/L/g, "") : "";
  return `https://searchfox.org/mozilla-central/source/${path}${a}`;
}

function bz(id) {
  return `https://bugzilla.mozilla.org/show_bug.cgi?id=${id}`;
}

// Cache-busted URL for index.json. serve.py rebuilds index.json on every start,
// but SimpleHTTPRequestHandler serves it as a cacheable static file, so a bare
// fetch can return a stale copy and the viewer "won't catch up" after the
// investigation dir changes. `nonce` is a per-load value (e.g. Date.now()).
function indexUrl(nonce) {
  return `./index.json?ts=${nonce}`;
}

// "depth" frontmatter is jargon; surface plain "quick"/"full" with a tooltip.
const DEPTH = {
  triage: { label: "quick", tip: "Quick triage pass — a root-cause hypothesis only, no fix or test plan" },
  deep:   { label: "full",  tip: "Full investigation — verified root cause + implementation & test plan" },
};
function depthMeta(v) { return DEPTH[v] || { label: v, tip: "" }; }

function chipHtml(text, cls) {
  return `<span class="chip ${cls || ""}">${escapeHtml(text)}</span>`;
}
function depthChipHtml(v) {
  const m = depthMeta(v);
  return `<span class="chip depth-${escapeHtml(v)}" title="${escapeHtml(m.tip)}">${escapeHtml(m.label)}</span>`;
}

// case-insensitive substring match over id + summary + root_cause + notes + body
function matchesQuery(d, q) {
  if (!q) return true;
  const hay = (d.bug_id + " " + (d.summary || "") + " " + (d.root_cause || "") +
               " " + (d.notes || "") + " " + (d.body || "")).toLowerCase();
  return hay.includes(q.toLowerCase());
}

// comparator over the "YYYY-MM-DD" date string; desc = newest first
function byDate(a, b, desc) {
  return desc ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date);
}

// Index of the entry whose bug_id matches `id` (string-compared so a numeric
// id and its #hash-string form match), or -1 when absent / not-yet-loaded.
// Used to re-select the open investigation after the list is rebuilt: the
// deep-link path, and the on-visible refresh that swaps in a freshly fetched
// index — object identity can't survive that swap, so we re-find by bug_id.
function findIndexByBugId(list, id) {
  if (!Array.isArray(list)) return -1;
  return list.findIndex(d => String(d.bug_id) === String(id));
}

// Whether a "user returned to the viewer" event (tab visible again, or the
// window regained focus) should kick off a re-fetch. Both visibilitychange and
// focus can fire for a single return, and a return mid-fetch shouldn't stack a
// second one — so refresh only when the tab is actually visible and no fetch is
// already in flight.
function shouldRefresh(visibilityState, refreshing) {
  return visibilityState === "visible" && !refreshing;
}

// Whether to show the search-results dropdown. The filtered list lives only in
// the sidebar, so when the sidebar is collapsed a search would otherwise have no
// visible surface — show the dropdown only then, and only with a real query and
// at least one match.
function shouldShowDropdown(collapsed, query, count) {
  return !!collapsed && String(query == null ? "" : query).trim().length > 0 && count > 0;
}

// The detail pane's scrollTop after a (re-)render. Rendering re-selects a doc on
// every background refresh (visibilitychange/focus → loadIndex → reselect) and on
// any same-doc reselect, so unconditionally zeroing scrollTop throws away the
// reader's position on every tab-switch / link-out-and-back. Preserve the prior
// scroll only when the SAME doc is being re-rendered (same content ⇒ same height,
// so the offset is still valid); reset to the top when switching to a different
// doc. `prevId == null` (nothing rendered yet) counts as a switch.
function scrollTopAfterRender(prevId, nextId, prevScrollTop) {
  if (prevId != null && String(prevId) === String(nextId)) {
    return prevScrollTop > 0 ? prevScrollTop : 0;
  }
  return 0;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { escapeHtml, sfUrl, bz, indexUrl, DEPTH, depthMeta, chipHtml, depthChipHtml, matchesQuery, byDate, findIndexByBugId, shouldRefresh, shouldShowDropdown, scrollTopAfterRender };
}
