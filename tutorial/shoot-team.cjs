/* Capture a screenshot of the LIVE firefox-review-stats team dashboard for the
 * tutorial. The dashboard is a PUBLIC GitHub Pages site
 * (alastor0325.github.io/firefox-review-stats), so — unlike the triage/revue
 * shots — there's no private data and no synthetic setup: we just shoot the
 * published Playback Team View. Not a test, not run by CI — a doc-asset
 * generator run manually (needs network).
 *   NODE_PATH=<playwright> node tutorial/shoot-team.cjs
 */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const OUT = path.join(__dirname, "assets");
fs.mkdirSync(OUT, { recursive: true });
// Deep-link straight to the Playback Team View, 6-month rollup — the headline
// summary + within-group review distribution + concentration metrics.
const URL = "https://alastor0325.github.io/firefox-review-stats/playback/#team/6m";

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1320, height: 1000 }, deviceScaleFactor: 2 });
  try {
    await page.goto(URL, { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForTimeout(1200);   // let the SPA finish rendering the Team View
    await page.screenshot({ path: path.join(OUT, "open-team.png") });
    console.log("wrote", path.join(OUT, "open-team.png"));
  } catch (e) {
    console.error("shoot-team failed (network? site down?):", e.message, "\nSkipping screenshot.");
    process.exitCode = 0;   // doc asset — never block
  } finally {
    await browser.close();
  }
})();
