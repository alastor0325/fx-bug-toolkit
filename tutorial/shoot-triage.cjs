/* Capture a screenshot of the TRIAGE DASHBOARD for the tutorial. The dashboard
 * is the separate firefox-triage-dashboard pip app (installed in the managed
 * venv at ~/.fx-bug-toolkit/venv by /triage-dashboard). We never screenshot a
 * real triage dir — it can hold private/security bugs and the owner's email.
 * Instead we point the dashboard at a TEMP dir of SYNTHETIC, public-bug-only
 * drafts (the featured card is the same real, public Bug 2044320 the viewer
 * tutorial uses; the rest are plausible public fakes for context).
 * Not a test, not committed output — a doc-asset generator like shoot.cjs.
 *   NODE_PATH=<playwright> node tutorial/shoot-triage.cjs
 */
const fs = require("node:fs");
const os = require("node:os");
const net = require("node:net");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");

const OUT = path.join(__dirname, "assets");
fs.mkdirSync(OUT, { recursive: true });

// ---- locate the dashboard CLI inside the managed venv ----------------------
const VENV = path.join(os.homedir(), ".fx-bug-toolkit", "venv");
const BIN = fs.existsSync(path.join(VENV, "bin")) ? path.join(VENV, "bin")
                                                  : path.join(VENV, "Scripts");
const EXE = path.join(BIN, process.platform === "win32" ? "triage-dashboard.exe"
                                                        : "triage-dashboard");
if (!fs.existsSync(EXE)) {
  console.error(`triage-dashboard not found at ${EXE}\n` +
    "Install it first: run /triage-dashboard in a Claude session (or pip install " +
    "the pinned release into ~/.fx-bug-toolkit/venv). Skipping screenshot.");
  process.exit(0);
}

// ---- synthetic, public-only fixture ---------------------------------------
// Dates are relative to "now" so the "New" tag (filed ≤ 7 days) stays accurate
// whenever the asset is regenerated.
const DAY = 86400000;
const iso = (daysAgo) => new Date(Date.now() - daysAgo * DAY).toISOString();

// The featured card: the real, public Bug 2044320 (Audio/Video: Playback),
// the same one the viewer tutorial features. Rich context so the card is full.
const featured = {
  bug_id: 2044320,
  title: "MP4 with two adjacent colr boxes fails to parse",
  bug_component: "Audio/Video: Playback",
  severity: "S3", priority: "P2",                 // proposed → §1b "Analyzed"
  keywords_add: ["regression"],
  blocks_add: [], cc_add: [], ni_targets: [], resolution: null,
  product: null, component: null, regressed_by_add: [2030296],
  status: null, assigned_to: null, created_at: iso(2),
  comment:
    "Triaged as **S3 / P2**.\n\n" +
    "Root-caused: a second `colr` box in a video sample entry makes mp4parse " +
    "hard-fail under Normal strictness (`ColrBadQuantityBMFF`), aborting the " +
    "whole metadata parse — but ISO/IEC 14496-12 §12.1.5 explicitly permits " +
    "more than one. The same strictness regression also breaks animated AVIF.\n\n" +
    "Marking as a regression (see regressor below); fix is to downgrade the " +
    "duplicate-`colr` case to a warning.",
  bug_context: {
    description_excerpt:
      "Some MP4 files with two adjacent colr boxes fail to play.\n\n" +
      "Steps to reproduce:\n1. Open the attached sample.mp4 in Firefox.\n" +
      "2. Observe the video never starts.\n\n" +
      "Actual: playback fails, console shows a metadata parse error.\n" +
      "Expected: the video plays (it plays in other browsers).",
    platform: "All", firefox_version: "Nightly 153.0a1",
    reporter_name: "A. Reporter", reporter_email: "reporter@example.com",
    filed: iso(2), last_activity: iso(1),
    affected_versions: "all",
    inventory_present: ["Reduced test case (sample.mp4)", "Console error",
                        "Affected versions"],
    inventory_missing: [],
    current_severity: "", current_priority: "",   // no P/S yet → triage sets it
    keywords: [],
    see_also: [
      { bug_id: 2030296, label: "regressed by" },
      { bug_id: 2044532, label: "duplicate-ish" },
      { bug_id: 1729071, label: "similar" },
    ],
    recent_comments: [
      { author: "reporter@example.com", ts: iso(2),
        text: "Attaching a minimal sample.mp4 that reproduces the failure." },
    ],
    attachments: [
      { name: "sample.mp4", url: "https://bugzilla.mozilla.org/attachment.cgi?id=1",
        content_type: "video/mp4" },
    ],
    ai_reasoning:
      "The regressor 2030296 tightened colr-box quantity validation. Per " +
      "ISO/IEC 14496-12 the box may repeat, so Normal strictness should warn, " +
      "not fail. S3 (no crash, specific files) / P2 (clear regression, has fix).",
  },
};

// Plausible PUBLIC fakes that fill the rail and the other tabs.
const analyzed = [
  {
    bug_id: 1899210, title: "Web Audio: AudioWorklet glitches when the buffer size changes mid-stream",
    bug_component: "Web Audio", severity: "S3", priority: "P3", created_at: iso(5),
    keywords_add: [], blocks_add: [], cc_add: [], ni_targets: [], resolution: null,
    product: null, component: null, regressed_by_add: [], status: null, assigned_to: null,
    comment: "Triaged **S3 / P3** — audible but intermittent; needs a stable repro for a fix.",
    bug_context: { platform: "Windows", firefox_version: "152.0", filed: iso(5),
      last_activity: iso(3), affected_versions: "151+", current_severity: "", current_priority: "",
      keywords: [], inventory_present: ["Repro steps"], inventory_missing: ["Profiler capture"],
      reporter_name: "B. Tester", see_also: [], recent_comments: [], attachments: [] },
  },
  {
    bug_id: 1900145, title: "HEVC hardware decode silently falls back to software on some Intel GPUs",
    bug_component: "Audio/Video: Playback", severity: "S2", priority: "P2", created_at: iso(10),
    keywords_add: [], blocks_add: [], cc_add: [], ni_targets: [], resolution: null,
    product: null, component: null, regressed_by_add: [], status: null,
    assigned_to: "dev@mozilla.example",
    comment: "Triaged **S2 / P2** — performance regression on a common config; assigned.",
    bug_context: { platform: "Windows", firefox_version: "151.0", filed: iso(10),
      last_activity: iso(2), affected_versions: "150+", current_severity: "S2", current_priority: "P2",
      keywords: [], assigned_to: "dev@mozilla.example", assigned_to_name: "D. Eveloper",
      inventory_present: ["GPU model", "about:support"], inventory_missing: [],
      see_also: [], recent_comments: [], attachments: [] },
  },
];

const needsInfo = [
  {
    bug_id: 1901002, title: "No audio on some YouTube videos after resume from sleep",
    bug_component: "Audio/Video: cubeb", severity: null, priority: null, created_at: iso(3),
    keywords_add: [], blocks_add: [], cc_add: [], resolution: null, product: null, component: null,
    regressed_by_add: [], status: null, assigned_to: null,
    ni_targets: ["reporter@example.com"],
    comment: "Could you attach a cubeb log (`MOZ_LOG=cubeb:5`) captured right after the audio drops out, " +
             "and your exact output device? That'll let us see whether the device is being lost on resume.",
    bug_context: { platform: "macOS", firefox_version: "152.0", filed: iso(3), last_activity: iso(3),
      reporter_name: "C. User", current_severity: "", current_priority: "", keywords: [],
      inventory_present: ["Repro steps"], inventory_missing: ["cubeb log", "Output device"],
      see_also: [], recent_comments: [], attachments: [] },
  },
  {
    bug_id: 1901550, title: "MediaRecorder produces an empty .webm on Linux",
    bug_component: "Audio/Video: Recording", severity: null, priority: null, created_at: iso(8),
    keywords_add: [], blocks_add: [], cc_add: [], resolution: null, product: null, component: null,
    regressed_by_add: [], status: null, assigned_to: null,
    ni_targets: ["reporter@example.com"],
    comment: "Which distro and which `ffmpeg`/system codecs are installed? A minimal HTML repro would help too.",
    bug_context: { platform: "Linux", firefox_version: "152.0", filed: iso(8), last_activity: iso(7),
      reporter_name: "E. Filer", current_severity: "", current_priority: "", keywords: [],
      inventory_present: [], inventory_missing: ["Distro", "Codecs", "Minimal repro"],
      see_also: [], recent_comments: [], attachments: [] },
  },
];

const watch = [
  { bug_id: 1898400, title: "Seamless-looping seek asserts on duration mismatch at end of media",
    ni_targets: ["reporter@example.com"], added_at: iso(20) },
];

const log = [
  { bug_id: 1899210, date: iso(0).slice(0, 10), component: "Web Audio", reporter: "B. Tester",
    decision: "triaged", reason: "S3/P3 — intermittent", priority: "P3", severity: "S3" },
  { bug_id: 1900145, date: iso(1).slice(0, 10), component: "Audio/Video: Playback", reporter: "—",
    decision: "triaged", reason: "S2/P2 — perf regression", priority: "P2", severity: "S2" },
];

// ---- lay the fixture down in a temp triage dir + investigation dir ---------
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fxbt-triage-shot-"));
const TRIAGE = path.join(tmp, "triage");
const INVDIR = path.join(tmp, "investigation");
const pending = path.join(TRIAGE, "pending");
fs.mkdirSync(pending, { recursive: true });
fs.mkdirSync(INVDIR, { recursive: true });

for (const d of [featured, ...analyzed, ...needsInfo]) {
  fs.writeFileSync(path.join(pending, `bug-${d.bug_id}.json`), JSON.stringify(d, null, 2));
}
fs.writeFileSync(path.join(TRIAGE, "ni-watch.json"), JSON.stringify(watch, null, 2));
fs.writeFileSync(path.join(TRIAGE, "triage-log.json"), JSON.stringify(log, null, 2));
// Real, public investigation file so the focused card shows the Findings block.
fs.copyFileSync(path.join(__dirname, "example", "bug-2044320-investigation.md"),
                path.join(INVDIR, "bug-2044320-investigation.md"));

// ---- boot the dashboard against the fixture, screenshot, tear down ---------
function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.unref();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => { const { port } = s.address(); s.close(() => resolve(port)); });
  });
}
function waitReady(url, tries = 60) {
  return new Promise((resolve, reject) => {
    const tick = (n) => {
      const req = http.get(url, (res) => { res.resume(); resolve(); });
      req.on("error", () => {
        if (n <= 0) return reject(new Error("dashboard never came up"));
        setTimeout(() => tick(n - 1), 300);
      });
    };
    tick(tries);
  });
}

(async () => {
  const port = await freePort();
  const url = `http://127.0.0.1:${port}/`;
  const env = { ...process.env, TRIAGE_DIR: TRIAGE, FX_BUG_INVESTIGATION_DIR: INVDIR,
                TRIAGE_OWNER: "av-triage@example.com" };
  const srv = spawn(EXE, ["--host", "127.0.0.1", "--port", String(port), "--no-browser"],
                    { env, stdio: "ignore" });

  let browser;
  try {
    await waitReady(url);
    browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1360, height: 940 }, deviceScaleFactor: 2 });
    // Focus the Analyzed tab on the featured public bug.
    await page.goto(`${url}?tab=triaged&bug=2044320`);
    await page.waitForSelector(".rail-item.is-active");
    await page.waitForSelector(".card");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT, "triage-dashboard.png") });
    console.log("wrote", path.join(OUT, "triage-dashboard.png"));
  } finally {
    if (browser) await browser.close();
    srv.kill("SIGKILL");
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => { console.error(e); process.exit(1); });
