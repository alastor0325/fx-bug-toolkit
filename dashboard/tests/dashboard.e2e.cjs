/* Browser E2E for the v3 dashboard: sections render, cards expand, the
 * solvability gate shows the /bug-start button, and clicking an action POSTs to
 * /queue. Self-contained — a throwaway Node server serves the real assets + a
 * fixture data/status and handles POST /queue (no serve.py, no Claude).
 *
 *   node dashboard/tests/dashboard.e2e.cjs
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const { chromium } = require("playwright");

const DASH = path.resolve(__dirname, "..");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
               ".svg": "image/svg+xml", ".css": "text/css" };

const DATA = {
  generated_at: "2026-07-04T09:00:00Z", user: "you@example.com", status: "ready",
  sections: {
    needinfos: [
      // analyzed (brief) → "act" cards
      { type: "ni", id: "111", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=111",
        title: "Solvable NI", waiting_days: 3, from: "asker@example.com",
        tags: [{ text: "Audio/Video", kind: "component" }, { text: "S2", kind: "severity" }],
        brief: { bug: "what the bug is", ask: "what the ask is" },
        solvable: true, solvable_reason: "clear STR" },
      { type: "ni", id: "112", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=112",
        title: "Analyzed older NI", waiting_days: 20, from: "asker2@example.com",
        tags: [], brief: { bug: "b", ask: "a" } },
      // not analyzed → demoted stale ledger
      { type: "ni", id: "113", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=113",
        title: "Stale NI", waiting_days: 500, from: "old@example.com",
        tags: [{ text: "Audio/Video", kind: "component" }], brief: null },
    ],
    reviews: [
      // group, analyzed → Group zone act card
      { type: "review", id: "D9", url: "https://phabricator.services.mozilla.com/D9",
        title: "A group review", waiting_days: 1, author: "coworker", direct: false,
        reviewers: ["#media-playback-reviewers"], tags: [], brief: { summary: "review summary" } },
      // direct, analyzed → Direct zone act card
      { type: "review", id: "D10", url: "https://phabricator.services.mozilla.com/D10",
        title: "A direct review", waiting_days: 2, author: "someone", direct: true,
        reviewers: ["me"], tags: [], brief: { summary: "direct summary" } },
      // group, not analyzed → Group zone stale ledger
      { type: "review", id: "D11", url: "https://phabricator.services.mozilla.com/D11",
        title: "Old group review", waiting_days: 40, author: "x", direct: false,
        reviewers: ["#media-playback-reviewers"], tags: [], brief: null },
    ],
    my_bugs: [
      // Needs me: r- (needs-revision) and r+ (accepted)
      { type: "mybug", id: "222", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=222",
        title: "My crash bug", last_activity_days: 1, patch_status: "needs-revision",
        reviewer: "padenot", rev_url: "https://phabricator.services.mozilla.com/D1222",
        tags: [{ text: "S2", kind: "severity" }, { text: "sec", kind: "security" }], brief: null },
      // accepted but parked (r+ I'm not landing) → backlog, even though fresh
      { type: "mybug", id: "223", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=223",
        title: "Ready to land thing", last_activity_days: 5, patch_status: "accepted",
        patch_accepted: 1, patch_total: 1,
        reviewer: "bryce", rev_url: "https://phabricator.services.mozilla.com/D1223", tags: [], brief: null },
      // dormant in-review (untouched way past the active window) → backlog
      { type: "mybug", id: "228", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=228",
        title: "Abandoned review", last_activity_days: 400, patch_status: "in-review",
        patch_accepted: 0, patch_total: 1, reviewer: "jya", rev_url: "https://phabricator.services.mozilla.com/D1228",
        tags: [], brief: null },
      // active review — a 2-patch stack, 1 of 2 accepted (X/Y count)
      { type: "mybug", id: "225", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=225",
        title: "Waiting review bug", last_activity_days: 3, patch_status: "in-review",
        patch_accepted: 1, patch_total: 2,
        reviewer: "kershaw", rev_url: "https://phabricator.services.mozilla.com/D1225", tags: [], brief: null },
      // active wip (draft I'm working)
      { type: "mybug", id: "226", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=226",
        title: "Draft bug", last_activity_days: 2, patch_status: "wip", reviewer: "", tags: [], brief: null },
      // fresh, no patch yet → active "No patch yet" zone (a bug I just filed)
      { type: "mybug", id: "229", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=229",
        title: "Just filed, no patch yet", last_activity_days: 0, patch_status: "none", tags: [], brief: null },
      // stale, no patch → collapsed backlog
      { type: "mybug", id: "224", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=224",
        title: "Old assigned bug", last_activity_days: 200, patch_status: "none", tags: [], brief: null },
    ],
  },
};
const STATUS = { state: "ready", generated_at: DATA.generated_at, counts: { needinfos: 3, reviews: 3, my_bugs: 7 } };

let posted = [];   // POST /queue payloads captured

function startServer() {
  const files = {
    "/dashboard.html": fs.readFileSync(path.join(DASH, "dashboard.html")),
    "/dashboard.logic.js": fs.readFileSync(path.join(DASH, "dashboard.logic.js")),
    "/theme.css": fs.readFileSync(path.join(DASH, "..", "assets", "theme.css")),
    "/favicon.svg": fs.readFileSync(path.join(DASH, "favicon.svg")),
    "/data.json": Buffer.from(JSON.stringify(DATA)),
    "/status.json": Buffer.from(JSON.stringify(STATUS)),
  };
  const srv = http.createServer((req, res) => {
    const url = req.url.split("?")[0];
    if (req.method === "POST" && (url === "/queue" || url === "/unqueue")) {
      let body = "";
      req.on("data", c => (body += c));
      req.on("end", () => {
        const e = JSON.parse(body || "{}");
        if (url === "/queue") posted.push(e);
        else posted = posted.filter(p => !(String(p.id) === String(e.id) && p.action === e.action));
        res.writeHead(200, { "content-type": "application/json" });
        res.end('{"ok":true}');
      });
      return;
    }
    if (url === "/queue.json") { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(posted)); return; }
    const buf = files[url];
    if (!buf) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(url)] || "text/plain" });
    res.end(buf);
  });
  return new Promise(r => srv.listen(0, "127.0.0.1", () => r({ srv, port: srv.address().port })));
}

let failures = 0;
async function check(name, fn) {
  try { await fn(); console.log("  ok   -", name); }
  catch (e) { failures++; console.log("FAIL   -", name, "::", e.message); }
}

async function main() {
  const { srv, port } = await startServer();
  const base = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`${base}/dashboard.html`, { waitUntil: "load" });
  await page.waitForSelector(".tab");

  await check("section tabs + queue tab render with counts", async () => {
    const labels = await page.$$eval(".tab", els => els.map(e => e.textContent.replace(/\d+$/, "").trim()));
    assert.deepStrictEqual(labels, ["Needinfos", "Review requests", "My work", "Queue"]);
    const counts = await page.$$eval(".tab .n", els => els.map(e => e.textContent));
    assert.deepStrictEqual(counts, ["3", "3", "7", "0"]);  // queue empty at start
  });

  await check("section tabs drag-reorder and persist", async () => {
    const tabKeys = () => page.$$eval('#tabs .tab', els => els.map(e => e.dataset.k));
    assert.deepStrictEqual(await tabKeys(), ["needinfos", "reviews", "my_bugs", "queue"], "default order");
    // section tabs are draggable, Queue is not
    assert.strictEqual(await page.getAttribute('.tab[data-k="my_bugs"]', "draggable"), "true");
    assert.notStrictEqual(await page.getAttribute('.tab[data-k="queue"]', "draggable"), "true");
    // drag "My work" onto the left half of "Needinfos" → drops before it (HTML5 DnD)
    await page.evaluate(() => {
      const dt = new DataTransfer();
      const from = document.querySelector('.tab[data-k="my_bugs"]');
      const to = document.querySelector('.tab[data-k="needinfos"]');
      const x = to.getBoundingClientRect().left + 2;
      for (const type of ["dragstart", "dragover", "drop", "dragend"]) {
        const el = (type === "dragstart" || type === "dragend") ? from : to;
        el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt, clientX: x }));
      }
    });
    assert.deepStrictEqual(await tabKeys(), ["my_bugs", "needinfos", "reviews", "queue"], "My work moved to front");
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("fxdash.secorder")));
    assert.deepStrictEqual(saved, ["my_bugs", "needinfos", "reviews"], "new order persisted to localStorage");
    // restore the default order for the rest of the suite
    await page.evaluate(() => localStorage.removeItem("fxdash.secorder"));
    await page.reload({ waitUntil: "load" });
    await page.waitForSelector(".tabpanel.active");
    assert.deepStrictEqual(await tabKeys(), ["needinfos", "reviews", "my_bugs", "queue"], "reset to default");
  });

  await check("needinfos 'act' zone = analyzed cards; stale NI is NOT a card", async () => {
    const cardIds = await page.$$eval('.tabpanel[data-k="needinfos"] .card', els => els.map(c => c.dataset.id));
    assert.deepStrictEqual(cardIds.sort(), ["111", "112"], "only analyzed NIs are act cards");
    assert.ok(!cardIds.includes("113"), "stale NI 113 is not an act card");
  });

  await check("needinfos act cards default newest-first; order toggle flips", async () => {
    const firstId = () => page.$eval('.tabpanel[data-k="needinfos"] .card', c => c.dataset.id);
    assert.strictEqual(await firstId(), "111", "newest (3d) on top by default");
    await page.click('.order-btn');
    assert.strictEqual(await firstId(), "112", "oldest (20d) on top after toggle");
    await page.click('.order-btn');
    assert.strictEqual(await firstId(), "111");
  });

  await check("stale divider is collapsed, and reveals the ledger row on click", async () => {
    assert.ok((await page.textContent('.stale-divider')).includes("1 earlier"), "divider counts the 1 stale NI");
    assert.ok(!(await page.isVisible('.stale-list .lrow')), "ledger hidden until opened");
    await page.click('.stale-divider');
    assert.ok(await page.isVisible('.stale-list .lrow'), "ledger row shown after toggle");
    const row = await page.textContent('.stale-list .lrow');
    assert.ok(row.includes("113") && row.includes("Stale NI"));
  });

  await check("expanding a solvable NI reveals brief + the /bug-start button", async () => {
    await page.click('.card[data-id="111"] .chead');
    await page.waitForSelector('.card[data-id="111"].open .cbody');
    const bodyText = await page.$eval('.card[data-id="111"] .cbody', e => e.innerText);
    assert.ok(bodyText.includes("what the ask is"), "shows the needinfo ask");
    const btns = await page.$$eval('.card[data-id="111"] .abtn', els => els.map(e => e.textContent));
    assert.ok(btns.some(b => b.includes("Draft reply")), "has Draft reply");
    assert.ok(btns.some(b => b.includes("/bug-start")), "solvable → offers /bug-start");
  });

  await check("clicking an action POSTs it to /queue and the button shows queued", async () => {
    await page.click('.card[data-id="111"] .abtn[data-action="draft-reply"]');
    await page.waitForTimeout(200);
    assert.ok(posted.some(p => p.id === "111" && p.action === "draft-reply"), "POST /queue received");
    const q = await page.$eval('.card[data-id="111"] .abtn.queued', e => e.textContent).catch(() => "");
    assert.ok(/queued/i.test(q), "button flips to queued");
  });

  await check("Queue tab lists the queued action; ✕ removes it (count updates live)", async () => {
    assert.strictEqual(await page.textContent('.tab[data-k="queue"] .n'), "1", "queue count bumped on queue");
    await page.click('.tab[data-k="queue"]');
    await page.waitForSelector('.tabpanel[data-k="queue"].active');
    assert.ok(await page.$('.qrow[data-id="111"][data-action="draft-reply"]'), "queued row present");
    assert.ok((await page.textContent('.qrow[data-id="111"] .qaction')).includes("Draft reply"));
    await page.click('.qrow[data-id="111"] .rm');
    await page.waitForTimeout(150);
    assert.strictEqual((await page.$$('.qrow')).length, 0, "row removed after ✕");
    assert.strictEqual(await page.textContent('.tab[data-k="queue"] .n'), "0", "count decremented");
  });

  await check("reviews split into Direct + Group zones; group chip shows; group backlog collapses", async () => {
    await page.click('.tab[data-k="reviews"]');
    await page.waitForSelector('.tabpanel[data-k="reviews"].active');
    const rp = '.tabpanel[data-k="reviews"]';
    const zones = await page.$$eval(`${rp} .zone-h`, els => els.map(e => e.textContent.replace(/\s+·.*$/, "").trim()));
    assert.deepStrictEqual(zones, ["Direct", "Group"], "Direct zone on top, Group second");
    // Direct zone card = D10; Group zone act card = D9; the group chip is shown
    assert.ok(await page.$(`${rp} .card[data-id="D10"]`), "direct review is an act card");
    const chips = await page.$$eval(`${rp} .card[data-id="D9"] .crow .chip`, els => els.map(e => e.textContent));
    assert.ok(chips.some(c => c.includes("media-playback-reviewers")), "group card shows its group chip");
    // un-analyzed reviews are shown as a VISIBLE ledger (reviews are all actionable, not hidden)
    assert.strictEqual((await page.$$(`${rp} .stale-divider`)).length, 0, "no collapse toggle for reviews");
    assert.ok(await page.isVisible(`${rp} .ledger .lrow[href*="=D11"], ${rp} .ledger .lrow`), "un-analyzed review visible in ledger");
    assert.ok((await page.textContent(`${rp} .ledger`)).includes("Old group review"), "shows the un-analyzed group review inline");
  });

  await check("my work: active zones (revise/waiting/wip) on top, parked backlog collapsed", async () => {
    await page.click('.tab[data-k="my_bugs"]');
    await page.waitForSelector('.tabpanel[data-k="my_bugs"].active');
    const mp = '.tabpanel[data-k="my_bugs"]';
    // ACTIVE: r- to revise is a card; the live review + live wip are ledger rows
    assert.ok(await page.$(`${mp} .card.mw-red[data-id="222"]`), "r- card, my court");
    assert.strictEqual(await page.$eval(`${mp} .card[data-id="222"] .pstatus`, e => e.textContent.trim()), "r- revise");
    assert.ok((await page.$eval(`${mp} .card[data-id="222"] a.pl`, e => e.href)).includes("D1222"), "patch link");
    assert.strictEqual(await page.$eval(`${mp} .lrow[href*="=225"] .pstatus`, e => e.textContent.trim()), "in review");
    assert.ok(await page.$(`${mp} .lrow[href*="=226"]`), "live wip row present");
    // a just-filed bug with no patch is active (No patch yet), not backlog
    assert.ok(await page.isVisible(`${mp} .lrow[href*="=229"]`), "no-patch-yet bug is active, visible");
    assert.ok((await page.textContent(mp)).includes("No patch yet"), "No patch yet zone shown");
    // X/Y ready count shows only for a multi-patch stack (225 = 1/2)
    assert.strictEqual(await page.$eval(`${mp} .lrow[href*="=225"] .rcount`, e => e.textContent.trim()), "1/2 r+");
    // a parked r+ (223) and a dormant review (228) are NOT active — no card, no top ledger
    assert.ok(!(await page.$(`${mp} .card[data-id="223"]`)), "parked r+ is not an active card");
    assert.ok(!(await page.isVisible(`${mp} [data-stale="mybugs-backlog"] + .stale-list .lrow`)), "backlog collapsed");
    // reveal backlog: it holds the parked r+ (with its 'r+ land it' pill), the
    // dormant review, and the no-patch assigned bug
    await page.click(`${mp} .stale-divider[data-stale="mybugs-backlog"]`);
    assert.ok(await page.isVisible(`${mp} .stale-list .lrow[href*="=223"]`), "backlog holds the parked r+");
    assert.strictEqual(await page.$eval(`${mp} .lrow[href*="=223"] .pstatus`, e => e.textContent.trim()), "r+ land it");
    assert.ok(await page.$(`${mp} .lrow[href*="=228"]`), "backlog holds the dormant review");
    assert.ok(await page.$(`${mp} .lrow[href*="=224"]`), "backlog holds the no-patch bug");
    // search filters the whole section
    await page.fill('#mbq', 'crash');
    await page.waitForTimeout(120);
    assert.ok((await page.textContent('#mb-body')).includes("222"), "search matches the crash bug");
  });

  await check("id link points at the bug and opens in a new tab", async () => {
    await page.click('.tab[data-k="needinfos"]');
    const [href, target] = await page.$eval('.card[data-id="111"] a.id', e => [e.href, e.target]);
    assert.ok(href.includes("show_bug.cgi?id=111"));
    assert.strictEqual(target, "_blank");
  });

  await browser.close();
  srv.close();
  if (failures) { console.log(`\n${failures} check(s) failed`); process.exit(1); }
  console.log("\ndashboard E2E OK — all checks pass");
}

main().catch(e => { console.error(e); process.exit(1); });
