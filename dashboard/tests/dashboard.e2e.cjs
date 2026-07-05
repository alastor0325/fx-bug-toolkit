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
      { type: "ni", id: "111", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=111",
        title: "Solvable NI", waiting_days: 3, from: "asker@example.com",
        tags: [{ text: "Audio/Video", kind: "component" }, { text: "S2", kind: "severity" }],
        brief: { bug: "what the bug is", ask: "what the ask is" },
        solvable: true, solvable_reason: "clear STR" },
    ],
    reviews: [
      { type: "review", id: "D9", url: "https://phabricator.services.mozilla.com/D9",
        title: "A review", waiting_days: 1, author: "coworker", tags: [],
        brief: { summary: "review summary" } },
    ],
    my_bugs: [
      { type: "mybug", id: "222", url: "https://bugzilla.mozilla.org/show_bug.cgi?id=222",
        title: "My bug", age_days: 2, patch_status: "needs-revision",
        tags: [{ text: "Web Audio", kind: "component" }], brief: { summary: "next step" } },
    ],
  },
};
const STATUS = { state: "ready", generated_at: DATA.generated_at, counts: { needinfos: 1, reviews: 1, my_bugs: 1 } };

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
    assert.deepStrictEqual(counts, ["1", "1", "1"]);
  });

  await check("needinfos tab is active by default; its card is visible", async () => {
    assert.ok(await page.isVisible('.tabpanel[data-k="needinfos"] .card[data-id="111"]'));
    assert.ok(!(await page.isVisible('.tabpanel[data-k="my_bugs"] .card[data-id="222"]')), "other panel hidden");
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

  await check("switching to the my-bugs tab reveals its card (patch status, display-only)", async () => {
    await page.click('.tab[data-k="my_bugs"]');
    await page.waitForSelector('.tabpanel[data-k="my_bugs"].active');
    assert.ok(await page.isVisible('.card[data-id="222"]'), "my-bug card now visible");
    const pill = await page.$eval('.card[data-id="222"] .pstatus', e => e.textContent.trim());
    assert.strictEqual(pill, "needs revision");
    await page.click('.card[data-id="222"] .chead');
    assert.strictEqual((await page.$$('.card[data-id="222"] .abtn')).length, 0, "no action buttons (MVP display-only)");
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
