import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const output = path.join(root, "preview", "screenshots");
const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
await fs.rm(output, { recursive: true, force: true });
await fs.mkdir(output, { recursive: true });

const browser = await chromium.launch({ headless: true, args: ["--autoplay-policy=no-user-gesture-required"] });

async function settle(page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    const images = [...document.images];
    images.forEach((image) => { image.loading = "eager"; });
    await Promise.all(images.map((image) => image.complete
      ? Promise.resolve()
      : new Promise((resolve) => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
        })));
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function shot(page, name, options = {}) {
  await page.screenshot({ path: path.join(output, name), animations: "disabled", ...options });
}

const previewQuery = "?telegram=1&shared=1";
const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await desktop.goto(`${base}/${previewQuery}`, { waitUntil: "networkidle" });
await settle(desktop);
await shot(desktop, "01-cover-desktop.png", { fullPage: false });

await desktop.locator("#open-book").click();
await desktop.waitForTimeout(450);

const croppedPhoto = desktop.locator('[data-media-key="d02"] img').first();
const croppedPhotoPosition = await croppedPhoto.evaluate((element) => getComputedStyle(element).objectPosition);
if (!croppedPhotoPosition.includes("24%") || !croppedPhotoPosition.includes("72%")) {
  throw new Error(`Saved photo crop was not applied: ${croppedPhotoPosition}`);
}
const selectedVideoPreview = desktop.locator('[data-media-key="d05"] video').first();
await selectedVideoPreview.waitFor({ state: "attached" });
await selectedVideoPreview.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(250);
await selectedVideoPreview.evaluate((video, expected) => new Promise((resolve, reject) => {
  const deadline = performance.now() + 12000;
  const check = () => {
    if (Math.abs(video.currentTime - expected) <= .35 && video.readyState >= 2) {
      resolve();
      return;
    }
    if (performance.now() >= deadline) {
      reject(new Error(`Timed out waiting for selected frame ${expected}; current=${video.currentTime}; readyState=${video.readyState}`));
      return;
    }
    window.setTimeout(check, 80);
  };
  ["loadedmetadata", "loadeddata", "seeked", "timeupdate", "canplay"].forEach((name) => video.addEventListener(name, check));
  check();
}), 1.2);
const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
  currentTime: video.currentTime,
  objectPosition: getComputedStyle(video).objectPosition
}));
if (Math.abs(selectedVideoState.currentTime - 1.2) > .35) {
  throw new Error(`Selected video frame was not sought: ${selectedVideoState.currentTime}`);
}
if (!selectedVideoState.objectPosition.includes("68%") || !selectedVideoState.objectPosition.includes("34%")) {
  throw new Error(`Saved video crop was not applied: ${selectedVideoState.objectPosition}`);
}

await shot(desktop, "02-book-full-desktop.png", { fullPage: true });

for (const [id, name] of [
  ["beginning", "03-chapter-beginning.png"],
  ["ordinary-days", "04-chapter-events.png"],
  ["journeys", "05-chapter-stack.png"],
  ["telegram", "06-chapter-telegram.png"],
  ["ending", "07-chapter-ending.png"],
]) {
  const section = desktop.locator(`#${id}`);
  await section.scrollIntoViewIfNeeded();
  await desktop.waitForTimeout(160);
  await section.screenshot({ path: path.join(output, name), animations: "disabled" });
}

const sharedAlbum = desktop.locator("#shared-album");
await sharedAlbum.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(180);
await sharedAlbum.screenshot({ path: path.join(output, "08-shared-album.png"), animations: "disabled" });

// Censorship checks run in their own page so sessionStorage and local reveal state cannot leak.
const censorPage = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await censorPage.goto(`${base}/${previewQuery}`, { waitUntil: "networkidle" });
await settle(censorPage);
await censorPage.locator("#open-book").click();
const censoredCover = censorPage.locator("#ordinary-days .censor-preview").first();
await censoredCover.waitFor({ state: "visible" });
await censoredCover.evaluate((element) => element.closest("button")?.click());
await censorPage.locator("#lightbox-censor").waitFor({ state: "visible" });
await shot(censorPage, "09-censorship-warning.png", { fullPage: false });
await censorPage.locator("#lightbox-censor-show").click();
await censorPage.waitForTimeout(120);
await shot(censorPage, "10-censorship-revealed.png", { fullPage: false });
await censorPage.locator("#lightbox-close").click();
await censorPage.locator("#ordinary-days").scrollIntoViewIfNeeded();
await censorPage.waitForTimeout(120);
if (await censorPage.locator("#ordinary-days .censor-preview").count()) {
  throw new Error("Locally revealed censored card became hidden again after closing the lightbox");
}
await shot(censorPage, "11-local-censorship-stays-revealed.png", { fullPage: false });

const censorshipButton = censorPage.locator(".reader-tools__button--censor");
await censorshipButton.click();
await censorPage.waitForLoadState("networkidle");
await censorPage.locator("#open-book").click();
await censorPage.locator("#ordinary-days").scrollIntoViewIfNeeded();
await censorPage.waitForTimeout(250);
await shot(censorPage, "12-global-censorship-off.png", { fullPage: false });
await censorPage.close();

// Regression for applying memories.js and reopening while the browser restores a deep scroll position.
const chromeCheck = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await chromeCheck.goto(`${base}/${previewQuery}&opened=1#ordinary-days`, { waitUntil: "networkidle" });
await chromeCheck.locator("#ordinary-days").scrollIntoViewIfNeeded();
await chromeCheck.waitForTimeout(180);
await chromeCheck.reload({ waitUntil: "networkidle" });
await settle(chromeCheck);
await chromeCheck.locator("#ordinary-days").scrollIntoViewIfNeeded();
await chromeCheck.waitForTimeout(320);
const readerChromeRestored = await chromeCheck.evaluate(() => {
  const rail = document.querySelector("#chapter-rail");
  const tools = document.querySelector(".reader-tools");
  const railVisible = rail && getComputedStyle(rail).opacity !== "0";
  const toolsVisible = tools && getComputedStyle(tools).opacity !== "0";
  return document.body.classList.contains("book-opened") && Boolean(railVisible) && Boolean(toolsVisible);
});
if (!readerChromeRestored) throw new Error("Reader chrome was not restored after a deep reload");
await shot(chromeCheck, "13-reader-chrome-after-deep-reload.png", { fullPage: false });
await chromeCheck.close();

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
await mobile.goto(`${base}/${previewQuery}`, { waitUntil: "networkidle" });
await settle(mobile);
await shot(mobile, "14-cover-mobile.png", { fullPage: false });
await mobile.locator("#open-book").click();
await mobile.locator("#ordinary-days").scrollIntoViewIfNeeded();
await mobile.waitForTimeout(220);
await shot(mobile, "15-event-mobile.png", { fullPage: false });
const telegramMobile = mobile.locator("#telegram .memory-block--collage").first();
await telegramMobile.scrollIntoViewIfNeeded();
await mobile.waitForTimeout(180);
await telegramMobile.screenshot({ path: path.join(output, "16-telegram-mobile.png"), animations: "disabled" });
await mobile.locator("#shared-album").scrollIntoViewIfNeeded();
await mobile.waitForTimeout(180);
await shot(mobile, "17-shared-album-mobile.png", { fullPage: false });

const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
await settle(studio);
const populatedChapter = studio.locator("details.chapter").nth(1);
await populatedChapter.evaluate((element) => { element.open = true; });
await populatedChapter.scrollIntoViewIfNeeded();
await studio.waitForTimeout(350);
if (await studio.locator(".item-preview.is-missing").count()) {
  throw new Error("Memory Studio contains broken photo or video previews");
}
await shot(studio, "18-memory-studio.png", { fullPage: false });
const expandButton = populatedChapter.locator("[data-expand]").first();
await expandButton.click();
const expandedCard = populatedChapter.locator(".item.is-expanded").first();
await expandedCard.scrollIntoViewIfNeeded();
await studio.waitForTimeout(140);
await shot(studio, "19-memory-studio-expanded-caption.png", { fullPage: false });

const firstPhotoItem = populatedChapter.locator(".item").filter({ hasText: "PHOTO" }).first();
await firstPhotoItem.locator(".item-preview").hover();
await firstPhotoItem.locator("[data-crop]").click();
await studio.locator("#crop-dialog").waitFor({ state: "visible" });
await shot(studio, "20-studio-crop-editor.png", { fullPage: false });
const cropStage = studio.locator("#crop-stage");
const cropBox = await cropStage.boundingBox();
if (!cropBox) throw new Error("Crop stage has no bounding box");
await studio.mouse.move(cropBox.x + cropBox.width / 2, cropBox.y + cropBox.height / 2);
await studio.mouse.down();
await studio.mouse.move(cropBox.x + cropBox.width / 2 + 70, cropBox.y + cropBox.height / 2 - 45, { steps: 8 });
await studio.mouse.up();
const cropPositionText = await studio.locator("#crop-position").textContent();
if (!cropPositionText || cropPositionText.includes("X 50% · Y 50%")) {
  throw new Error("Dragging inside crop editor did not change crop position");
}
await studio.locator("#crop-save").click();
await studio.locator("#crop-dialog").waitFor({ state: "hidden" });

const videoItem = populatedChapter.locator(".item").filter({ hasText: "VIDEO" }).first();
await videoItem.locator(".item-preview").hover();
await videoItem.locator("[data-crop]").click();
await studio.locator("#open-frame-picker").click();
await studio.locator("#frame-view").waitFor({ state: "visible" });
await studio.locator("#frame-video").evaluate((video) => new Promise((resolve) => {
  if (video.readyState >= 1) resolve();
  else video.addEventListener("loadedmetadata", resolve, { once: true });
}));
await studio.locator("#frame-range").evaluate((range) => {
  range.value = "2.1";
  range.dispatchEvent(new Event("input", { bubbles: true }));
});
await studio.waitForTimeout(180);
await shot(studio, "21-studio-video-frame-picker.png", { fullPage: false });
await studio.locator("#frame-save").click();
await studio.locator("#crop-view").waitFor({ state: "visible" });
const cropVideo = studio.locator("#crop-stage video");
await cropVideo.waitFor({ state: "attached" });
await cropVideo.evaluate((video) => new Promise((resolve) => {
  if (video.readyState >= 2 && Math.abs(video.currentTime - 2.1) < .4) resolve();
  else {
    video.addEventListener("seeked", resolve, { once: true });
    window.setTimeout(resolve, 3000);
  }
}));
const cropVideoTime = await cropVideo.evaluate((video) => video.currentTime);
if (Math.abs(cropVideoTime - 2.1) > .4) {
  throw new Error(`Saved frame did not return to crop editor: ${cropVideoTime}`);
}
await shot(studio, "22-studio-video-frame-in-polaroid.png", { fullPage: false });

await studio.locator("#open-frame-picker").click();
await studio.locator("#frame-video").evaluate((video) => new Promise((resolve) => {
  if (video.readyState >= 1) resolve();
  else video.addEventListener("loadedmetadata", resolve, { once: true });
}));
await studio.locator("#frame-range").evaluate((range) => {
  range.value = "3.1";
  range.dispatchEvent(new Event("input", { bubbles: true }));
});
await studio.locator("#frame-cancel").click();
await studio.locator("#open-frame-picker").click();
await studio.locator("#frame-video").evaluate((video) => new Promise((resolve) => {
  if (video.readyState >= 1) resolve();
  else video.addEventListener("loadedmetadata", resolve, { once: true });
}));
const restoredFrameTime = await studio.locator("#frame-video").evaluate((video) => video.currentTime);
if (Math.abs(restoredFrameTime - 2.1) > .4) {
  throw new Error(`Frame picker cancel did not restore previous frame: ${restoredFrameTime}`);
}
await studio.locator("#frame-range").evaluate((range) => {
  range.value = "2.6";
  range.dispatchEvent(new Event("input", { bubbles: true }));
});
await studio.locator("#frame-save-exit").click();
await studio.locator("#crop-dialog").waitFor({ state: "hidden" });

const exported = studio.waitForEvent("download");
await studio.locator("#export").click();
const download = await exported;
const exportPath = path.join(output, "studio-export-test.js");
await download.saveAs(exportPath);
const exportedText = await fs.readFile(exportPath, "utf8");
if (!exportedText.includes('"crop"') || !exportedText.includes('"posterTime": 2.6')) {
  throw new Error("Studio export does not contain crop and selected video frame settings");
}
await fs.rm(exportPath, { force: true });

const singleEvent = desktop.locator("#ordinary-days .memory-block--event").first();
await singleEvent.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(120);
await singleEvent.screenshot({ path: path.join(output, "23-single-row-event.png"), animations: "disabled" });
const eightEvent = desktop.locator("#journeys .memory-block--event").first();
await eightEvent.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(120);
await eightEvent.screenshot({ path: path.join(output, "24-eight-item-event.png"), animations: "disabled" });
const rightmostItem = eightEvent.locator(".event-preview__item--8");
await rightmostItem.hover();
await desktop.waitForTimeout(120);
await eightEvent.screenshot({ path: path.join(output, "25-eight-item-hover-layer.png"), animations: "disabled" });

await browser.close();

const files = (await fs.readdir(output)).sort();
await fs.writeFile(
  path.join(output, "manifest.json"),
  JSON.stringify({ generatedAt: new Date().toISOString(), files }, null, 2),
  "utf8"
);
console.log(`Captured ${files.length} screenshots`);