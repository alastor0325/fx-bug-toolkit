/* Capture a screenshot of the REVUE review dashboard for the tutorial. Revue is
 * the separate `revue` npm CLI (github:alastor0325/revue) that /review-dashboard
 * launches. We never screenshot a real repo — it can hold private/security work.
 * Instead we build a throwaway git repo with a SYNTHETIC, public-only patch
 * series (the same public Bug 2044320 colr fix the viewer/triage tutorials use)
 * and start Revue's Express app IN-PROCESS against it — so this never touches a
 * `revue` daemon the user may have running.
 * Not a test, not committed output — a doc-asset generator like shoot.cjs.
 *   NODE_PATH=<playwright> node tutorial/shoot-revue.cjs
 */
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execSync } = require("node:child_process");
const { chromium } = require("playwright");

const OUT = path.join(__dirname, "assets");
fs.mkdirSync(OUT, { recursive: true });

// ---- locate the installed revue package so we can require its server --------
function findRevuePkgRoot() {
  const exe = process.platform === "win32" ? "revue.cmd" : "revue";
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    const cand = path.join(dir, exe);
    if (!fs.existsSync(cand)) continue;
    // bin → <pkg>/bin/revue.js → <pkg>; follow the symlink npm/`npm link` makes.
    const real = fs.realpathSync(cand);
    const root = path.resolve(path.dirname(real), "..");
    if (fs.existsSync(path.join(root, "src", "server.js"))) return root;
  }
  return null;
}

const pkgRoot = findRevuePkgRoot();
if (!pkgRoot) {
  console.error(
    "revue not found on PATH. Install it first:\n" +
    "  npm install -g github:alastor0325/revue\n" +
    "Skipping screenshot.");
  process.exit(0);
}
const { createApp } = require(path.join(pkgRoot, "src", "server.js"));

// ---- synthetic, public-only patch series ------------------------------------
// A two-part series on the real, public Bug 2044320 (Audio/Video: Playback) —
// the same bug the viewer/triage tutorials feature. Content is plausible-public,
// not copied from any private tree.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fxbt-revue-shot-"));
const repo = path.join(tmp, "mozilla-central");
fs.mkdirSync(repo, { recursive: true });

const git = (cmd) => execSync(`git ${cmd}`, {
  cwd: repo,
  stdio: "pipe",
  env: { ...process.env,
    GIT_AUTHOR_NAME: "A. Reviewer", GIT_AUTHOR_EMAIL: "dev@example.com",
    GIT_COMMITTER_NAME: "A. Reviewer", GIT_COMMITTER_EMAIL: "dev@example.com",
    GIT_AUTHOR_DATE: "2026-06-02T10:00:00", GIT_COMMITTER_DATE: "2026-06-02T10:00:00" },
});
const write = (rel, body) => {
  const p = path.join(repo, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, body);
};
// Commit via a message file so the body keeps real newlines and characters
// (a shell-escaped `-m` leaves literal "\n"/"§" in the message).
const commit = (msg) => {
  const f = path.join(tmp, "COMMIT_MSG.txt");
  fs.writeFileSync(f, msg);
  git(`commit -q -F "${f}"`);
};

git("init -q -b main");

// ---- base commit (what origin/main points at) ------------------------------
write("third_party/rust/mp4parse/src/lib.rs",
`fn read_colr(src: &mut impl Read, count: u32) -> Result<ColourInformation> {
    // Under Normal strictness, more than one colr box is rejected outright.
    if count > 1 {
        return Err(Error::from(Status::ColrBadQuantityBMFF));
    }
    parse_colour_information(src)
}
`);
write("dom/media/mp4/MP4Metadata.cpp",
`bool MP4Metadata::Parse() {
  // A single hard failure here aborts the whole metadata parse.
  return mParser->Parse(mSource);
}
`);
git("add -A");
commit("Bug 2030296 - Initial colr parsing");
// Pin origin/main at the base so Revue resolves the series as base..HEAD.
git("update-ref refs/remotes/origin/main HEAD");

// ---- part 1 of the series --------------------------------------------------
write("third_party/rust/mp4parse/src/lib.rs",
`fn read_colr(src: &mut impl Read, count: u32) -> Result<ColourInformation> {
    // ISO/IEC 14496-12 §12.1.5 permits more than one colr box: keep the first
    // and warn rather than hard-failing the whole metadata parse.
    if count > 1 {
        warn!("ignoring {} extra colr box(es)", count - 1);
    }
    parse_colour_information(src)
}
`);
git("add -A");
commit(
`Bug 2044320 - Downgrade duplicate colr box to a warning in mp4parse

Allow a video sample entry to carry more than one colr box, as ISO/IEC
14496-12 §12.1.5 explicitly permits. Previously the second box made mp4parse
hard-fail (ColrBadQuantityBMFF), aborting the parse and also breaking
animated AVIF.`);

// ---- part 2 of the series --------------------------------------------------
write("dom/media/gtest/TestMP4Metadata.cpp",
`TEST(MP4Metadata, DuplicateColrBoxes) {
  // Two adjacent colr boxes must parse: the first wins, the rest are ignored.
  RefPtr<MediaByteBuffer> buffer = make_adjacent_colr_fixture();
  MP4Metadata metadata(buffer);
  EXPECT_TRUE(metadata.Parse());
  EXPECT_EQ(metadata.GetNumberTracks(TrackType::kVideoTrack).Ref(), 1u);
}
`);
git("add -A");
commit(
`Bug 2044320 - Add a gtest for adjacent colr boxes

Covers the invariant that a video sample entry with more than one colr box
parses and exposes its track, so the strictness regression cannot silently
return.`);

// ---- boot Revue in-process against the fixture, screenshot, tear down -------
(async () => {
  const app = createApp({
    worktreeName: "bug-2044320",
    worktreePath: repo,
    mainRepoPath: repo,
  });
  const server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  const port = server.address().port;
  const url = `http://127.0.0.1:${port}/`;

  let browser;
  try {
    browser = await chromium.launch();
    const page = await browser.newPage({
      viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2,
    });
    await page.goto(url);
    // Wait for the diff to render (the loader hides and the file list appears).
    await page.waitForSelector("#files-changed", { state: "visible", timeout: 15000 });
    await page.waitForFunction(
      () => document.querySelector("#files-changed")?.textContent.trim().length > 0,
      null, { timeout: 15000 });
    // The fixture lives in an OS temp dir; show a clean, generic worktree path
    // in the asset instead of leaking the build machine's /var/folders path.
    await page.evaluate(() => {
      const el = document.querySelector("#worktree-path");
      if (el) el.textContent = "~/firefox-2044320";
    });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT, "review-dashboard.png") });
    console.log("wrote", path.join(OUT, "review-dashboard.png"));
  } finally {
    if (browser) await browser.close();
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => { console.error(e); process.exit(1); });
