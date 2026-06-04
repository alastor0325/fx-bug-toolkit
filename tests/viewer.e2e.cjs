/* Browser E2E for the viewer's DOM behaviour (render / search / select /
 * deep-link / keyboard / fold) — the parts unit tests can't reach.
 *
 * Self-contained: builds a fixture index, serves the real viewer assets on an
 * ephemeral port, drives a real browser, asserts, tears down.
 *
 *   cd tests && npm install && npx playwright install chromium
 *   node tests/viewer.e2e.cjs
 *
 * Exits non-zero on the first failed assertion.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");
const { chromium } = require("playwright");

const VIEWER = path.join(__dirname, "..", "viewer");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml" };

const INDEX = [
  { bug_id: 700001, bug_url: "https://bugzilla.mozilla.org/show_bug.cgi?id=700001",
    folder: null, summary: "Numbered headline", status: null, depth: "deep", complexity: "high",
    root_cause: "the numbered root cause", affected_files: ["dom/media/Foo.cpp#L10-L12"],
    related_bugs: [222], investigated_at: "2026-01-01T00:00:00Z", notes: null,
    has_frontmatter: true, date: "2026-01-01", body: "# Heading\n\nsome **body** with `code`\n" },
  { bug_id: "mfcdm-thing", bug_url: null, folder: "mf-playback", summary: "MFCDM Thing slug",
    status: null, depth: null, complexity: null, root_cause: null, affected_files: [],
    related_bugs: [], investigated_at: null, notes: null, has_frontmatter: false,
    date: "2020-01-01", body: "# Investigation: MFCDM Thing\n\nslug body\n" },
];

function startServer() {
  const files = {
    "/viewer.html": fs.readFileSync(path.join(VIEWER, "viewer.html")),
    "/viewer.logic.js": fs.readFileSync(path.join(VIEWER, "viewer.logic.js")),
    "/marked.min.js": fs.readFileSync(path.join(VIEWER, "marked.min.js")),
    "/favicon.svg": fs.readFileSync(path.join(VIEWER, "favicon.svg")),
    "/index.json": Buffer.from(JSON.stringify(INDEX)),
  };
  const srv = http.createServer((req, res) => {
    const url = req.url.split("?")[0];
    const buf = files[url];
    if (!buf) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": MIME[path.extname(url)] || "text/plain" });
    res.end(buf);
  });
  return new Promise(r => srv.listen(0, "127.0.0.1", () => r({ srv, port: srv.address().port })));
}

async function main() {
  const { srv, port } = await startServer();
  const base = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  let failed = false;
  try {
    await page.goto(`${base}/viewer.html`);
    await page.waitForSelector(".row");

    // 1) renders both fixture rows, newest first
    assert.strictEqual(await page.locator(".row").count(), 2, "two rows render");
    assert.match(await page.locator(".row").first().innerText(), /Numbered headline/, "newest first");

    // 2) search filters, clearing restores
    await page.fill("#q", "slug");
    assert.strictEqual(await page.locator(".row").count(), 1, "search narrows to 1");
    await page.fill("#q", "");
    assert.strictEqual(await page.locator(".row").count(), 2, "clearing search restores");

    // 3) click selects + detail renders (heading, root cause, bugzilla link, rendered md)
    await page.locator(".row").first().click();
    assert.match(await page.locator(".dochead h1").innerText(), /Numbered headline/, "detail heading");
    assert.match(await page.locator(".rootcause").innerText(), /numbered root cause/, "root cause shown");
    const href = await page.locator(".dochead .id a").getAttribute("href");
    assert.ok(href.endsWith("=700001"), "bugzilla link");
    assert.strictEqual(await page.locator(".body strong").innerText(), "body", "markdown rendered");

    // 4) deep-link by hash selects the right (slug) item, no bugzilla link
    await page.goto(`${base}/viewer.html#mfcdm-thing`);
    await page.waitForSelector(".row.sel");
    assert.match(await page.locator(".row.sel").innerText(), /MFCDM Thing slug/, "deep-link selects slug item");
    assert.strictEqual(await page.locator(".dochead .id a").count(), 0, "slug item has no bugzilla link");

    // 5) keyboard: 's' down, 'w' up
    await page.goto(`${base}/viewer.html`);
    await page.waitForSelector(".row");
    await page.keyboard.press("s");
    assert.strictEqual(await page.locator(".row.sel").count(), 1, "'s' selects a row");
    const firstSel = await page.locator(".row.sel").innerText();
    await page.keyboard.press("s");
    assert.notStrictEqual(await page.locator(".row.sel").innerText(), firstSel, "'s' again moves down");
    await page.keyboard.press("w");
    assert.strictEqual(await page.locator(".row.sel").innerText(), firstSel, "'w' moves back up");

    // 6) fold the sidebar with 'b'
    await page.keyboard.press("b");
    assert.ok(await page.evaluate(() => document.querySelector("main").classList.contains("collapsed")),
      "'b' folds the list");

    console.log("E2E OK — all viewer DOM checks passed");
  } catch (e) {
    failed = true;
    console.error("E2E FAIL:", e.message);
  } finally {
    await browser.close();
    srv.close();
  }
  process.exit(failed ? 1 : 0);
}

main();
