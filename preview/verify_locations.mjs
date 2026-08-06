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

  const pageTransforms = await page.locator("#memory-book > .memory-page").evaluateAll((pages) =>
    pages.map((node) => getComputedStyle(node).transform)
  );
  assert(pageTransforms.length >= 4, "Reader fixture does not contain enough chapter pages");
  assert(pageTransforms.every((value) => value === "none" || value === "matrix(1, 0, 0, 1, 0, 0)"),
    `A whole chapter page is still rotated: ${pageTransforms.join(", ")}`);

  const largeEvent = page.locator(".memory-block--event", { has: page.locator('[data-media-key="t01"]') });
  await largeEvent.scrollIntoViewIfNeeded();
  await largeEvent.evaluate((node) => {
    node.classList.remove("event-layout-collage");
    node.classList.add("event-layout-stack");
  });
  const stackRects = await largeEvent.locator(".event-preview__item").evaluateAll((items) =>
    items.slice(0, 5).map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width };
    })
  );
  assert(stackRects.length === 5, "Large event fixture does not contain five cards");
  const firstRow = stackRects.slice(0, 3);
  const distinctColumns = new Set(firstRow.map((rect) => Math.round(rect.left / 25))).size;
  const horizontalSpan = Math.max(...firstRow.map((rect) => rect.right)) - Math.min(...firstRow.map((rect) => rect.left));
  assert(distinctColumns === 3, `Large event does not expose three full-size desktop columns: ${JSON.stringify(stackRects)}`);
  assert(horizontalSpan > 850, `Full-size event preview is too compressed: ${horizontalSpan}px`);
  assert(firstRow.every((rect) => rect.width >= 280), `Desktop polaroids are smaller than the accepted design: ${JSON.stringify(stackRects)}`);
  assert(stackRects[3].top > Math.min(...firstRow.map((rect) => rect.bottom)),
    `The fourth card did not start a new growing row: ${JSON.stringify(stackRects)}`);

  await page.locator("#ordinary-days").scrollIntoViewIfNeeded();
  await page.locator('[data-media-key="d01"]').click();
  const location = page.locator("#lightbox-location");
  await location.waitFor({ state: "visible" });
  assert((await location.textContent())?.includes("Москва, Россия"), "Fullscreen place label is missing or incorrect");

  const locationGeometry = await page.evaluate(() => {
    const badge = document.getElementById("lightbox-location").getBoundingClientRect();
    const image = document.getElementById("lightbox-image").getBoundingClientRect();
    return {
      badgeBottom: badge.bottom,
      badgeLeft: badge.left,
      imageTop: image.top,
      imageLeft: image.left,
      gap: image.top - badge.bottom,
    };
  });
  assert(locationGeometry.badgeBottom <= locationGeometry.imageTop + 1,
    `Location overlaps the photograph: ${JSON.stringify(locationGeometry)}`);
  assert(locationGeometry.gap >= 0 && locationGeometry.gap <= 10,
    `Location is not kept just above the photograph: ${JSON.stringify(locationGeometry)}`);
  assert(Math.abs(locationGeometry.badgeLeft - locationGeometry.imageLeft) <= 8,
    `Location is not aligned to the photograph left edge: ${JSON.stringify(locationGeometry)}`);

  await page.locator("#lightbox-close").click();
  await page.locator('[data-media-key="d02"]').click();
  assert(await location.isHidden(), "Location badge stayed visible for an item without a place");
  await page.locator("#lightbox-close").click();

  await page.locator("#journeys").scrollIntoViewIfNeeded();
  await page.locator('[data-media-key="t05"]').click();
  const liveButton = page.locator("#lightbox-live");
  await liveButton.waitFor({ state: "visible" });
  const liveGeometry = await page.evaluate(() => {
    const caption = document.getElementById("lightbox-caption").getBoundingClientRect();
    const controls = document.querySelector(".lightbox__live-controls").getBoundingClientRect();
    const image = document.getElementById("lightbox-image").getBoundingClientRect();
    return {
      imageBottom: image.bottom,
      captionTop: caption.top,
      captionBottom: caption.bottom,
      controlsTop: controls.top,
    };
  });
  assert(liveGeometry.imageBottom <= liveGeometry.captionTop + 1,
    `Caption overlaps Live Photo media: ${JSON.stringify(liveGeometry)}`);
  assert(liveGeometry.captionBottom <= liveGeometry.controlsTop + 1,
    `Live Photo controls overlap the caption: ${JSON.stringify(liveGeometry)}`);
  await page.locator("#lightbox-close").click();
  await page.close();

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  const field = studio.locator('[data-location][value="Москва, Россия"]');
  await field.waitFor({ state: "attached" });
  await field.evaluate((node) => { const chapter = node.closest("details"); if (chapter) chapter.open = true; });
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
    stableChapterPages: true,
    fullSizeGrowingEventGrid: true,
    fullscreenLocation: true,
    locationAboveMedia: true,
    missingLocationHidden: true,
    liveControlsBelowCaption: true,
    studioLocationEditor: true,
    locationExport: true,
    gpsPreserved: true,
  }, null, 2));
} finally {
  await browser.close();
}
