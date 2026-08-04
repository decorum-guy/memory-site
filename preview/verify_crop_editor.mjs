import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const output = path.join(process.cwd(), "preview", "crop-verification-output");
await fs.rm(output, { recursive: true, force: true });
await fs.mkdir(output, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ["--autoplay-policy=no-user-gesture-required"],
});

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function waitForVideoMetadata(videoLocator) {
  await videoLocator.evaluate((video) => new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("video metadata timeout")), 10000);
    const done = () => {
      window.clearTimeout(timer);
      resolve();
    };
    if (video.readyState >= 1) done();
    else video.addEventListener("loadedmetadata", done, { once: true });
  }));
}

async function setRange(page, selector, value) {
  await page.locator(selector).evaluate((range, nextValue) => {
    range.value = String(nextValue);
    range.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}

try {
  const reader = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  reader.setDefaultTimeout(15000);
  await reader.goto(`${base}/?opened=1#ordinary-days`, { waitUntil: "networkidle" });

  const croppedPhoto = reader.locator('[data-media-key="d02"] img').first();
  await croppedPhoto.waitFor({ state: "visible" });
  const photoPosition = await croppedPhoto.evaluate((image) => getComputedStyle(image).objectPosition);
  assert(photoPosition.includes("24%") && photoPosition.includes("72%"), `book ignored saved photo crop: ${photoPosition}`);

  const selectedVideo = reader.locator('[data-media-key="d05"] video').first();
  await selectedVideo.scrollIntoViewIfNeeded();
  await reader.waitForFunction(() => {
    const video = document.querySelector('[data-media-key="d05"] video');
    return Boolean(video && video.readyState >= 2 && Math.abs(video.currentTime - 1.2) <= .35);
  }, null, { timeout: 15000 });
  const readerVideoState = await selectedVideo.evaluate((video) => ({
    currentTime: video.currentTime,
    objectPosition: getComputedStyle(video).objectPosition,
    paused: video.paused,
  }));
  assert(readerVideoState.objectPosition.includes("68%") && readerVideoState.objectPosition.includes("34%"), `book ignored saved video crop: ${readerVideoState.objectPosition}`);
  assert(readerVideoState.paused, "selected video preview frame is still playing");
  await reader.close();

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  studio.setDefaultTimeout(15000);
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });

  const ordinaryChapter = studio.locator("details.chapter").nth(1);
  await ordinaryChapter.evaluate((element) => { element.open = true; });
  await ordinaryChapter.scrollIntoViewIfNeeded();

  const firstPhotoItem = ordinaryChapter.locator(".item-meta").filter({ hasText: /^PHOTO$/ }).first().locator("../..");
  await firstPhotoItem.locator(".item-preview").hover();
  await firstPhotoItem.locator("[data-crop]").click();
  await studio.locator("#crop-dialog").waitFor({ state: "visible" });

  const cropStage = studio.locator("#crop-stage");
  const cropBox = await cropStage.boundingBox();
  assert(cropBox, "photo crop stage has no bounding box");
  await studio.mouse.move(cropBox.x + cropBox.width / 2, cropBox.y + cropBox.height / 2);
  await studio.mouse.down();
  await studio.mouse.move(cropBox.x + cropBox.width / 2 + 80, cropBox.y + cropBox.height / 2 - 55, { steps: 8 });
  await studio.mouse.up();
  const movedPosition = await studio.locator("#crop-position").textContent();
  assert(movedPosition && !movedPosition.includes("X 50% · Y 50%"), `photo dragging did not change position: ${movedPosition}`);
  await studio.locator("#crop-save").click();
  await studio.locator("#crop-dialog").waitFor({ state: "hidden" });

  await firstPhotoItem.locator(".item-preview").hover();
  await firstPhotoItem.locator("[data-crop]").click();
  const savedPosition = await studio.locator("#crop-position").textContent();
  const secondBox = await cropStage.boundingBox();
  assert(secondBox, "reopened photo crop stage has no bounding box");
  await studio.mouse.move(secondBox.x + secondBox.width / 2, secondBox.y + secondBox.height / 2);
  await studio.mouse.down();
  await studio.mouse.move(secondBox.x + secondBox.width / 2 - 90, secondBox.y + secondBox.height / 2 + 45, { steps: 8 });
  await studio.mouse.up();
  await studio.locator("#crop-cancel").click();
  await studio.locator("#crop-dialog").waitFor({ state: "hidden" });
  await firstPhotoItem.locator(".item-preview").hover();
  await firstPhotoItem.locator("[data-crop]").click();
  const restoredCropAfterCancel = await studio.locator("#crop-position").textContent();
  assert(restoredCropAfterCancel === savedPosition, `crop cancel changed committed position: ${savedPosition} -> ${restoredCropAfterCancel}`);
  await studio.locator("#crop-cancel").click();

  const videoItem = ordinaryChapter.locator(".item-meta").filter({ hasText: /^VIDEO/ }).first().locator("../..");
  await videoItem.scrollIntoViewIfNeeded();
  await videoItem.locator(".item-preview").hover();
  await videoItem.locator("[data-crop]").click();
  await studio.locator("#crop-dialog").waitFor({ state: "visible" });
  const videoCropState = await studio.evaluate(() => ({
    frameButtonHidden: document.getElementById("open-frame-picker")?.hidden,
    cropMediaTag: document.querySelector("#crop-stage [data-crop-media]")?.tagName,
    cropDialogOpen: document.getElementById("crop-dialog")?.open,
  }));
  assert(videoCropState.cropDialogOpen, `video crop dialog did not open: ${JSON.stringify(videoCropState)}`);
  assert(videoCropState.frameButtonHidden === false, `video frame button stayed hidden: ${JSON.stringify(videoCropState)}`);
  assert(videoCropState.cropMediaTag === "VIDEO", `video crop editor did not render a video preview: ${JSON.stringify(videoCropState)}`);
  await studio.locator("#open-frame-picker").click();
  await studio.locator("#frame-view").waitFor({ state: "visible" });
  await waitForVideoMetadata(studio.locator("#frame-video"));

  await setRange(studio, "#frame-range", 2.1);
  await studio.locator("#frame-save").click();
  await studio.locator("#crop-view").waitFor({ state: "visible" });
  const cropVideo = studio.locator("#crop-stage video");
  await cropVideo.waitFor({ state: "attached" });
  await studio.waitForFunction(() => {
    const video = document.querySelector("#crop-stage video");
    return Boolean(video && video.readyState >= 2 && Math.abs(video.currentTime - 2.1) <= .4);
  }, null, { timeout: 15000 });

  await studio.locator("#open-frame-picker").click();
  await waitForVideoMetadata(studio.locator("#frame-video"));
  await setRange(studio, "#frame-range", 3.1);
  await studio.locator("#frame-cancel").click();
  await studio.locator("#open-frame-picker").click();
  await waitForVideoMetadata(studio.locator("#frame-video"));
  const restoredFrameValue = Number(await studio.locator("#frame-range").inputValue());
  assert(Math.abs(restoredFrameValue - 2.1) <= .4, `frame cancel did not restore committed time: ${restoredFrameValue}`);

  await setRange(studio, "#frame-range", 2.6);
  await studio.locator("#frame-save-exit").click();
  await studio.locator("#crop-dialog").waitFor({ state: "hidden" });

  const journeysChapter = studio.locator("details.chapter").nth(2);
  await journeysChapter.evaluate((element) => { element.open = true; });
  const liveItem = journeysChapter.locator(".item-meta").filter({ hasText: /^LIVE$/ }).first().locator("../..");
  await liveItem.scrollIntoViewIfNeeded();
  await liveItem.locator(".item-preview").hover();
  await liveItem.locator("[data-crop]").click();
  await studio.locator("#crop-dialog").waitFor({ state: "visible" });
  assert(await studio.locator("#open-frame-picker").isHidden(), "Live Photo unexpectedly exposes regular-video timeline picker");
  await studio.locator("#crop-cancel").click();

  const downloadPromise = studio.waitForEvent("download");
  await studio.locator("#export").click();
  const download = await downloadPromise;
  const exportPath = path.join(output, "memories.crop-verified.js");
  await download.saveAs(exportPath);
  const exportedText = await fs.readFile(exportPath, "utf8");
  assert(exportedText.includes('"crop"'), "Studio export does not contain crop metadata");
  assert(exportedText.includes('"posterTime": 2.6'), "Studio export does not contain the saved-and-exited video frame time");

  const report = {
    photoPosition,
    readerVideoState,
    movedPosition,
    savedPosition,
    restoredCropAfterCancel,
    restoredFrameValue,
    videoCropState,
    exportedCrop: true,
    exportedPosterTime: 2.6,
    liveTimelineHidden: true,
  };
  await fs.writeFile(path.join(output, "report.json"), JSON.stringify(report, null, 2), "utf8");
  console.log("Crop editor functional verification passed", report);
} finally {
  await browser.close();
}
