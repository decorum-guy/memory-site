import { chromium } from "playwright";
import { writeFile, unlink } from "node:fs/promises";
import { resolve } from "node:path";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:8765";
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

  const event = page.locator(".memory-block--event").first();
  await event.scrollIntoViewIfNeeded();
  const cards = event.locator(".event-preview__item");
  assert(await cards.count() === 13, `Expected 13 event cards, got ${await cards.count()}`);

  const cardRects = await cards.evaluateAll((items) => items.slice(0, 5).map((node) => {
    const rect = node.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height };
  }));
  const previewBox = await event.locator(".event-preview").boundingBox();
  assert(cardRects.length === 5 && previewBox, "Event geometry is unavailable");
  const firstRow = cardRects.slice(0, 4);
  const overlaps = firstRow.slice(0, -1).map((rect, index) => rect.right - firstRow[index + 1].left);
  assert(firstRow.every((rect) => rect.width >= 245), `Desktop polaroids became too small: ${JSON.stringify(cardRects)}`);
  assert(overlaps.every((value) => value >= 8 && value <= 75), `Four-card row does not overlap gently: ${JSON.stringify({ cardRects, overlaps })}`);
  assert(cardRects[4].top > Math.min(...firstRow.map((rect) => rect.bottom)), "The fifth card did not start a second row");
  assert(previewBox.height > firstRow[0].height * 3, "Event preview did not grow for all four rows");

  const seededLayout = await page.evaluate(() => {
    const api = window.MEMORY_EVENT_LAYOUT;
    if (!api) throw new Error("Date-seeded layout API is missing");
    const preview = document.querySelector(".memory-block--event .event-preview");
    const nodes = [...preview.querySelectorAll(".event-preview__item")].slice(0, 4);
    const readNode = (node) => ({
      rotate: Number.parseFloat(node.style.getPropertyValue("--event-rotate")),
      x: Number.parseFloat(node.style.getPropertyValue("--event-shelf-x")),
      y: Number.parseFloat(node.style.getPropertyValue("--event-shelf-y")),
      layer: Number.parseInt(node.style.getPropertyValue("--event-layer"), 10),
    });
    const sameDateA = Array.from({ length: 4 }, (_, index) => api.cardLayout("2026-07-10", index));
    const sameDateB = Array.from({ length: 4 }, (_, index) => api.cardLayout("2026-07-10", index));
    const otherDate = Array.from({ length: 4 }, (_, index) => api.cardLayout("2026-07-11", index));
    return {
      seed: preview.dataset.eventDateSeed,
      dom: nodes.map(readNode),
      sameDateA,
      sameDateB,
      otherDate,
    };
  });
  assert(seededLayout.seed === "2026-07-10", `Event seed was not derived from its date: ${JSON.stringify(seededLayout)}`);
  assert(JSON.stringify(seededLayout.sameDateA) === JSON.stringify(seededLayout.sameDateB), "The same event date changes its layout between calculations");
  assert(JSON.stringify(seededLayout.sameDateA) !== JSON.stringify(seededLayout.otherDate), "Different event dates received an identical layout");
  assert(JSON.stringify(seededLayout.dom) === JSON.stringify(seededLayout.sameDateA), `Rendered cards do not use the date seed: ${JSON.stringify(seededLayout)}`);

  const firstCard = cards.nth(0);
  const caption = firstCard.locator(".event-preview__caption");
  const cardBox = await firstCard.boundingBox();
  const frameBox = await firstCard.locator(".image-frame").boundingBox();
  const captionBox = await caption.boundingBox();
  assert(cardBox && frameBox && captionBox, "Polaroid geometry is unavailable");

  const cardState = await firstCard.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      aspectRatio: style.aspectRatio,
      paddingTop: parseFloat(style.paddingTop),
      paddingRight: parseFloat(style.paddingRight),
      paddingBottom: parseFloat(style.paddingBottom),
      width: node.getBoundingClientRect().width,
      height: node.getBoundingClientRect().height,
    };
  });
  assert(cardState.aspectRatio === "4 / 5", `Original 4:5 polaroid proportion was lost: ${JSON.stringify(cardState)}`);
  assert(cardState.paddingTop >= 8 && cardState.paddingRight >= 8, `Top/side paper margin collapsed: ${JSON.stringify(cardState)}`);
  assert(cardState.paddingBottom >= 40, `Lower white paper strip collapsed: ${JSON.stringify(cardState)}`);
  assert(frameBox.x >= cardBox.x + 7 && frameBox.y >= cardBox.y + 7, "Photo touches the top or side card edge");
  assert(cardBox.y + cardBox.height - (frameBox.y + frameBox.height) >= 60, "White lower polaroid area is no longer visible");
  assert(captionBox.x >= cardBox.x, "Caption escapes the left card edge");
  assert(captionBox.x + captionBox.width <= cardBox.x + cardBox.width, "Caption escapes the right card edge");

  const captionState = await caption.evaluate((node) => {
    const style = getComputedStyle(node);
    const frame = node.parentElement.querySelector(".image-frame");
    return {
      whiteSpace: style.whiteSpace,
      lineClamp: style.webkitLineClamp,
      overflowWrap: style.overflowWrap,
      overflow: style.overflow,
      clientHeight: node.clientHeight,
      scrollHeight: node.scrollHeight,
      width: node.getBoundingClientRect().width,
      cardWidth: node.closest(".event-preview__item").getBoundingClientRect().width,
      frameBottom: frame.offsetTop + frame.offsetHeight,
      captionTop: node.offsetTop,
    };
  });
  assert(captionState.captionTop >= captionState.frameBottom + 4, "Caption overlaps the photo or has no upper gap");
  assert(captionState.whiteSpace === "normal", "Caption is still forced into one line");
  assert(captionState.lineClamp === "4", `Expected four-line clamp, got ${captionState.lineClamp}`);
  assert(["anywhere", "break-word"].includes(captionState.overflowWrap), "Long words cannot wrap inside the caption");
  assert(captionState.overflow === "hidden", "Overflowing caption is not clipped");
  assert(captionState.scrollHeight > captionState.clientHeight, "Long fixture caption was not actually clamped");
  assert(captionState.width <= captionState.cardWidth * 0.8, "Caption is wider than the decorative lower rule");

  await cards.nth(12).click();
  await page.locator("#lightbox-counter").waitFor({ state: "visible" });
  assert((await page.locator("#lightbox-counter").textContent())?.trim() === "13 / 13", "Last visible card did not open the thirteenth item");
  await page.locator("#lightbox-close").click();

  const favicon = page.locator('link[rel="icon"]');
  assert(await favicon.count() === 1, "Offline favicon link is missing");
  assert((await favicon.getAttribute("href")) === "assets/memory-book-icon.svg", "Unexpected favicon path");
  await page.close();

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  await studio.locator("#book-settings").waitFor({ state: "visible" });
  assert(await studio.locator('[data-typography-field="eventCaptionPx"]').count() === 1, "Day-caption type control is missing");
  assert(await studio.locator('[data-typography-field="eventDatePx"]').count() === 1, "Day-date type control is missing");
  assert(await studio.locator('[data-typography-field="polaroidCaptionScale"]').count() === 1, "Polaroid-caption type control is missing");
  assert(await studio.locator("#apply-production-file").count() === 1, "One-click production apply control is missing");

  await studio.locator('[data-typography-field="eventCaptionPx"]').evaluate((node) => {
    node.value = "22";
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const previewSize = parseFloat(await studio.locator('[data-type-preview="eventCaption"]').evaluate((node) => getComputedStyle(node).fontSize));
  assert(Math.abs(previewSize - 22) < .5, `Studio typography preview did not update: ${previewSize}`);

  const downloadPromise = studio.waitForEvent("download");
  await studio.locator("#export").click();
  const exported = await downloadText(await downloadPromise);
  assert(exported.includes('"eventCaptionPx": 22'), "Typography setting did not reach exported memories.js");

  const applyPath = resolve("preview/.memory-apply-test.js");
  await writeFile(applyPath, exported, "utf8");
  studio.on("dialog", (dialog) => dialog.accept());
  let applyResponse = null;
  studio.on("response", async (response) => {
    if (!response.url().endsWith("/api/memory/apply")) return;
    applyResponse = {
      status: response.status(),
      body: await response.text().catch(() => "<unreadable>")
    };
  });
  const popupPromise = studio.waitForEvent("popup");
  await studio.locator("#apply-production-file").setInputFiles(applyPath);
  const popup = await popupPromise;
  await studio.waitForFunction(() => {
    const text = document.getElementById("status")?.textContent || "";
    return text.includes("Production обновлён") || text.includes("Не удалось применить");
  }, null, { timeout: 15000 });
  const applyStatus = (await studio.locator("#status").textContent()) || "";
  assert(applyStatus.includes("Production обновлён"), `Production apply failed: ${applyStatus}; response=${JSON.stringify(applyResponse)}`);
  await popup.waitForLoadState("networkidle");
  const appliedState = await popup.evaluate(() => ({
    value: window.MEMORY_BOOK?.meta?.typography?.eventCaptionPx,
    computed: parseFloat(getComputedStyle(document.querySelector(".event-heading .hand-caption")).fontSize)
  }));
  assert(appliedState.value === 22, `Applied production book lost typography settings: ${JSON.stringify(appliedState)}`);
  assert(Math.abs(appliedState.computed - 22) < .5, `Reader did not apply typography CSS: ${JSON.stringify(appliedState)}`);
  await popup.close();
  await studio.close();
  await unlink(applyPath).catch(() => {});

  console.log(JSON.stringify({
    renderedCards: 13,
    overlappingFourCardRows: true,
    dateSeededLayout: true,
    stableSameDateLayout: true,
    differentDatesDiffer: true,
    originalPolaroidSize: true,
    originalPaperMargins: true,
    captionBelowMedia: true,
    captionFourLineClamp: true,
    lastCardOpensCorrectItem: true,
    offlineFavicon: true,
    typographyControls: true,
    oneClickProductionApply: true,
  }, null, 2));
} finally {
  await browser.close();
}
