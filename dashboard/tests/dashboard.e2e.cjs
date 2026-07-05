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
      // active (open patch) → In-progress zone, most-recent first
      { type: "mybug", id: "222", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=222",
        title: "My crash bug", last_activity_days: 1, patch_status: "needs-revision",
        tags: [{ text: "Playback", kind: "component" }], brief: null },
      { type: "mybug", id: "223", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=223",
        title: "Audio thing", last_activity_days: 5, patch_status: "accepted",
        tags: [{ text: "Web Audio", kind: "component" }], brief: null },
      // no patch → collapsed backlog
      { type: "mybug", id: "224", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=224",
        title: "Old assigned bug", last_activity_days: 200, patch_status: "none",
        tags: [{ text: "Playback", kind: "component" }], brief: null },
    ],
  },
};
const STATUS = { state: "ready", generated_at: DATA.generated_at, counts: { needinfos: 3, reviews: 3, my_bugs: 3 } };

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
    assert.deepStrictEqual(counts, ["3", "3", "3", "0"]);  // queue empty at start
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

  await check("my work: In-progress focus (recent first) + collapsed backlog; searchable", async () => {
    await page.click('.tab[data-k="my_bugs"]');
    await page.waitForSelector('.tabpanel[data-k="my_bugs"].active');
    const mp = '.tabpanel[data-k="my_bugs"]';
    assert.strictEqual((await page.$$(`${mp} .cards .card`)).length, 0, "display-only, no cards");
    assert.ok((await page.textContent(`${mp} .zone-h`)).includes("In progress"), "In-progress zone");
    // active bugs (open patch) listed most-recent first (222 @1d before 223 @5d)
    const active = await page.$$eval(`${mp} .ledger .lrow`, els => els.map(r => r.getAttribute('href')));
    assert.ok(active[0].includes("=222") && active.some(h => h.includes("=223")), "active bugs, recent first");
    assert.strictEqual(await page.$eval(`${mp} .lrow[href*="=222"] .pstatus`, e => e.textContent.trim()), "needs revision");
    // backlog (no patch) is collapsed
    assert.ok(!(await page.isVisible(`${mp} .stale-list .lrow`)), "backlog collapsed");
    await page.click(`${mp} .stale-divider`);
    assert.ok((await page.textContent(`${mp} .stale-list`)).includes("224"), "backlog reveals 224");
    // search filters the whole section
    await page.fill('#mbq', 'audio');
    await page.waitForTimeout(120);
    assert.ok((await page.textContent('#mb-body')).includes("223"), "search matches the Audio bug");
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
