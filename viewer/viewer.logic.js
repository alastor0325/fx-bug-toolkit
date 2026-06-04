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

if (typeof module !== "undefined" && module.exports) {
  module.exports = { escapeHtml, sfUrl, bz, DEPTH, depthMeta, chipHtml, depthChipHtml, matchesQuery, byDate };
}
