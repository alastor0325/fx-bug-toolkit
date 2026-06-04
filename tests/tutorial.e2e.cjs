/* Browser E2E for the tutorial page (tutorial/tutorial.html) — covers its
 * interactive features: the foldable chapter TOC, bookmarkable chapter hashes
 * (scrollspy + anchor jumps), the click-to-enlarge lightbox, and the repo/wiki
 * links.
 *
 *   cd tests && npm install && npx playwright install chromium
 *   node tests/tutorial.e2e.cjs
 *
 * Runs all checks (a failure doesn't hide later ones); exits non-zero if any failed.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");
const { chromium } = require("playwright");

const TUT = path.join(__dirname, "..", "tutorial");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png" };

function startServer() {
  const srv = http.createServer((req, res) => {
    let u = decodeURIComponent(req.url.split("?")[0]);
    if (u === "/") u = "/tutorial.html";
    fs.readFile(path.join(TUT, u), (e, buf) => {
      if (e) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "content-type": MIME[path.extname(u)] || "application/octet-stream" });
      res.end(buf);
    });
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
  // wide viewport so the TOC is open by default
  const page = await browser.newPage({ viewport: { width: 1180, height: 840 } });
  try {
    await page.goto(`${base}/tutorial.html`);
    await page.waitForSelector("h1");

    await check("hero shows the display title", async () =>
      assert.match(await page.locator("h1").innerText(), /FX Bug Toolkit/));
    await check("TOC has all chapter links", async () =>
      assert.strictEqual(await page.locator('#toc a[href^="#"]').count(), 6));
    await check("repo link present and correct", async () =>
      assert.ok((await page.locator('#toc a.ext').getAttribute("href")).includes("alastor0325/fx-bug-toolkit")));
    await check("wiki link points at firefox-wiki-plugin", async () =>
      assert.ok((await page.locator('#wiki a[href*="firefox-wiki-plugin"]').first().getAttribute("href")).includes("firefox-wiki-plugin")));

    await check("clicking a TOC chapter sets the URL hash", async () => {
      await page.click('#toc a[href="#commands"]');
      // smooth-scroll + scrollspy settle on the target; wait for the final hash
      await page.waitForFunction(() => location.hash === "#commands", null, { timeout: 4000 });
    });
    await check("scrollspy syncs the hash to the chapter in view", async () => {
      await page.evaluate(() => document.getElementById("browse").scrollIntoView());
      await page.waitForTimeout(500);
      assert.strictEqual(await page.evaluate(() => location.hash), "#browse");
    });

    await check("TOC toggle folds and expands; stays inside the rail", async () => {
      const x = await page.locator("#tocToggle").evaluate(el => el.getBoundingClientRect().left);
      assert.ok(x < 248, `toggle should be inside the 248px rail, got ${x}`);
      const before = await page.evaluate(() => document.body.classList.contains("toc-collapsed"));
      await page.click("#tocToggle");
      assert.notStrictEqual(await page.evaluate(() => document.body.classList.contains("toc-collapsed")), before);
      await page.click("#tocToggle"); // restore
    });

    await check("lightbox opens on image click", async () => {
      await page.locator("figure img").scrollIntoViewIfNeeded();
      await page.locator("figure img").click();
      await page.waitForTimeout(350);
      assert.strictEqual(await page.locator("#lightbox.open").count(), 1);
    });
    await check("lightbox closes on backdrop click", async () => {
      await page.mouse.click(15, 15);
      await page.waitForTimeout(350);
      assert.strictEqual(await page.locator("#lightbox.open").count(), 0);
    });
    await check("lightbox closes on Escape", async () => {
      await page.locator("figure img").click();
      await page.waitForTimeout(200);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
      assert.strictEqual(await page.locator("#lightbox.open").count(), 0);
    });
  } finally {
    await browser.close();
    srv.close();
  }
  console.log(failures ? `\nTUTORIAL E2E FAIL — ${failures} check(s) failed` : "\nTUTORIAL E2E OK — all checks pass");
  process.exit(failures ? 1 : 0);
}

main();
