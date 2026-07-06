/* Unit tests for the v3 dashboard logic (sections, tags, cards, actions, view
 * state). Run from the repo root: `node --test`. */
const test = require("node:test");
const assert = require("node:assert");
const L = require("../dashboard.logic.js");

test("SECTIONS are the three v3 buckets in order", () => {
  assert.deepStrictEqual(L.SECTIONS.map(s => s.key), ["needinfos", "reviews", "my_bugs"]);
});

test("tagClass: color is signal only — danger red, attention amber, rest neutral", () => {
  assert.strictEqual(L.tagClass("security"), "security");   // filled red
  assert.strictEqual(L.tagClass("warn"), "red");            // crash → danger
  assert.strictEqual(L.tagClass("memory-safety"), "red");
  assert.strictEqual(L.tagClass("regression"), "amber");    // attention
  assert.strictEqual(L.tagClass("severity"), "amber");
  assert.strictEqual(L.tagClass("component"), "");          // context → neutral (was cyan)
  assert.strictEqual(L.tagClass("good"), "");               // descriptive → neutral (was green)
  assert.strictEqual(L.tagClass("info"), "");
  assert.strictEqual(L.tagClass("nope"), "");
});

test("tagRank orders filled-danger > danger > attention > neutral", () => {
  assert.ok(L.tagRank("security") > L.tagRank("warn"));
  assert.ok(L.tagRank("warn") > L.tagRank("regression"));
  assert.ok(L.tagRank("regression") > L.tagRank("component"));
  assert.strictEqual(L.tagRank("component"), 0);
});

test("displayTags: dedup by text, signal-first, capped", () => {
  const tags = [
    { text: "Audio/Video", kind: "component" },
    { text: "REGRESSION", kind: "regression" },
    { text: "regression", kind: "info" },      // dup of REGRESSION (case-insensitive)
    { text: "sec", kind: "security" },
    { text: "has-profile", kind: "info" },
  ];
  const out = L.displayTags(tags, 3);
  assert.strictEqual(out.length, 3);                          // capped
  assert.deepStrictEqual(out.map(t => t.text), ["sec", "REGRESSION", "Audio/Video"]); // security > regression > neutral; dup dropped
  assert.deepStrictEqual(L.displayTags([], 3), []);
});

test("waitingLabel: today / days / weeks / months", () => {
  assert.strictEqual(L.waitingLabel(0), "today");
  assert.strictEqual(L.waitingLabel(5), "5d");
  assert.strictEqual(L.waitingLabel(9), "1w");
  assert.strictEqual(L.waitingLabel(40), "1mo");
});

test("patchStatusMeta: state colors (r- red / r+ green / waiting cyan / wip blue)", () => {
  assert.deepStrictEqual(L.patchStatusMeta("needs-revision"), { label: "r- revise", cls: "red" });
  assert.deepStrictEqual(L.patchStatusMeta("accepted"), { label: "r+ land it", cls: "green" });
  assert.strictEqual(L.patchStatusMeta("in-review").cls, "cyan");
  assert.strictEqual(L.patchStatusMeta("wip").cls, "blue");
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

test("myBugsZones: active (revise/waiting/wip/todo) vs parked backlog", () => {
  const z = L.myBugsZones([
    { id: "1", patch_status: "none", last_activity_days: 1 },            // fresh, no patch → todo (active)
    { id: "2", patch_status: "needs-revision", last_activity_days: 2 },  // r-, active → revise
    { id: "3", patch_status: "accepted", last_activity_days: 2 },        // r+ parked → backlog (even fresh)
    { id: "4", patch_status: "in-review", last_activity_days: 3 },       // active review → waiting
    { id: "5", patch_status: "wip", last_activity_days: 4 },             // active draft → wip
    { id: "6", patch_status: "none", last_activity_days: 200 },          // stale, no patch → backlog
  ]);
  assert.deepStrictEqual(z.revise.map(b => b.id), ["2"]);
  assert.deepStrictEqual(z.waiting.map(b => b.id), ["4"]);
  assert.deepStrictEqual(z.wip.map(b => b.id), ["5"]);
  assert.deepStrictEqual(z.todo.map(b => b.id), ["1"]);                  // just-filed bug, no patch
  assert.deepStrictEqual(z.backlog.map(b => b.id).sort(), ["3", "6"]);   // parked r+ + stale no-patch
});

test("myBugsZones: a dormant patch (untouched > window) drops to backlog", () => {
  const items = [
    { id: "a", patch_status: "in-review", last_activity_days: 400 },  // abandoned review
    { id: "b", patch_status: "wip", last_activity_days: 500 },        // stale draft
    { id: "c", patch_status: "in-review", last_activity_days: 3 },    // live review
  ];
  const z = L.myBugsZones(items);
  assert.deepStrictEqual(z.waiting.map(b => b.id), ["c"]);
  assert.deepStrictEqual(z.backlog.map(b => b.id).sort(), ["a", "b"]);
  // window is tunable: with a huge window, the old review counts as active again
  assert.deepStrictEqual(L.myBugsZones(items, 1000).waiting.map(b => b.id).sort(), ["a", "c"]);
});

test("byRecency: most-recently-active first", () => {
  assert.deepStrictEqual(L.byRecency([{ id: "a", last_activity_days: 9 }, { id: "b", last_activity_days: 1 }]).map(b => b.id), ["b", "a"]);
});

test("readyCount: X/Y only for a multi-patch stack, blank for a single patch", () => {
  assert.strictEqual(L.readyCount({ patch_accepted: 1, patch_total: 2 }), "1/2");
  assert.strictEqual(L.readyCount({ patch_accepted: 3, patch_total: 3 }), "3/3");
  assert.strictEqual(L.readyCount({ patch_accepted: 1, patch_total: 1 }), "");  // single patch → pill says it
  assert.strictEqual(L.readyCount({}), "");
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
