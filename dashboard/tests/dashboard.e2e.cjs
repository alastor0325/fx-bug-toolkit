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
      { type: "review", id: "D9", url: "https://phabricator.services.mozilla.com/D9",
        title: "A review", waiting_days: 1, author: "coworker", tags: [],
        brief: { summary: "review summary" } },
    ],
    my_bugs: [
      { type: "mybug", id: "222", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=222",
        title: "My crash bug", age_days: 2, patch_status: "needs-revision",
        tags: [{ text: "Playback", kind: "component" }], brief: null },
      { type: "mybug", id: "223", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=223",
        title: "Audio thing", age_days: 5, patch_status: "accepted",
        tags: [{ text: "Web Audio", kind: "component" }], brief: null },
    ],
  },
};
const STATUS = { state: "ready", generated_at: DATA.generated_at, counts: { needinfos: 3, reviews: 1, my_bugs: 2 } };

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
    if (req.method === "POST" && url === "/queue") {
      let body = "";
      req.on("data", c => (body += c));
      req.on("end", () => {
        posted.push(JSON.parse(body || "{}"));
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

  await check("three section tabs render with counts", async () => {
    const labels = await page.$$eval(".tab", els => els.map(e => e.textContent.replace(/\d+$/, "").trim()));
    assert.deepStrictEqual(labels, ["Needinfos", "Review requests", "Bugs I'm working on"]);
    const counts = await page.$$eval(".tab .n", els => els.map(e => e.textContent));
    assert.deepStrictEqual(counts, ["3", "1", "2"]);
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

  await check("reviews render expanded by default", async () => {
    await page.click('.tab[data-k="reviews"]');
    await page.waitForSelector('.tabpanel[data-k="reviews"].active');
    assert.ok(await page.isVisible('.card[data-id="D9"].open'), "review card open by default");
    assert.ok((await page.textContent('.card[data-id="D9"] .cbody')).includes("review summary"));
  });

  await check("my-bugs is a searchable ledger (rows, not cards; display-only)", async () => {
    await page.click('.tab[data-k="my_bugs"]');
    await page.waitForSelector('.tabpanel[data-k="my_bugs"].active');
    assert.strictEqual((await page.$$('.tabpanel[data-k="my_bugs"] .card')).length, 0, "no cards");
    const rows = await page.$$eval('#mb-ledger .lrow', els => els.map(r => r.dataset ? r.getAttribute('href') : ''));
    assert.strictEqual(rows.length, 2, "two ledger rows");
    const pill = await page.$eval('.lrow[href*="=222"] .pstatus', e => e.textContent.trim());
    assert.strictEqual(pill, "needs revision");
    // search filters the ledger in place
    await page.fill('#mbq', 'audio');
    await page.waitForTimeout(120);
    const after = await page.$$eval('#mb-ledger .lrow', els => els.map(r => r.getAttribute('href')));
    assert.strictEqual(after.length, 1, "search narrows to 1");
    assert.ok(after[0].includes("=223"), "matched the Audio bug");
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
