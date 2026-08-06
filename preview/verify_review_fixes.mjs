import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:8765";
const browser = await chromium.launch({
  headless: true,
  args: ["--autoplay-policy=no-user-gesture-required"],
});
function assert(value, message) { if (!value) throw new Error(message); }

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?opened=1`, { waitUntil: "networkidle" });

  const event = page.locator(".memory-block--event").first();
  await event.scrollIntoViewIfNeeded();
  const cards = event.locator(".event-preview__item");
  assert(await cards.count() === 9, `Expected nine ordered cards, got ${await cards.count()}`);
  assert(await event.evaluate((node) => node.classList.contains("event-layout-stack")),
    "A 9-item legacy collage was not promoted to the growing stack grid");
  assert(!await event.evaluate((node) => node.classList.contains("event-layout-collage")),
    "Legacy collage class remained on a 9-item event");

  const order = await cards.evaluateAll((nodes) => nodes.map((node) => ({
    order: Number(node.dataset.mediaOrder),
    instance: node.querySelector(".image-frame")?.dataset.mediaInstanceKey || "",
    caption: node.querySelector(".event-preview__caption")?.textContent?.trim() || "",
  })));
  assert(order.every((entry, index) => entry.order === index), `Reader lost explicit media order: ${JSON.stringify(order)}`);
  assert(order.map((entry) => entry.caption).join("|") === Array.from({ length: 9 }, (_, index) => `Порядок ${index + 1}`).join("|"),
    `Reader DOM order differs from Studio order: ${JSON.stringify(order)}`);

  const scrapbook = await cards.evaluateAll((nodes) => nodes.map((node) => ({
    rotate: Number.parseFloat(node.style.getPropertyValue("--event-rotate")),
    x: Number.parseFloat(node.style.getPropertyValue("--event-shelf-x")),
    y: Number.parseFloat(node.style.getPropertyValue("--event-shelf-y")),
    layer: Number.parseInt(node.style.getPropertyValue("--event-layer"), 10),
    transform: getComputedStyle(node).transform,
  })));
  assert(scrapbook.every((entry) => [entry.rotate, entry.x, entry.y, entry.layer].every(Number.isFinite)),
    `Scrapbook layout variables disappeared: ${JSON.stringify(scrapbook)}`);
  assert(new Set(scrapbook.map((entry) => entry.rotate.toFixed(3))).size >= 4,
    `Card tilts were flattened: ${JSON.stringify(scrapbook)}`);
  assert(new Set(scrapbook.map((entry) => entry.layer)).size >= 2,
    `Card depth layers were flattened: ${JSON.stringify(scrapbook)}`);
  assert(scrapbook.some((entry) => Math.abs(entry.x) > .05 || Math.abs(entry.y) > .05),
    `Card scrapbook offsets were flattened: ${JSON.stringify(scrapbook)}`);
  assert(scrapbook.every((entry) => entry.transform !== "none"),
    `Card transforms are not applied: ${JSON.stringify(scrapbook)}`);

  const geometry = await cards.evaluateAll((nodes) => nodes.map((node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
      display: style.display,
      visibility: style.visibility,
      opacity: Number(style.opacity),
    };
  }));
  assert(geometry.every((rect) => rect.width > 100 && rect.height > 100 && rect.display !== "none" && rect.visibility !== "hidden" && rect.opacity > 0),
    `One or more cards are not visibly rendered: ${JSON.stringify(geometry)}`);
  assert(geometry.slice(0, 4).every((rect, index, row) => index === 0 || rect.left > row[index - 1].left),
    `First row is not left-to-right: ${JSON.stringify(geometry)}`);
  assert(geometry.slice(4, 8).every((rect, index, row) => index === 0 || rect.left > row[index - 1].left),
    `Second row is not left-to-right: ${JSON.stringify(geometry)}`);
  assert(geometry[4].top > Math.min(...geometry.slice(0, 4).map((rect) => rect.bottom)),
    `Fifth item did not start the second row: ${JSON.stringify(geometry)}`);
  assert(geometry[8].top > Math.min(...geometry.slice(4, 8).map((rect) => rect.bottom)),
    `Ninth item did not start a visible third row: ${JSON.stringify(geometry)}`);

  const previewGeometry = await event.locator(".event-preview").evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return { top: rect.top, bottom: rect.bottom, height: rect.height };
  });
  assert(previewGeometry.bottom >= geometry[8].bottom - 16,
    `Growing preview clips the ninth card: ${JSON.stringify({ previewGeometry, ninth: geometry[8] })}`);

  const centers = geometry.map((rect) => `${Math.round((rect.left + rect.right) / 2)}:${Math.round((rect.top + rect.bottom) / 2)}`);
  assert(new Set(centers).size === 9, `Two cards still occupy the same slot: ${JSON.stringify(centers)}`);

  const count = event.locator(".event-preview__count");
  assert((await count.textContent())?.trim() === "9 файлов", `Wrong count badge: ${await count.textContent()}`);
  const countZ = Number(await count.evaluate((node) => getComputedStyle(node).zIndex));
  await cards.nth(8).hover();
  const hoverZ = Number(await cards.nth(8).evaluate((node) => getComputedStyle(node).zIndex));
  assert(hoverZ > countZ, `Hovered card stays below file-count badge: ${hoverZ} <= ${countZ}`);

  await cards.nth(0).click();
  const video = page.locator("#lightbox-video");
  await video.waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const media = document.getElementById("lightbox-video");
    return media && !media.paused && media.currentTime > 0;
  }, null, { timeout: 15000 });
  assert(await page.locator("#lightbox").evaluate((node) => node.classList.contains("is-video")), "Regular video did not open as video");
  assert(await page.locator("#lightbox-live").isHidden(), "Regular video exposed Live Photo controls");

  await video.evaluate((media) => { media.currentTime = 2.6; });
  await page.waitForFunction(() => {
    const media = document.getElementById("lightbox-video");
    return media && Math.abs(media.currentTime - 2.6) < .45;
  }, null, { timeout: 15000 });
  await page.waitForTimeout(700);
  const seekTime = await video.evaluate((media) => media.currentTime);
  assert(seekTime > 2, `Reader video seek fell back to the beginning: ${seekTime}`);

  const locationState = await page.evaluate(() => {
    const badge = document.getElementById("lightbox-location");
    const icon = badge?.querySelector(".lightbox__location-icon");
    const text = badge?.querySelector(".lightbox__location-text");
    if (!badge || !icon || !text || badge.hidden) return null;
    const badgeStyle = getComputedStyle(badge);
    const iconRect = icon.getBoundingClientRect();
    const textRect = text.getBoundingClientRect();
    return {
      display: badgeStyle.display,
      alignItems: badgeStyle.alignItems,
      centerDelta: Math.abs((iconRect.top + iconRect.height / 2) - (textRect.top + textRect.height / 2)),
      text: text.textContent,
    };
  });
  assert(locationState && locationState.display === "inline-flex" && locationState.alignItems === "center",
    `Location badge is not flex-centered: ${JSON.stringify(locationState)}`);
  assert(locationState.centerDelta < 2, `GPS icon is vertically misaligned: ${JSON.stringify(locationState)}`);
  await page.locator("#lightbox-close").click();
  await page.close();

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  await studio.waitForFunction(() => Boolean(window.MEMORY_CROP_BOUNDS));
  const firstPhoto = studio.locator(".item-meta").filter({ hasText: /^PHOTO$/ }).first().locator("../..");
  await firstPhoto.locator(".item-preview").hover();
  await firstPhoto.locator("[data-crop]").click();
  await studio.locator("#crop-dialog").waitFor({ state: "visible" });
  await studio.waitForFunction(() => {
    const state = window.MEMORY_CROP_BOUNDS?.getState?.();
    return state && state.x === false && state.y === false;
  });

  const before = await studio.locator("#crop-position").textContent();
  const stage = studio.locator("#crop-stage");
  const box = await stage.boundingBox();
  assert(box, "Crop stage has no geometry");
  await studio.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await studio.mouse.down();
  await studio.mouse.move(box.x + box.width / 2 + 140, box.y + box.height / 2 - 100, { steps: 8 });
  await studio.mouse.up();
  const after = await studio.locator("#crop-position").textContent();
  const cropState = await studio.evaluate(() => window.MEMORY_CROP_BOUNDS.getState());
  assert(before === "X 50% · Y 50%" && after === before,
    `Fully fitting photo changed meaningless X/Y values: ${before} -> ${after}`);
  assert(cropState.xValue === 50 && cropState.yValue === 50, `Locked axes were persisted away from center: ${JSON.stringify(cropState)}`);
  await studio.locator("#crop-cancel").click();
  await studio.close();

  const range = await fetch(`${base}/preview/demo-media/order-video.webm`, { headers: { Range: "bytes=64-127" } });
  assert(range.status === 206, `Server ignored media byte range: HTTP ${range.status}`);
  assert(range.headers.get("content-range")?.startsWith("bytes 64-127/"), `Invalid Content-Range: ${range.headers.get("content-range")}`);
  assert((await range.arrayBuffer()).byteLength === 64, "Partial media response has wrong length");

  console.log(JSON.stringify({
    legacyNineItemCollagePromoted: true,
    ninthCardVisible: true,
    hoveredCardAboveCount: true,
    sourceOrderPreserved: true,
    scrapbookTiltsPreserved: true,
    scrapbookOffsetsPreserved: true,
    scrapbookLayersPreserved: true,
    regularVideoAutoplay: true,
    readerVideoSeekStable: true,
    mediaByteRanges: true,
    locationIconCentered: true,
    inactiveCropAxesLocked: true,
  }, null, 2));
} finally {
  await browser.close();
}
