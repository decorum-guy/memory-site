import { chromium } from "playwright";
import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:8765";
const fixture = resolve("preview/incremental-fixture");
const browser = await chromium.launch({ headless: true });
const assert = (value, message) => { if (!value) throw new Error(message); };

async function currentBook(page) {
  return page.evaluate(() => JSON.parse(JSON.stringify(book)));
}

async function selectImportFiles(page) {
  const photos = Array.from({ length: 18 }, (_, index) => resolve(fixture, `batch-${String(index + 1).padStart(2, "0")}.jpg`));
  await page.locator("[data-import-files]").setInputFiles([
    ...photos,
    resolve(fixture, "standalone.mp4"),
  ]);
  await page.locator("[data-live-photo]").setInputFiles(resolve(fixture, "LIVE_0001.JPG"));
  await page.locator("[data-live-video]").setInputFiles(resolve(fixture, "LIVE_0001.MOV"));
  await page.locator("[data-add-live-pair]").click();
}

async function runImport(page, expectedStatus) {
  const popupPromise = page.waitForEvent("popup");
  await page.locator("[data-import-start]").click();
  const popup = await popupPromise;
  await page.locator("#status").waitFor({ state: "visible" });
  await page.waitForFunction((needle) => document.getElementById("status")?.textContent?.includes(needle), expectedStatus, { timeout: 180000 });
  await popup.waitForLoadState("domcontentloaded", { timeout: 180000 });
  return popup;
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  await page.locator("#memory-media-import").waitFor({ state: "visible" });
  assert(await page.locator("#memory-media-import").textContent() === "Добавить фото и видео", "Import trigger is missing");

  const initial = await currentBook(page);
  assert(initial.meta.manualMarker === "KEEP-ME", "Manual fixture marker is missing before import");
  assert(initial.chapters[0].blocks[0].caption === "Ручная подпись, которую нельзя потерять", "Manual event caption is missing before import");

  await page.locator("#memory-media-import").click();
  await page.locator("#memory-media-import-dialog").waitFor({ state: "visible" });
  assert(await page.locator("[data-import-target] option").count() >= 2, "Existing event target is absent");
  await selectImportFiles(page);
  assert(await page.locator(".media-import-file").count() === 21, "Batch queue did not keep all 21 selected files");
  assert(await page.locator(".media-import-pairs article").count() === 1, "Explicit Live Photo pair is absent");
  assert((await page.locator("[data-import-summary]").textContent())?.includes("21 файл"), "Queue summary is incorrect");

  const popup = await runImport(page, "Добавлено 20");
  const imported = await currentBook(page);
  assert(imported.meta.manualMarker === "KEEP-ME", "Incremental import overwrote manual book metadata");
  assert(imported.chapters[0].blocks[0].caption === "Ручная подпись, которую нельзя потерять", "Incremental import overwrote an existing event caption");

  const allItems = imported.chapters.flatMap((chapter) => chapter.blocks || []).flatMap((block) => block.items || []);
  const newItems = allItems.filter((item) => item.id !== "existing-item");
  assert(newItems.length === 20, `Expected 20 new media items, got ${newItems.length}`);
  assert(newItems.filter((item) => item.kind === "photo").length === 18, "Photo type detection failed");
  assert(newItems.filter((item) => item.kind === "video").length === 1, "Standalone video type detection failed");
  assert(newItems.filter((item) => item.kind === "live").length === 1, "Explicit Live Photo was not created as one live item");
  const live = newItems.find((item) => item.kind === "live");
  assert(live?.liveVideo?.endsWith(".mp4"), "Live Photo motion file was not converted");
  const video = newItems.find((item) => item.kind === "video");
  assert(video?.poster?.endsWith(".jpg"), "Standalone video poster is missing");
  assert(newItems.every((item) => item.takenAt && item.src), "Imported date or source is missing");
  assert(new Set(newItems.map((item) => item.id)).size === 20, "Imported item IDs are not unique");

  const eventBlocks = imported.chapters.flatMap((chapter) => chapter.blocks || []).filter((block) => block.type === "event");
  const importedEvents = eventBlocks.filter((block) => block.id !== "existing-event");
  assert(importedEvents.length >= 2, `Automatic date grouping did not create separate event groups: ${importedEvents.length}`);
  const largest = importedEvents.sort((a, b) => (b.items?.length || 0) - (a.items?.length || 0))[0];
  assert((largest.items || []).length >= 19, "Large batch was not kept together by its metadata dates");

  const readerCards = popup.locator(`#${largest.id} .event-preview__item`);
  await popup.locator(`#${largest.id}`).scrollIntoViewIfNeeded();
  assert(await readerCards.count() === largest.items.length, "Reader hid imported files in a large event");
  await popup.close();

  const backups = (await readdir(resolve("content"))).filter((name) => name.startsWith("memories.before-media-import-"));
  assert(backups.length >= 1, "Incremental import did not create a production backup");
  const productionText = await readFile(resolve("content/memories.js"), "utf8");
  assert(productionText.includes("KEEP-ME"), "Production memories.js lost manual metadata");

  // Import the exact same files again. Content-addressed source paths and item
  // IDs must make the operation idempotent rather than duplicating 20 cards.
  await page.locator("#memory-media-import").click();
  await selectImportFiles(page);
  const duplicatePopup = await runImport(page, "Новых файлов не найдено");
  await duplicatePopup.close();
  const afterDuplicate = await currentBook(page);
  const afterDuplicateItems = afterDuplicate.chapters.flatMap((chapter) => chapter.blocks || []).flatMap((block) => block.items || []);
  assert(afterDuplicateItems.length === allItems.length, "Repeated batch import duplicated media items");

  // Add one more file directly into the original, manually edited event.
  await page.locator("#memory-media-import").click();
  await page.locator("[data-import-files]").setInputFiles(resolve(fixture, "target-photo.jpg"));
  await page.locator("[data-import-target]").selectOption("0:0");
  const targetPopup = await runImport(page, "Добавлено 1");
  await targetPopup.close();
  const targeted = await currentBook(page);
  const originalEvent = targeted.chapters[0].blocks[0];
  assert(originalEvent.id === "existing-event", "Target event identity changed");
  assert(originalEvent.caption === "Ручная подпись, которую нельзя потерять", "Target import overwrote the event caption");
  assert(originalEvent.items.length === 2, "Target import did not append exactly one item");
  assert(originalEvent.items.some((item) => item.src !== "preview/incremental-fixture/existing.jpg"), "Target photo is missing");

  // Server-side validation must reject an explicit pair where the second file
  // is another photo instead of a video.
  const invalidPair = await page.evaluate(async () => {
    const batchId = `memory-invalid-${crypto.randomUUID().replace(/-/g, "")}`;
    const upload = async (name, bytes) => {
      const response = await fetch("/api/memory/import/upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Memory-Batch": batchId,
          "X-Memory-Name": encodeURIComponent(name),
          "X-Memory-Modified": String(Date.now()),
        },
        body: bytes,
      });
      return response.json();
    };
    const first = await upload("first.jpg", new Uint8Array([255, 216, 255, 217]));
    const second = await upload("second.jpg", new Uint8Array([255, 216, 255, 217, 0]));
    const response = await fetch("/api/memory/import/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batchId,
        book,
        pairs: [{ photoToken: first.token, videoToken: second.token }],
      }),
    });
    return { status: response.status, body: await response.json() };
  });
  assert(invalidPair.status === 400, "Invalid explicit Live Photo pair was accepted");
  assert(/видео/i.test(invalidPair.body.error || ""), `Invalid-pair error is unclear: ${JSON.stringify(invalidPair)}`);

  console.log(JSON.stringify({
    batchFilesSelected: 21,
    importedItems: 20,
    photos: 18,
    standaloneVideos: 1,
    explicitLivePhotos: 1,
    metadataDateGrouping: true,
    manualEditsPreserved: true,
    productionBackupCreated: true,
    largeEventFullyVisible: true,
    duplicateBatchIdempotent: true,
    targetEventAppend: true,
    invalidLivePairRejected: true,
  }, null, 2));
} finally {
  await browser.close();
}
