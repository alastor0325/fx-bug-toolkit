/* Capture a screenshot of the viewer for the tutorial. The FEATURED (selected)
 * item is a REAL, public, non-security investigation (Bug 2044320), read from
 * tutorial/example/. The other list rows are plausible fakes for context.
 * Not a test, not committed — a doc asset generator.
 *   NODE_PATH=<playwright> node tutorial/shoot.cjs
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const VIEWER = path.join(__dirname, "..", "viewer");
const OUT = path.join(__dirname, "assets");
fs.mkdirSync(OUT, { recursive: true });
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml" };

// real example: take the body after the YAML frontmatter
const exampleRaw = fs.readFileSync(path.join(__dirname, "example", "bug-2044320-investigation.md"), "utf8");
const exampleBody = exampleRaw.slice(exampleRaw.indexOf("\n---", 4) + 4).replace(/^\n+/, "");

const featured = {
  bug_id: 2044320, bug_url: "https://bugzilla.mozilla.org/show_bug.cgi?id=2044320", folder: null,
  summary: "MP4 with two adjacent colr boxes fails to parse — an mp4parse strictness regression that also breaks animated AVIF",
  status: "investigated", depth: "deep", complexity: "low",
  root_cause: "A second colr box in a video sample entry makes mp4parse hard-fail under Normal strictness (ColrBadQuantityBMFF), aborting the whole metadata parse — ISO 14496-12 §12.1.5 explicitly permits more than one.",
  affected_files: ["third_party/rust/mp4parse/src/lib.rs#L5773-L5787", "dom/media/mp4/MP4Metadata.cpp#L98-L107"],
  related_bugs: [2044532, 2030296, 1729071], investigated_at: "2026-06-02T00:00:00Z",
  has_frontmatter: true, date: "2026-06-02", body: exampleBody,
};

const fakes = [
  { bug_id: 1898555, bug_url: "https://bugzilla.mozilla.org/show_bug.cgi?id=1898555", folder: "hdr-windows",
    summary: "HEVC hardware decode silently falls back to software on some Intel GPUs", depth: "deep",
    complexity: "high", root_cause: null, affected_files: [], related_bugs: [], has_frontmatter: true,
    date: "2026-05-30", body: "# Bug 1898555\n" },
  { bug_id: "mfcdm-terminated", bug_url: null, folder: "mf-playback",
    summary: "CDM process termination is not surfaced to active MediaKeySession objects", depth: "triage",
    complexity: null, root_cause: null, affected_files: [], related_bugs: [], has_frontmatter: false,
    date: "2026-05-28", body: "# Investigation\n" },
  { bug_id: 1897777, bug_url: "https://bugzilla.mozilla.org/show_bug.cgi?id=1897777", folder: null,
    summary: "Seamless-looping seek asserts on duration mismatch at end of media", depth: "deep",
    complexity: "low", root_cause: null, affected_files: [], related_bugs: [], has_frontmatter: true,
    date: "2026-05-26", body: "# Bug 1897777\n" },
  { bug_id: "audio-session-plan", bug_url: null, folder: "media-controller",
    summary: "Platform audio-session integration: scope and rollout plan", depth: null, complexity: null,
    root_cause: null, affected_files: [], related_bugs: [], has_frontmatter: false,
    date: "2026-05-20", body: "# Audio Session API Implementation Plan\n" },
];

const INDEX = [featured, ...fakes];

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

(async () => {
  const { srv, port } = await startServer();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1320, height: 840 }, deviceScaleFactor: 2 });
  await page.goto(`http://127.0.0.1:${port}/viewer.html#2044320`);
  await page.waitForSelector(".row.sel");
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, "viewer.png") });
  console.log("wrote", path.join(OUT, "viewer.png"));
  await browser.close();
  srv.close();
})();
