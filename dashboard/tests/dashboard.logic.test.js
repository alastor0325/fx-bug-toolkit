/* Unit tests for the v3 dashboard logic (sections, tags, cards, actions, view
 * state). Run from the repo root: `node --test`. */
const test = require("node:test");
const assert = require("node:assert");
const L = require("../dashboard.logic.js");

test("SECTIONS are the three v3 buckets in order", () => {
  assert.deepStrictEqual(L.SECTIONS.map(s => s.key), ["needinfos", "reviews", "my_bugs"]);
});

test("tagClass maps kinds to theme chip colors, neutral for unknown/info", () => {
  assert.strictEqual(L.tagClass("component"), "cyan");
  assert.strictEqual(L.tagClass("security"), "security");
  assert.strictEqual(L.tagClass("regression"), "red");
  assert.strictEqual(L.tagClass("good"), "green");
  assert.strictEqual(L.tagClass("info"), "");
  assert.strictEqual(L.tagClass("nope"), "");
});

test("waitingLabel: today / days / weeks / months", () => {
  assert.strictEqual(L.waitingLabel(0), "today");
  assert.strictEqual(L.waitingLabel(5), "5d");
  assert.strictEqual(L.waitingLabel(9), "1w");
  assert.strictEqual(L.waitingLabel(40), "1mo");
});

test("patchStatusMeta covers the patch lifecycle", () => {
  assert.strictEqual(L.patchStatusMeta("needs-revision").label, "needs revision");
  assert.strictEqual(L.patchStatusMeta("accepted").cls, "green");
  assert.strictEqual(L.patchStatusMeta("none").label, "no patch");
  assert.strictEqual(L.patchStatusMeta("weird").label, "weird");
});

test("actionsForItem: NI gets draft+investigate, +bug-start only when solvable", () => {
  const base = L.actionsForItem({ type: "ni", solvable: false }).map(a => a.action);
  assert.deepStrictEqual(base, ["draft-reply", "bug-investigate"]);
  const solvable = L.actionsForItem({ type: "ni", solvable: true }).map(a => a.action);
  assert.ok(solvable.includes("bug-start"));
});

test("actionsForItem: review gets /review; my_bugs are display-only (MVP)", () => {
  assert.deepStrictEqual(L.actionsForItem({ type: "review" }).map(a => a.action), ["review"]);
  assert.deepStrictEqual(L.actionsForItem({ type: "mybug" }), []);
});

test("actionKey pairs a card+action stably", () => {
  assert.strictEqual(L.actionKey("1911204", "draft-reply"), "1911204::draft-reply");
});

test("buildQueueEntry carries id/type/action/title/url and queued status", () => {
  const e = L.buildQueueEntry({ id: "D5", type: "review", title: "t", url: "u" }, "review");
  assert.deepStrictEqual(e, { id: "D5", type: "review", action: "review", title: "t", url: "u", status: "queued" });
});

test("actionMeta labels + accents known actions; falls back for unknown", () => {
  assert.strictEqual(L.actionMeta("bug-start").label, "run /bug-start");
  assert.strictEqual(L.actionMeta("draft-reply").accent, "amber");
  assert.deepStrictEqual(L.actionMeta("mystery"), { label: "mystery", accent: "" });
});

test("viewMode: processing on first run, ready with data, empty when done+0", () => {
  assert.strictEqual(L.viewMode(null, { state: "running" }).mode, "processing");
  const data = { sections: { needinfos: [{ id: "1" }], reviews: [], my_bugs: [] } };
  const ready = L.viewMode(data, { state: "ready" });
  assert.strictEqual(ready.mode, "ready");
  assert.strictEqual(ready.analyzing, false);
  // data present + a regeneration running → ready but analyzing
  assert.strictEqual(L.viewMode(data, { state: "running" }).analyzing, true);
  const empty = { sections: { needinfos: [], reviews: [], my_bugs: [] } };
  assert.strictEqual(L.viewMode(empty, { state: "ready" }).mode, "empty");
});

test("sortForSection: needinfos newest by default, oldest when asked; others unchanged", () => {
  const nis = [{ id: "a", waiting_days: 2 }, { id: "b", waiting_days: 30 }, { id: "c", waiting_days: 9 }];
  // default (newer) = fewest days waited first
  assert.deepStrictEqual(L.sortForSection("needinfos", nis).map(i => i.id), ["a", "c", "b"]);
  assert.deepStrictEqual(L.sortForSection("needinfos", nis, "newer").map(i => i.id), ["a", "c", "b"]);
  // older = most days waited first
  assert.deepStrictEqual(L.sortForSection("needinfos", nis, "older").map(i => i.id), ["b", "c", "a"]);
  const mine = [{ id: "x" }, { id: "y" }];
  assert.deepStrictEqual(L.sortForSection("my_bugs", mine, "older").map(i => i.id), ["x", "y"]);  // order preserved
});

test("analyzedSplit: brief present → act, absent → rest", () => {
  const { act, rest } = L.analyzedSplit([
    { id: "1", brief: { ask: "x" } }, { id: "2", brief: null }, { id: "3" },
  ]);
  assert.deepStrictEqual(act.map(i => i.id), ["1"]);
  assert.deepStrictEqual(rest.map(i => i.id), ["2", "3"]);
});

test("filterLedger: matches id/title/tags, case-insensitive; empty query = all", () => {
  const items = [
    { id: "111", title: "Crash on seek", tags: [{ text: "Playback" }] },
    { id: "222", title: "Audio mute", tags: [{ text: "Web Audio" }] },
  ];
  assert.strictEqual(L.filterLedger(items, "").length, 2);
  assert.deepStrictEqual(L.filterLedger(items, "crash").map(i => i.id), ["111"]);
  assert.deepStrictEqual(L.filterLedger(items, "web audio").map(i => i.id), ["222"]);
  assert.deepStrictEqual(L.filterLedger(items, "2").map(i => i.id), ["222"]);
});

test("myBugsSplit: active (open patch) vs backlog; byRecency puts recent on top", () => {
  const items = [
    { id: "1", patch_status: "none", last_activity_days: 3 },
    { id: "2", patch_status: "needs-revision", last_activity_days: 9 },
    { id: "3", patch_status: "accepted", last_activity_days: 1 },
    { id: "4", patch_status: "landed", last_activity_days: 2 },
  ];
  const { active, backlog } = L.myBugsSplit(items);
  assert.deepStrictEqual(active.map(b => b.id).sort(), ["2", "3"]);   // open patches
  assert.deepStrictEqual(backlog.map(b => b.id).sort(), ["1", "4"]);  // none + landed
  assert.deepStrictEqual(L.byRecency(active).map(b => b.id), ["3", "2"]);  // 1d before 9d
});

test("totalItems sums across sections", () => {
  assert.strictEqual(L.totalItems({ sections: { needinfos: [1, 2], reviews: [3], my_bugs: [] } }), 3);
  assert.strictEqual(L.totalItems(null), 0);
});

test("generatedAgo: minutes / hours / days / invalid", () => {
  const now = Date.parse("2026-07-04T15:00:00Z");
  assert.strictEqual(L.generatedAgo("2026-07-04T14:57:00Z", now), "3m ago");
  assert.strictEqual(L.generatedAgo("2026-07-04T13:00:00Z", now), "2h ago");
  assert.strictEqual(L.generatedAgo("2026-07-02T15:00:00Z", now), "2d ago");
  assert.strictEqual(L.generatedAgo("bogus", now), "");
});
