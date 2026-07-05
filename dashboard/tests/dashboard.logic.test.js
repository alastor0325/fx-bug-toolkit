/* Unit tests for the dashboard's pure logic (urgency scoring, ordering, filters,
 * summary, action verbs). Run from the repo root: `node --test`. */
const test = require("node:test");
const assert = require("node:assert");
const L = require("../dashboard.logic.js");

const item = (o) => Object.assign({ type: "ni", id: "1", title: "t", url: "u", waiting_days: 0 }, o);

test("waitingLabel: today / days / weeks / months", () => {
  assert.strictEqual(L.waitingLabel(0), "today");
  assert.strictEqual(L.waitingLabel(3), "3d");
  assert.strictEqual(L.waitingLabel(9), "1w");
  assert.strictEqual(L.waitingLabel(40), "1mo");
});

test("urgencyScore: security + severity + waiting all raise the score", () => {
  const plain = L.urgencyScore(item({ type: "ni", waiting_days: 0 }));
  assert.ok(L.urgencyScore(item({ type: "ni", waiting_days: 10 })) > plain, "age raises");
  assert.ok(L.urgencyScore(item({ type: "ni", sec: true })) > plain, "security raises");
  assert.ok(L.urgencyScore(item({ type: "ni", severity: "S1" })) > plain, "severity raises");
  // a blocking type (ni) outranks a self-directed one (fix) at equal age
  assert.ok(L.urgencyScore(item({ type: "ni" })) > L.urgencyScore(item({ type: "fix" })));
});

test("urgencyLevel: red reserved for security / S1 / blocking-a-week", () => {
  assert.strictEqual(L.urgencyLevel(item({ sec: true, waiting_days: 0 })), "crit");
  assert.strictEqual(L.urgencyLevel(item({ severity: "S1", waiting_days: 0 })), "crit");
  assert.strictEqual(L.urgencyLevel(item({ type: "ni", waiting_days: 8 })), "crit");   // blocking 1w+
  assert.strictEqual(L.urgencyLevel(item({ type: "fix", waiting_days: 8 })), "high");  // old but not blocking
  assert.strictEqual(L.urgencyLevel(item({ type: "fix", waiting_days: 4 })), "med");
  assert.strictEqual(L.urgencyLevel(item({ type: "fix", waiting_days: 1 })), "low");
});

test("sortQueue: most urgent first, deterministic", () => {
  const secNi = item({ id: "sec", type: "ni", sec: true, waiting_days: 1 });
  const oldNi = item({ id: "old", type: "ni", waiting_days: 10 });
  const freshFix = item({ id: "fix", type: "fix", waiting_days: 0 });
  const out = L.sortQueue([freshFix, oldNi, secNi]).map(i => i.id);
  assert.deepStrictEqual(out, ["sec", "old", "fix"]);
});

test("filterQueue: 'mine' matches land+fix; type keys match themselves", () => {
  const items = [item({ id: "a", type: "ni" }), item({ id: "b", type: "review" }),
                 item({ id: "c", type: "land" }), item({ id: "d", type: "fix" })];
  assert.deepStrictEqual(L.filterQueue(items, "all").map(i => i.id), ["a", "b", "c", "d"]);
  assert.deepStrictEqual(L.filterQueue(items, "ni").map(i => i.id), ["a"]);
  assert.deepStrictEqual(L.filterQueue(items, "review").map(i => i.id), ["b"]);
  assert.deepStrictEqual(L.filterQueue(items, "mine").map(i => i.id), ["c", "d"]);
});

test("summarize: counts blocking items + oldest wait", () => {
  const s = L.summarize([item({ type: "ni", waiting_days: 3 }),
                         item({ type: "review", waiting_days: 9 }),
                         item({ type: "fix", waiting_days: 2 })]);
  assert.strictEqual(s.blocking, 2);   // ni + review, not fix
  assert.strictEqual(s.oldestWait, 9);
  assert.strictEqual(s.total, 3);
});

test("actionVerb: homogeneous gets a specific verb, mixed is generic", () => {
  assert.strictEqual(L.actionVerb([item({ type: "ni" }), item({ type: "ni" })]), "Draft replies (2)");
  assert.strictEqual(L.actionVerb([item({ type: "review" })]), "Run /review (1)");
  assert.strictEqual(L.actionVerb([item({ type: "ni" }), item({ type: "review" })]), "Process 2 selected");
  assert.strictEqual(L.actionVerb([]), "");
});

test("generatedAgo: minutes / hours / days", () => {
  const now = Date.parse("2026-07-03T15:00:00Z");
  assert.strictEqual(L.generatedAgo("2026-07-03T14:57:00Z", now), "3m ago");
  assert.strictEqual(L.generatedAgo("2026-07-03T13:00:00Z", now), "2h ago");
  assert.strictEqual(L.generatedAgo("2026-07-01T15:00:00Z", now), "2d ago");
  assert.strictEqual(L.generatedAgo("bogus", now), "");
});
