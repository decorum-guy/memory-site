import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }

async function downloadText(download) {
  const stream = await download.createReadStream();
  assert(stream, "Exported memories.js stream is unavailable");
  let text = "";
  for await (const chunk of stream) text += chunk.toString("utf8");
  return text;
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?opened=1`, { waitUntil: "networkidle" });
  await page.locator("#ordinary-days").scrollIntoViewIfNeeded();
  await page.locator('[data-media-key="d01"]').click();
  const location = page.locator("#lightbox-location");
  await location.waitFor({ state: "visible" });
  assert((await location.textContent())?.includes("Москва, Россия"), "Fullscreen place label is missing or incorrect");

  await page.locator("#lightbox-close").click();
  await page.locator('[data-media-key="d02"]').click();
  assert(await location.isHidden(), "Location badge stayed visible for an item without a place");
  await page.locator("#lightbox-close").click();
  await page.close();

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  const field = studio.locator('[data-location][value="Москва, Россия"]');
  await field.waitFor({ state: "visible" });
  assert((await field.inputValue()) === "Москва, Россия", "Imported place did not reach Memory Studio");
  const hint = field.locator("xpath=..").locator("small");
  assert((await hint.textContent())?.includes("55.75220"), "Saved GPS hint is missing in Memory Studio");
  await field.fill("Наше место");
  await field.press("Tab");

  const downloadPromise = studio.waitForEvent("download");
  await studio.locator("#export").click();
  const exported = await downloadText(await downloadPromise);
  assert(exported.includes('"location": "Наше место"'), "Edited place was not exported to memories.js");
  assert(exported.includes('"gps": {'), "GPS coordinates were lost during Studio export");
  await studio.close();

  console.log(JSON.stringify({
    fullscreenLocation: true,
    missingLocationHidden: true,
    studioLocationEditor: true,
    locationExport: true,
    gpsPreserved: true,
  }, null, 2));
} finally {
  await browser.close();
}
