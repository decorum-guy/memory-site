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

async function readerLayoutSnapshot(page) {
  return page.evaluate(() => [...document.querySelectorAll(".memory-block--event .event-preview")].map((preview) => ({
    seed: preview.dataset.eventIdentitySeed,
    cards: [...preview.querySelectorAll(".event-preview__item")].map((node) => ({
      rotate: node.style.getPropertyValue("--event-rotate"),
      x: node.style.getPropertyValue("--event-shelf-x"),
      y: node.style.getPropertyValue("--event-shelf-y"),
      layer: node.style.getPropertyValue("--event-layer"),
      instance: node.querySelector(".image-frame")?.dataset.mediaInstanceKey || "",
    })),
  })));
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?opened=1`, { waitUntil: "networkidle" });

  const events = page.locator(".memory-block--event");
  assert(await events.count() === 2, `Expected two same-day fixture events, got ${await events.count()}`);
  const event = events.nth(0);
  await event.scrollIntoViewIfNeeded();
  const cards = event.locator(".event-preview__item");
  assert(await cards.count() === 13, `Expected 13 event cards, got ${await cards.count()}`);

  const identityReport = await page.evaluate(() => {
    const api = window.MEMORY_EVENT_LAYOUT;
    if (!api) throw new Error("Event identity layout API is missing");
    const chapter = window.MEMORY_BOOK.chapters[0];
    const first = chapter.blocks[0];
    const second = chapter.blocks[1];
    const contextA = { chapterId: chapter.id, chapterIndex: 0, blockIndex: 0 };
    const contextB = { chapterId: chapter.id, chapterIndex: 0, blockIndex: 1 };
    const keyA = api.eventIdentityKey(first, contextA);
    const keyARepeat = api.eventIdentityKey(first, contextA);
    const keyB = api.eventIdentityKey(second, contextB);

    const reordered = { ...first, items: [...first.items].reverse() };
    const textEdited = {
      ...first,
      title: "Полностью другое название",
      caption: "Полностью другая подпись",
      items: first.items.map((item) => ({ ...item, caption: `Новый текст ${item.id}` })),
    };
    const withExtraMedia = {
      ...first,
      items: [...first.items, {
        id: "new-media",
        kind: "photo",
        src: "preview/demo-media/new.jpg",
        takenAt: "2026-07-10T23:59:00",
      }],
    };
    const differentChapter = { ...contextA, chapterId: "year-2027" };
    const noIdA = {
      type: "event",
      title: "Одинаковая дата",
      items: [{ id: "no-id-a", src: "media/a.jpg", takenAt: "2026-07-10T12:00:00", kind: "photo" }],
    };
    const noIdB = {
      type: "event",
      title: "Одинаковая дата",
      items: [{ id: "no-id-b", src: "media/b.jpg", takenAt: "2026-07-10T12:00:00", kind: "photo" }],
    };
    const empty = { type: "event", title: "Пустое событие", items: [] };

    const stressCount = 12000;
    const identityKeys = new Set();
    const layoutSignatures = new Set();
    let boundsValid = true;
    for (let index = 0; index < stressCount; index += 1) {
      const synthetic = {
        type: "event",
        id: `synthetic-event-${index}`,
        date: "2026-07-10T12:00:00",
        items: [
          {
            id: `synthetic-media-${index}`,
            src: `media/generated/photos/${index}.jpg`,
            thumb: `media/generated/thumbs/${index}.jpg`,
            takenAt: `2026-07-10T12:${String(index % 60).padStart(2, "0")}:00`,
            kind: "photo",
          },
          {
            id: `synthetic-media-${index}-b`,
            src: `media/generated/photos/${index}-b.jpg`,
            takenAt: "2026-07-10T13:00:00",
            kind: "photo",
          },
        ],
      };
      const key = api.eventIdentityKey(synthetic, {
        chapterId: `year-${2023 + (index % 4)}`,
        chapterIndex: index % 4,
        blockIndex: index,
      });
      identityKeys.add(key);
      const layouts = Array.from({ length: 4 }, (_, cardIndex) => api.cardLayout(key, cardIndex));
      layoutSignatures.add(JSON.stringify(layouts));
      if (index < 1500) {
        for (let cardIndex = 0; cardIndex < 12; cardIndex += 1) {
          const layout = api.cardLayout(key, cardIndex);
          const column = cardIndex % 4;
          const baseX = [.5, .16, -.16, -.5][column];
          const baseY = [.35, -.25, .15, -.2][column];
          if (
            !Number.isFinite(layout.rotate) || Math.abs(layout.rotate) < .84 || Math.abs(layout.rotate) > 5.61 ||
            !Number.isFinite(layout.x) || layout.x < baseX - .141 || layout.x > baseX + .141 ||
            !Number.isFinite(layout.y) || layout.y < baseY - .301 || layout.y > baseY + .301 ||
            !Number.isInteger(layout.layer) || layout.layer < 2 || layout.layer > 5
          ) boundsValid = false;
        }
      }
    }

    const previews = [...document.querySelectorAll(".memory-block--event .event-preview")];
    const readDomLayout = (preview) => [...preview.querySelectorAll(".event-preview__item")].slice(0, 4).map((node) => ({
      rotate: Number.parseFloat(node.style.getPropertyValue("--event-rotate")),
      x: Number.parseFloat(node.style.getPropertyValue("--event-shelf-x")),
      y: Number.parseFloat(node.style.getPropertyValue("--event-shelf-y")),
      layer: Number.parseInt(node.style.getPropertyValue("--event-layer"), 10),
    }));

    return {
      keyA,
      keyARepeat,
      keyB,
      keyReordered: api.eventIdentityKey(reordered, { ...contextA, blockIndex: 99 }),
      keyTextEdited: api.eventIdentityKey(textEdited, contextA),
      keyExtraMedia: api.eventIdentityKey(withExtraMedia, contextA),
      keyDifferentChapter: api.eventIdentityKey(first, differentChapter),
      keyNoIdA: api.eventIdentityKey(noIdA, contextA),
      keyNoIdB: api.eventIdentityKey(noIdB, contextA),
      keyEmptyA: api.eventIdentityKey(empty, { chapterId: chapter.id, chapterIndex: 0, blockIndex: 20 }),
      keyEmptyB: api.eventIdentityKey(empty, { chapterId: chapter.id, chapterIndex: 0, blockIndex: 21 }),
      expectedLayoutA: Array.from({ length: 4 }, (_, index) => api.cardLayout(keyA, index)),
      domSeedA: previews[0]?.dataset.eventIdentitySeed,
      domSeedB: previews[1]?.dataset.eventIdentitySeed,
      domLayoutA: readDomLayout(previews[0]),
      identityCount: identityKeys.size,
      signatureCount: layoutSignatures.size,
      stressCount,
      boundsValid,
      keyPatternValid: /^evt-[0-9a-f]{32}$/.test(keyA),
    };
  });

  assert(identityReport.keyPatternValid, `Event identity is not a 128-bit hexadecimal key: ${identityReport.keyA}`);
  assert(identityReport.keyA === identityReport.keyARepeat, "The same event changes identity between calculations");
  assert(identityReport.keyA !== identityReport.keyB, "Same-day events with duplicated block IDs received the same identity");
  assert(identityReport.keyA === identityReport.keyReordered, "Reordering media changed the event identity");
  assert(identityReport.keyA === identityReport.keyTextEdited, "Editing titles or captions changed the event identity");
  assert(identityReport.keyA !== identityReport.keyExtraMedia, "Adding media did not change the event identity");
  assert(identityReport.keyA !== identityReport.keyDifferentChapter, "Moving an event to another chapter did not change its namespace");
  assert(identityReport.keyNoIdA !== identityReport.keyNoIdB, "Events without block IDs collided despite different media");
  assert(identityReport.keyEmptyA !== identityReport.keyEmptyB, "Empty fallback events collided");
  assert(identityReport.identityCount === identityReport.stressCount,
    `Identity collision in ${identityReport.stressCount} synthetic events: ${JSON.stringify(identityReport)}`);
  assert(identityReport.signatureCount === identityReport.stressCount,
    `Four-card layout collision in ${identityReport.stressCount} synthetic events: ${JSON.stringify(identityReport)}`);
  assert(identityReport.boundsValid, "Generated layout escaped safe rotation, offset or layer bounds");
  assert(identityReport.domSeedA === identityReport.keyA, "First rendered event does not use its composite identity");
  assert(identityReport.domSeedB === identityReport.keyB, "Second rendered event does not use its composite identity");
  assert(JSON.stringify(identityReport.domLayoutA) === JSON.stringify(identityReport.expectedLayoutA),
    `Rendered cards do not use their event identity: ${JSON.stringify(identityReport)}`);

  const instanceKeys = await cards.locator(".image-frame").evaluateAll((frames) => frames.map((frame) => frame.dataset.mediaInstanceKey));
  assert(instanceKeys.every(Boolean), `A rendered card has no occurrence-aware media key: ${JSON.stringify(instanceKeys)}`);
  assert(new Set(instanceKeys).size === 13,
    `Duplicate media IDs caused a card to disappear or share an instance key: ${JSON.stringify(instanceKeys)}`);

  const inlineLayouts = await cards.evaluateAll((nodes) => nodes.map((node) => ({
    rotate: Number.parseFloat(node.style.getPropertyValue("--event-rotate")),
    x: Number.parseFloat(node.style.getPropertyValue("--event-shelf-x")),
    y: Number.parseFloat(node.style.getPropertyValue("--event-shelf-y")),
    layer: Number.parseInt(node.style.getPropertyValue("--event-layer"), 10),
  })));
  assert(inlineLayouts.every((layout) => Object.values(layout).every(Number.isFinite)),
    `A rendered card received NaN layout values: ${JSON.stringify(inlineLayouts)}`);

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

  for (const [cardIndex, expectedCounter] of [[10, "11 / 13"], [11, "12 / 13"], [12, "13 / 13"]]) {
    await cards.nth(cardIndex).click();
    await page.locator("#lightbox-counter").waitFor({ state: "visible" });
    assert((await page.locator("#lightbox-counter").textContent())?.trim() === expectedCounter,
      `Card ${cardIndex + 1} opened the wrong gallery item`);
    await page.locator("#lightbox-close").click();
  }

  const beforeReload = await readerLayoutSnapshot(page);
  await page.reload({ waitUntil: "networkidle" });
  await page.locator(".memory-block--event").first().waitFor({ state: "attached" });
  const afterReload = await readerLayoutSnapshot(page);
  assert(JSON.stringify(beforeReload) === JSON.stringify(afterReload),
    "Event identities or card layouts changed after a full page reload");

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
    duplicateMediaInstancesPreserved: true,
    sameDayEventsDiffer: true,
    duplicatedBlockIdsDiffer: true,
    orderIndependentIdentity: true,
    textEditStableIdentity: true,
    mediaSetSensitiveIdentity: true,
    chapterNamespacedIdentity: true,
    noIdFallbackIdentity: true,
    emptyEventFallbackIdentity: true,
    syntheticIdentityCollisionTest: 12000,
    syntheticLayoutCollisionTest: 12000,
    safeLayoutBounds: true,
    fullReloadStability: true,
    overlappingFourCardRows: true,
    originalPolaroidSize: true,
    originalPaperMargins: true,
    captionBelowMedia: true,
    captionFourLineClamp: true,
    duplicateGalleryNavigation: true,
    offlineFavicon: true,
    typographyControls: true,
    oneClickProductionApply: true,
  }, null, 2));
} finally {
  await browser.close();
}
