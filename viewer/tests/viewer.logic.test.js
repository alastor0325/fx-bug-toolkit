/* Unit tests for viewer/viewer.logic.js — run with zero deps (from repo root):
 *   node --test
 */
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const VL = require(path.join(__dirname, "..", "viewer.logic.js"));

test("escapeHtml escapes the dangerous characters incl. quotes", () => {
  assert.strictEqual(VL.escapeHtml('a<b>&"c'), "a&lt;b&gt;&amp;&quot;c");
  assert.strictEqual(VL.escapeHtml(null), "");
  assert.strictEqual(VL.escapeHtml(12345), "12345");
});

test("sfUrl builds a searchfox URL and strips the L from line anchors", () => {
  assert.strictEqual(
    VL.sfUrl("dom/media/Foo.cpp#L297-L299"),
    "https://searchfox.org/mozilla-central/source/dom/media/Foo.cpp#297-299");
  assert.strictEqual(
    VL.sfUrl("dom/media/Bar.cpp"),
    "https://searchfox.org/mozilla-central/source/dom/media/Bar.cpp");
});

test("bz builds a bugzilla URL", () => {
  assert.strictEqual(VL.bz(123456), "https://bugzilla.mozilla.org/show_bug.cgi?id=123456");
});

test("indexUrl cache-busts index.json with the given nonce", () => {
  assert.strictEqual(VL.indexUrl(1700000000000), "./index.json?ts=1700000000000");
  // distinct nonces (e.g. per page load) yield distinct URLs, defeating the cache
  assert.notStrictEqual(VL.indexUrl(1), VL.indexUrl(2));
});

test("shouldShowDropdown: only when collapsed + non-blank query + matches", () => {
  assert.strictEqual(VL.shouldShowDropdown(true, "foo", 3), true);
  assert.strictEqual(VL.shouldShowDropdown(false, "foo", 3), false);  // expanded → the list is the surface
  assert.strictEqual(VL.shouldShowDropdown(true, "   ", 3), false);   // blank query
  assert.strictEqual(VL.shouldShowDropdown(true, "foo", 0), false);   // no matches
  assert.strictEqual(VL.shouldShowDropdown(true, null, 3), false);    // null query is safe
});

test("depthMeta maps triage/deep to plain labels, passes others through", () => {
  assert.strictEqual(VL.depthMeta("triage").label, "quick");
  assert.strictEqual(VL.depthMeta("deep").label, "full");
  assert.strictEqual(VL.depthMeta("weird").label, "weird");
});

test("chip/depthChip builders escape and class correctly", () => {
  assert.match(VL.chipHtml("hi", "cx-low"), /class="chip cx-low".*>hi</);
  assert.match(VL.chipHtml("<x>"), /&lt;x&gt;/);
  const dc = VL.depthChipHtml("triage");
  assert.match(dc, /class="chip depth-triage"/);
  assert.match(dc, />quick</);
  assert.match(dc, /title="Quick triage pass/);
});

test("matchesQuery searches id + summary + root_cause + notes + body, case-insensitive", () => {
  const d = { bug_id: 123456, summary: "Autoplay bug", root_cause: "blocking_policy", notes: "", body: "MediaDecoder" };
  assert.ok(VL.matchesQuery(d, ""));            // empty query matches all
  assert.ok(VL.matchesQuery(d, "AUTOPLAY"));    // case-insensitive, summary
  assert.ok(VL.matchesQuery(d, "123456"));      // id
  assert.ok(VL.matchesQuery(d, "blocking_policy")); // root_cause (underscore preserved)
  assert.ok(VL.matchesQuery(d, "mediadecoder")); // body
  assert.ok(!VL.matchesQuery(d, "nonexistent"));
});

test("byDate sorts newest-first when desc, oldest-first otherwise", () => {
  const a = { date: "2026-01-01" }, b = { date: "2020-01-01" };
  assert.ok(VL.byDate(a, b, true) < 0);   // a (newer) before b
  assert.ok(VL.byDate(a, b, false) > 0);  // a (newer) after b
});
