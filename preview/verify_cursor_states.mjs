import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);
  await page.goto(`${base}/?opened=1#ordinary-days`, { waitUntil: "networkidle" });

  const baseState = await page.evaluate(() => ({
    finePointer: matchMedia("(hover: hover) and (pointer: fine)").matches,
    stylesheetLoaded: [...document.styleSheets].some((sheet) =>
      String(sheet.href || "").includes("cursor-scrapbook-pencil-final-v19.css")
    ),
    cursor: getComputedStyle(document.body).cursor,
  }));
  assert(baseState.finePointer, `desktop Chromium did not expose a fine pointer: ${JSON.stringify(baseState)}`);
  assert(baseState.stylesheetLoaded, `cursor stylesheet was not loaded: ${JSON.stringify(baseState)}`);
  assert(baseState.cursor.includes("scrapbook-pencil-final-v19.svg"), `basic SVG cursor was not applied: ${baseState.cursor}`);
  assert(baseState.cursor.includes("data:image/png;base64"), `basic PNG fallback is missing: ${baseState.cursor}`);
  assert(baseState.cursor.includes("12 48"), `basic hotspot is not 12 48: ${baseState.cursor}`);

  const target = page.locator(".event-open").first();
  await target.waitFor({ state: "visible" });
  await target.hover();
  const hoverCursor = await target.evaluate((element) => getComputedStyle(element).cursor);
  assert(hoverCursor.includes("scrapbook-pencil-final-v19-hover-aligned.svg"), `hover SVG cursor was not applied: ${hoverCursor}`);
  assert(hoverCursor.includes("data:image/png;base64"), `hover PNG fallback is missing: ${hoverCursor}`);
  assert(hoverCursor.includes("12 48"), `hover hotspot is not 12 48: ${hoverCursor}`);

  const box = await target.boundingBox();
  assert(box, "hover target has no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  const activeCursor = await target.evaluate((element) => getComputedStyle(element).cursor);
  await page.mouse.move(0, 0);
  await page.mouse.up();
  assert(activeCursor.includes("scrapbook-pencil-final-v19-active-aligned.svg"), `active SVG cursor was not applied: ${activeCursor}`);
  assert(activeCursor.includes("data:image/png;base64"), `active PNG fallback is missing: ${activeCursor}`);
  assert(activeCursor.includes("12 48"), `active hotspot is not 12 48: ${activeCursor}`);

  const assets = await page.evaluate(async () => Promise.all([
    "assets/cursors/scrapbook-pencil-final-v19.svg",
    "assets/cursors/scrapbook-pencil-final-v19-hover-aligned.svg",
    "assets/cursors/scrapbook-pencil-final-v19-active-aligned.svg",
  ].map(async (asset) => {
    const response = await fetch(asset, { cache: "no-store" });
    return { asset, status: response.status, bytes: (await response.arrayBuffer()).byteLength };
  })));
  assets.forEach(({ asset, status, bytes }) => {
    assert(status === 200, `cursor SVG request failed: ${asset} -> ${status}`);
    assert(bytes > 0, `cursor SVG is empty: ${asset}`);
  });

  const textCursor = await page.locator("input").first().evaluate((element) => getComputedStyle(element).cursor).catch(() => null);
  if (textCursor !== null) assert(textCursor === "text", `text input cursor was overridden: ${textCursor}`);

  console.log(JSON.stringify({
    basic: baseState.cursor,
    hover: hoverCursor,
    active: activeCursor,
    assets,
  }, null, 2));
} finally {
  await browser.close();
}
