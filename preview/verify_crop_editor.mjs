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

async function waitForFrameSelection(page, expected) {
  await page.waitForFunction((target) => {
    const range = document.getElementById("frame-range");
    const video = document.getElementById("frame-video");
    const state = window.MEMORY_FRAME_PICKER?.getState?.();
    return Boolean(
      range
      && video
      && state
      && state.pendingTime === null
      && Math.abs(Number(range.value) - target) <= .08
      && Math.abs(state.draftTime - target) <= .08
      && Math.abs(video.currentTime - target) <= .4
    );
  }, expected, { timeout: 15000 });
}

try {
  const reader = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  reader.setDefaultTimeout(15000);
  await reader.goto(`${base}/?opened=1#ordinary-days`, { waitUntil: "networkidle" });

  const cursorState = await reader.evaluate(() => ({
    finePointer: matchMedia("(hover: hover) and (pointer: fine)").matches,
    bodyCursor: getComputedStyle(document.body).cursor,
    openButtonCursor: getComputedStyle(document.getElementById("open-book")).cursor,
    stylesheetLoaded: [...document.styleSheets].some((sheet) =>
      String(sheet.href || "").includes("cursor-scrapbook-pencil-final-v19.css")
    ),
  }));
  assert(cursorState.stylesheetLoaded, `custom cursor stylesheet was not loaded: ${JSON.stringify(cursorState)}`);
  assert(cursorState.finePointer, `desktop Chromium did not expose a fine pointer: ${JSON.stringify(cursorState)}`);
  assert(cursorState.bodyCursor.includes("scrapbook-pencil-final-v19"), `custom body cursor was not applied: ${JSON.stringify(cursorState)}`);
  assert(cursorState.openButtonCursor.includes("scrapbook-pencil-final-v19"), `custom interactive cursor was not applied: ${JSON.stringify(cursorState)}`);

  const croppedPhoto = reader.locator('[data-media-key="d02"] img').first();
  await croppedPhoto.waitFor({ state: "visible" });
  const photoPosition = await croppedPhoto.evaluate((image) => getComputedStyle(image).objectPosition);
  assert(photoPosition.includes("24%") && photoPosition.includes("72%"), `book ignored saved photo crop: ${photoPosition}`);

  const selectedVideo = reader.locator('[data-media-key="d05"] video').first();
  await selectedVideo.waitFor({ state: "attached" });
  await selectedVideo.scrollIntoViewIfNeeded();
  await selectedVideo.evaluate(async (video, expected) => {
  const sourceUrl = video.currentSrc || video.getAttribute("src") || video.src;
  const configuredTime = Number(video.dataset.posterTime);
  if (!sourceUrl) throw new Error("Selected-frame video has no source URL");
  if (!Number.isFinite(configuredTime) || Math.abs(configuredTime - expected) > 0.001) {
    throw new Error(`Runtime did not preserve posterTime: ${video.dataset.posterTime}`);
  }

  const waitUntil = async (predicate, timeout, message) => {
    const deadline = performance.now() + timeout;
    while (!predicate()) {
      if (performance.now() >= deadline) throw new Error(message());
      await new Promise((resolve) => window.setTimeout(resolve, 80));
    }
  };

  let usedBlobFallback = false;
  let responseStatus = null;
  let sourceBytes = null;

  try {
    await waitUntil(
      () => video.readyState >= 2 && Math.abs(video.currentTime - expected) <= 0.35,
      3000,
      () => "runtime preview frame was not decoded within the grace period"
    );
  } catch {
    const response = await fetch(sourceUrl, { cache: "no-store" });
    responseStatus = response.status;
    if (!response.ok) {
      throw new Error(`Selected-frame source request failed: ${response.status} ${sourceUrl}`);
    }
    const blob = await response.blob();
    sourceBytes = blob.size;
    if (!blob.size) throw new Error(`Selected-frame source is empty: ${sourceUrl}`);

    const objectUrl = URL.createObjectURL(blob);
    usedBlobFallback = true;
    video.muted = true;
    video.preload = "auto";
    video.src = objectUrl;

    await new Promise((resolve, reject) => {
      const timer = window.setTimeout(
        () => reject(new Error(`Timed out loading fetched video metadata: ${sourceUrl}`)),
        10000
      );
      const done = () => {
        window.clearTimeout(timer);
        resolve();
      };
      const fail = () => {
        window.clearTimeout(timer);
        reject(new Error(`Fetched video could not be decoded: ${sourceUrl}`));
      };
      video.addEventListener("loadedmetadata", done, { once: true });
      video.addEventListener("error", fail, { once: true });
      try { video.load(); } catch (error) { fail(error); }
    });

    try { await video.play(); } catch {}
    try { video.currentTime = expected; } catch (error) {
      throw new Error(`Could not seek fetched video: ${error?.message || error}`);
    }
    await waitUntil(
      () => video.readyState >= 2 && Math.abs(video.currentTime - expected) <= 0.35,
      10000,
      () => `Timed out decoding fetched selected frame ${expected}; current=${video.currentTime}; readyState=${video.readyState}`
    );
  }

  video.pause();
  if (video.readyState < 2 || Math.abs(video.currentTime - expected) > 0.35) {
    throw new Error(`Selected frame mismatch after verification: current=${video.currentTime}; readyState=${video.readyState}`);
  }
  video.dataset.verificationSourceUrl = sourceUrl;
  video.dataset.verificationBlobFallback = String(usedBlobFallback);
  if (responseStatus !== null) video.dataset.verificationResponseStatus = String(responseStatus);
  if (sourceBytes !== null) video.dataset.verificationSourceBytes = String(sourceBytes);
}, 1.2);
  const readerVideoState = await selectedVideo.evaluate((video) => ({
    currentTime: video.currentTime,
    objectPosition: getComputedStyle(video).objectPosition,
    paused: video.paused,
    sourceUrl: video.dataset.verificationSourceUrl || video.currentSrc || video.src,
    usedBlobFallback: video.dataset.verificationBlobFallback === "true",
    responseStatus: Number(video.dataset.verificationResponseStatus || 0) || null,
    sourceBytes: Number(video.dataset.verificationSourceBytes || 0) || null,
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
  assert(await studio.evaluate(() => Boolean(window.MEMORY_FRAME_PICKER?.getState)), "Stable frame-picker controller is missing");

  const playbackStarted = await studio.locator("#frame-video").evaluate(async (video) => {
    try { await video.play(); } catch {}
    return !video.paused;
  });
  assert(playbackStarted, "Frame-picker video could not start for seek-while-playing verification");
  await studio.waitForTimeout(120);

  // Two immediate range changes reproduce the browser race that previously let
  // an older timeupdate/seeked event reset the control to the beginning.
  await setRange(studio, "#frame-range", 1.4);
  await setRange(studio, "#frame-range", 2.1);
  const immediateFrameState = await studio.evaluate(() => ({
    range: Number(document.getElementById("frame-range")?.value),
    label: document.getElementById("frame-current")?.textContent,
    ...window.MEMORY_FRAME_PICKER.getState(),
  }));
  assert(immediateFrameState.paused, `Dragging the frame slider did not pause playback: ${JSON.stringify(immediateFrameState)}`);
  assert(Math.abs(immediateFrameState.range - 2.1) <= .08, `Slider immediately jumped away from the newest target: ${JSON.stringify(immediateFrameState)}`);

  await waitForFrameSelection(studio, 2.1);
  await studio.waitForTimeout(350);
  const settledFrameState = await studio.evaluate(() => ({
    range: Number(document.getElementById("frame-range")?.value),
    label: document.getElementById("frame-current")?.textContent,
    ...window.MEMORY_FRAME_PICKER.getState(),
  }));
  assert(Math.abs(settledFrameState.range - 2.1) <= .08, `Slider returned to zero after asynchronous media events: ${JSON.stringify(settledFrameState)}`);
  assert(Math.abs(settledFrameState.draftTime - 2.1) <= .08, `Draft frame time was lost: ${JSON.stringify(settledFrameState)}`);
  assert(settledFrameState.pendingTime === null, `Latest frame seek never settled: ${JSON.stringify(settledFrameState)}`);

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
  await waitForFrameSelection(studio, 2.1);
  await setRange(studio, "#frame-range", 3.1);
  await studio.waitForTimeout(250);
  const unsavedFrameValue = Number(await studio.locator("#frame-range").inputValue());
  assert(Math.abs(unsavedFrameValue - 3.1) <= .08, `Second non-zero selection jumped away before cancel: ${unsavedFrameValue}`);
  await studio.locator("#frame-cancel").click();
  await studio.locator("#open-frame-picker").click();
  await waitForVideoMetadata(studio.locator("#frame-video"));
  await waitForFrameSelection(studio, 2.1);
  const restoredFrameValue = Number(await studio.locator("#frame-range").inputValue());
  assert(Math.abs(restoredFrameValue - 2.1) <= .4, `frame cancel did not restore committed time: ${restoredFrameValue}`);

  // Save immediately, without waiting for the physical seek to finish. The
  // selected slider value must win over a stale currentTime from the video.
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
    cursorState,
    photoPosition,
    readerVideoState,
    movedPosition,
    savedPosition,
    restoredCropAfterCancel,
    immediateFrameState,
    settledFrameState,
    restoredFrameValue,
    videoCropState,
    exportedCrop: true,
    exportedPosterTime: 2.6,
    rapidSeekLatestWins: true,
    sliderPausesPlayback: true,
    immediateSaveUsesDraftTime: true,
    liveTimelineHidden: true,
  };
  await fs.writeFile(path.join(output, "report.json"), JSON.stringify(report, null, 2), "utf8");
  console.log("Crop editor and cursor functional verification passed", report);
} finally {
  await browser.close();
}
