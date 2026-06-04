/* Full-chain integration test: the SHIPPED serve.py launcher builds the index
 * from real investigation markdown and serves the real viewer assets, and a real
 * browser (Playwright) loads the served page and drives it.
 *
 * This is the gap the other suites don't cover:
 *   - viewer.e2e.cjs serves assets from a throwaway Node http server (not serve.py)
 *   - test_serve.py drives the real serve.py but with NO browser
 * Here the whole chain runs: serve.py start -> build_index.py -> HTTP -> browser.
 *
 * Self-contained + isolated: copies the viewer into a temp dir, builds from a
 * temp investigation dir, serves on a free port, tears everything down.
 *
 *   npm install && npx playwright install chromium   (from the repo root)
 *   node viewer/tests/viewer.serve.e2e.cjs        (needs python3 + pyyaml)
 *
 * Runs all checks (a failure doesn't hide later ones); exits non-zero if any failed.
 */
const http = require("node:http");
const fs = require("node:fs");
const os = require("node:os");
const net = require("node:net");
const path = require("node:path");
const assert = require("node:assert");
const { spawnSync } = require("node:child_process");
const { chromium } = require("playwright");

const VIEWER = path.join(__dirname, "..");  // viewer/tests -> viewer/
// everything serve.py needs to build + serve from an isolated copy
const LAUNCHER_FILES = ["viewer.html", "viewer.logic.js", "marked.min.js", "favicon.svg", "serve.py", "build_index.py"];

function pythonExe() {
  for (const c of ["python3", "python"]) {
    if (spawnSync(c, ["--version"], { stdio: "ignore" }).status === 0) return c;
  }
  throw new Error("no python3/python on PATH");
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function get(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, res => {
      let buf = "";
      res.on("data", d => (buf += d));
      res.on("end", () => resolve({ status: res.statusCode, body: buf }));
    });
    req.on("error", reject);
    req.setTimeout(3000, () => req.destroy(new Error("timeout")));
  });
}

async function waitUp(base, tries = 100) {
  for (let i = 0; i < tries; i++) {
    try { if ((await get(base + "/viewer.html")).status === 200) return; } catch { /* not up yet */ }
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error("serve.py did not come up");
}

let failures = 0;
async function check(name, fn) {
  try { await fn(); console.log("  ok   -", name); }
  catch (e) { failures++; console.log("FAIL   -", name, "::", e.message); }
}

async function main() {
  const PY = pythonExe();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fx-serve-e2e-"));
  const web = path.join(tmp, "web");
  const inv = path.join(tmp, "inv");
  fs.mkdirSync(web);
  fs.mkdirSync(inv);
  for (const f of LAUNCHER_FILES) fs.copyFileSync(path.join(VIEWER, f), path.join(web, f));

  // two real investigation files — build_index.py parses their frontmatter
  fs.writeFileSync(path.join(inv, "bug-700001-investigation.md"),
    "---\nbug_id: 700001\nsummary: Served headline\ndepth: deep\ncomplexity: high\n" +
    "root_cause: the served root cause\naffected_files:\n  - dom/media/Foo.cpp#L10-L12\n---\n" +
    "# Heading\n\nbody **text**\n");
  fs.writeFileSync(path.join(inv, "bug-800002-investigation.md"),
    "---\nbug_id: 800002\nsummary: Second served bug\n---\n# Second\n\nmore body\n");

  const port = await freePort();
  const serve = path.join(web, "serve.py");
  const env = { ...process.env, FX_BUG_INVESTIGATION_DIR: inv, FX_VIEWER_PORT: String(port) };
  const base = `http://127.0.0.1:${port}`;

  // start the REAL launcher — it runs build_index.py then serves detached
  const started = spawnSync(PY, [serve, "start"], { env, encoding: "utf-8" });
  assert.strictEqual(started.status, 0, "serve.py start failed: " + (started.stderr || started.stdout));

  let browser;
  try {
    await waitUp(base);

    // index.json is produced by the real build_index.py and served by serve.py
    await check("serve.py built + served index.json from the .md files", async () => {
      const r = await get(base + "/index.json");
      assert.strictEqual(r.status, 200, "index.json status");
      const data = JSON.parse(r.body);
      assert.strictEqual(data.length, 2, "two investigations indexed");
      assert.ok(data.some(d => d.bug_id === 700001 && d.summary === "Served headline"),
        "700001 summary parsed from frontmatter");
    });
    await check("serve.py serves the viewer assets", async () => {
      for (const a of ["viewer.html", "viewer.logic.js", "marked.min.js", "favicon.svg"]) {
        assert.strictEqual((await get(`${base}/${a}`)).status, 200, a);
      }
    });

    browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto(base + "/viewer.html");
    await page.waitForSelector(".row, .railempty");

    await check("browser renders both investigations from the live index", async () =>
      assert.strictEqual(await page.locator(".row").count(), 2));
    await check("search narrows the live-served list", async () => {
      await page.fill("#q", "Second");
      assert.strictEqual(await page.locator(".row").count(), 1);
    });
    await check("clearing search restores both rows", async () => {
      await page.fill("#q", "");
      assert.strictEqual(await page.locator(".row").count(), 2);
    });
    await check("click opens detail with heading + root cause from frontmatter", async () => {
      await page.locator(".row", { hasText: "Served headline" }).first().click();
      await page.waitForSelector(".dochead h1");
      assert.match(await page.locator(".dochead h1").innerText(), /Served headline/);
      assert.match(await page.locator(".rootcause").innerText(), /served root cause/i);
    });
  } finally {
    if (browser) await browser.close();
    spawnSync(PY, [serve, "stop"], { env, stdio: "ignore" });
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  console.log(failures ? `\n${failures} check(s) failed` : "\nall serve-e2e checks passed");
  process.exit(failures ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
