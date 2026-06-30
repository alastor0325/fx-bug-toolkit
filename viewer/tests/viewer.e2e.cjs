/* Browser E2E for the viewer's DOM behaviour — aims to cover EVERY feature the
 * page exposes (the parts unit tests can't reach).
 *
 * Self-contained: builds a fixture index, serves the real viewer assets on an
 * ephemeral port, drives a real browser, asserts every feature, tears down.
 *
 *   npm install && npx playwright install chromium   (from the repo root)
 *   node viewer/tests/viewer.e2e.cjs
 *
 * Runs all checks (a failure doesn't hide later ones); exits non-zero if any failed.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");
const { chromium } = require("playwright");

const VIEWER = path.join(__dirname, "..");  // viewer/tests -> viewer/
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml" };

const INDEX = [
  { bug_id: 700001, bug_url: "https://bugzilla.mozilla.org/show_bug.cgi?id=700001",
    folder: null, summary: "Numbered headline", status: null, depth: "deep", complexity: "high", security: true,
    root_cause: "the numbered root cause", affected_files: ["dom/media/Foo.cpp#L10-L12"],
    related_bugs: [222], investigated_at: "2026-01-01T00:00:00Z", notes: null,
    has_frontmatter: true, date: "2026-01-01",
    // body is deliberately tall (many paragraphs) so the detail pane actually
    // scrolls — the scroll-restoration checks below need a real scroll offset.
    body: "# Heading\n\nsome **body** with `code` and a [spec link](https://example.com/spec)\n\n"
      + Array.from({ length: 60 }, (_, i) =>
          `Filler paragraph ${i} — lorem ipsum dolor sit amet, long enough that the detail pane scrolls well past one screen so a restored scroll offset is observable.`
        ).join("\n\n") + "\n" },
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

  const reload = async (hash = "") => { await page.goto(`${base}/viewer.html${hash}`); await page.waitForSelector(".row, .railempty"); };

  try {
    await reload();

    await check("renders all rows", async () =>
      assert.strictEqual(await page.locator(".row").count(), 2));
    await check("sorted newest-first by default", async () =>
      assert.match(await page.locator(".row").first().innerText(), /Numbered headline/));
    await check("result count shows N / total", async () =>
      assert.match(await page.locator("#count").innerText(), /2\s*\/\s*2/));

    // chips
    // chips are uppercased via CSS, so innerText is FULL/HIGH — match case-insensitively
    await check("depth chip shows plain 'full' for deep", async () =>
      assert.match(await page.locator(".row").first().locator(".chip.depth-deep").innerText(), /full/i));
    await check("complexity is NOT shown on list rows", async () =>
      assert.strictEqual(await page.locator(".row .chip[class*='cx-']").count(), 0));
    await check("SECURITY chip shows on the security-bug row", async () => {
      assert.strictEqual(await page.locator(".row").first().locator(".chip.security").count(), 1);
      assert.match(await page.locator(".row").first().locator(".chip.security").innerText(), /security/i);
    });
    await check("no SECURITY chip on a non-security row", async () =>
      assert.strictEqual(await page.locator(".row.sparse .chip.security").count(), 0));
    await check("folder chip on the slug row", async () =>
      assert.match(await page.locator(".row.sparse").innerText(), /mf-playback/));
    await check("sparse row class for no-frontmatter file", async () =>
      assert.strictEqual(await page.locator(".row.sparse").count(), 1));

    // search
    await check("search narrows results", async () => {
      await page.fill("#q", "slug");
      assert.strictEqual(await page.locator(".row").count(), 1);
      assert.match(await page.locator("#count").innerText(), /1\s*\/\s*2/);
    });
    await check("no-match search shows empty state", async () => {
      await page.fill("#q", "zzz-nope-zzz");
      assert.strictEqual(await page.locator(".row").count(), 0);
      assert.match(await page.locator(".railempty").innerText(), /no matches/i);
    });
    await check("clearing search restores all", async () => {
      await page.fill("#q", "");
      assert.strictEqual(await page.locator(".row").count(), 2);
    });

    // sort toggle
    await check("sort toggle flips order + label", async () => {
      assert.match(await page.locator("#sort").innerText(), /newest/);
      await page.click("#sort");
      assert.match(await page.locator("#sort").innerText(), /oldest/);
      assert.match(await page.locator(".row").first().innerText(), /MFCDM Thing slug/);
      await page.click("#sort"); // back to newest
      assert.match(await page.locator(".row").first().innerText(), /Numbered headline/);
    });

    // detail pane
    await check("click selects + detail heading", async () => {
      await page.locator(".row").first().click();
      assert.match(await page.locator(".dochead h1").innerText(), /Numbered headline/);
    });
    await check("root cause block", async () =>
      assert.match(await page.locator(".rootcause").innerText(), /numbered root cause/));
    await check("complexity IS shown in the detail meta (moved off the row)", async () =>
      assert.match(await page.locator(".meta .chip.cx-high").innerText(), /high/i));
    await check("SECURITY chip in the detail meta", async () =>
      assert.strictEqual(await page.locator(".meta .chip.security").count(), 1));
    await check("bugzilla link in detail", async () =>
      assert.ok((await page.locator(".dochead .id a").getAttribute("href")).endsWith("=700001")));
    await check("affected-file searchfox link (L stripped from anchor)", async () => {
      const href = await page.locator(".files a").first().getAttribute("href");
      assert.ok(href.endsWith("/dom/media/Foo.cpp#10-12"), href);
    });
    await check("related-bug bugzilla chip", async () => {
      const href = await page.locator(".meta a").first().getAttribute("href");
      assert.ok(href.endsWith("=222"), href);
    });
    await check("markdown rendered (bold)", async () =>
      assert.strictEqual(await page.locator(".body strong").innerText(), "body"));
    await check("markdown link opens in new tab", async () => {
      const a = page.locator('.body a[href="https://example.com/spec"]');
      assert.strictEqual(await a.getAttribute("target"), "_blank");
    });
    await check("selecting updates the URL hash", async () =>
      assert.strictEqual(await page.evaluate(() => location.hash), "#700001"));

    // deep-link (fresh load)
    await check("deep-link by hash selects the slug item", async () => {
      await reload("#mfcdm-thing");
      await page.waitForSelector(".row.sel");
      assert.match(await page.locator(".row.sel").innerText(), /MFCDM Thing slug/);
    });
    await check("slug item has no bugzilla link", async () =>
      assert.strictEqual(await page.locator(".dochead .id a").count(), 0));

    // hashchange on an already-open page
    await check("hashchange on open page re-selects", async () => {
      await page.evaluate(() => { location.hash = "#700001"; });
      await page.waitForFunction(() => /Numbered headline/.test(document.querySelector(".row.sel")?.innerText || ""));
    });

    // keyboard
    await reload();
    await check("'/' focuses search, Esc clears + blurs", async () => {
      await page.keyboard.press("/");
      assert.ok(await page.evaluate(() => document.activeElement === document.querySelector("#q")));
      await page.fill("#q", "slug");
      await page.keyboard.press("Escape");
      assert.strictEqual(await page.inputValue("#q"), "");
      assert.ok(await page.evaluate(() => document.activeElement !== document.querySelector("#q")));
    });
    await check("'s'/'w' navigate down/up", async () => {
      await page.keyboard.press("s");
      const first = await page.locator(".row.sel").innerText();
      await page.keyboard.press("s");
      assert.notStrictEqual(await page.locator(".row.sel").innerText(), first);
      await page.keyboard.press("w");
      assert.strictEqual(await page.locator(".row.sel").innerText(), first);
    });
    await check("'j'/'k' also navigate", async () => {
      await page.keyboard.press("j");
      assert.strictEqual(await page.locator(".row.sel").count(), 1);
    });

    // sidebar fold: key 'b', key '\', and the toggle button
    const collapsed = () => page.evaluate(() => document.querySelector("main").classList.contains("collapsed"));
    await check("'b' folds and expands", async () => {
      await page.keyboard.press("b"); assert.ok(await collapsed());
      await page.keyboard.press("b"); assert.ok(!(await collapsed()));
    });
    await check("'\\' folds", async () => {
      await page.keyboard.press("\\"); assert.ok(await collapsed());
      await page.keyboard.press("\\"); assert.ok(!(await collapsed()));
    });
    await check("toggle button folds", async () => {
      await page.click("#toggle"); assert.ok(await collapsed());
      await page.click("#toggle"); assert.ok(!(await collapsed()));
    });

    // fix #2 — the open/closed state survives a browser reload
    await check("sidebar collapsed state persists across reload", async () => {
      await page.evaluate(() => localStorage.clear());
      await reload();
      assert.ok(!(await collapsed()), "fresh load is expanded by default");
      await page.click("#toggle");                 // collapse
      assert.ok(await collapsed());
      await reload();                              // browser refresh
      assert.ok(await collapsed(), "stays collapsed after reload");
    });

    // fix #3 — when collapsed, search surfaces a results dropdown you can click
    await check("collapsed search shows a results dropdown; click navigates", async () => {
      // (still collapsed from the previous check)
      await page.fill("#q", "Numbered");
      await page.waitForSelector("#results:not([hidden]) .res");
      assert.ok((await page.locator("#results .res").count()) >= 1);
      await page.locator("#results .res").first().click();
      assert.match(await page.locator(".dochead h1").innerText(), /Numbered headline/);
      assert.ok(await page.locator("#results").evaluate(el => el.hidden), "dropdown hides after a pick");
    });
    await check("dropdown stays hidden when the sidebar is expanded", async () => {
      await page.evaluate(() => localStorage.clear());
      await reload();                              // expanded (default)
      await page.fill("#q", "Numbered");
      assert.ok(await page.locator("#results").evaluate(el => el.hidden), "no dropdown while the list is visible");
    });

    // the reported bug: returning to the tab (visibilitychange/focus → background
    // refresh) re-selects the OPEN doc. On an UNCHANGED doc the detail pane must
    // be left completely untouched — not re-rendered then scroll-restored, which
    // lost the position in real-browser timing. So: scroll preserved AND the
    // rendered <article> node is the SAME node (no innerHTML rewrite at all).
    await check("background refresh leaves the open doc untouched (scroll kept, no re-render)", async () => {
      await page.evaluate(() => localStorage.clear());
      await reload();
      await page.locator(".row").first().click();                       // open the tall doc
      await page.locator("#detail").evaluate(el => { el.scrollTop = 400; });
      const before = await page.locator("#detail").evaluate(el => {
        el.querySelector(".doc").dataset.tag = "before";               // tag the node to detect a rewrite
        return el.scrollTop;
      });
      assert.ok(before > 0, "precondition: the detail pane is scrolled down");
      await page.evaluate(() => loadIndex());                           // the refresh path: re-fetch + re-select the same (unchanged) doc
      const after = await page.locator("#detail").evaluate(el => el.scrollTop);
      const sameNode = await page.locator("#detail").evaluate(el => el.querySelector(".doc")?.dataset.tag === "before");
      assert.strictEqual(after, before, "scroll position kept across the refresh");
      assert.ok(sameNode, "unchanged open doc was NOT re-rendered (same <article> node survived)");
    });
    await check("scroll resets to top when switching to a different doc", async () => {
      await page.locator("#detail").evaluate(el => { el.scrollTop = 400; });
      await page.locator(".row").nth(1).click();                        // a different doc
      assert.strictEqual(await page.locator("#detail").evaluate(el => el.scrollTop), 0, "switching docs scrolls to top");
    });

  } finally {
    await browser.close();
    srv.close();
  }
  console.log(failures ? `\nE2E FAIL — ${failures} check(s) failed` : "\nE2E OK — all viewer features pass");
  process.exit(failures ? 1 : 0);
}

main();
