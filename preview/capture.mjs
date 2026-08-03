import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const output = path.join(root, "preview", "screenshots");
const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
await fs.rm(output, { recursive: true, force: true });
await fs.mkdir(output, { recursive: true });

const browser = await chromium.launch({ headless: true });

async function settle(page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
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

const censoredFrame = desktop.locator(".image-frame.is-censored").first();
await censoredFrame.scrollIntoViewIfNeeded();
await censoredFrame.evaluate((element) => element.closest("button")?.click());
await desktop.locator("#lightbox-censor").waitFor({ state: "visible" });
await shot(desktop, "09-censorship-warning.png", { fullPage: false });
await desktop.locator("#lightbox-censor-show").click();
await desktop.waitForTimeout(120);
await shot(desktop, "10-censorship-revealed.png", { fullPage: false });
await desktop.locator("#lightbox-close").click();

const censorshipButton = desktop.locator(".reader-tools__button--censor");
await censorshipButton.click();
await desktop.waitForLoadState("networkidle");
await desktop.locator("#open-book").click();
await desktop.locator("#ordinary-days").scrollIntoViewIfNeeded();
await desktop.waitForTimeout(250);
await shot(desktop, "11-global-censorship-off.png", { fullPage: false });

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
await mobile.goto(`${base}/${previewQuery}`, { waitUntil: "networkidle" });
await settle(mobile);
await shot(mobile, "12-cover-mobile.png", { fullPage: false });
await mobile.locator("#open-book").click();
await mobile.locator("#ordinary-days").scrollIntoViewIfNeeded();
await mobile.waitForTimeout(220);
await shot(mobile, "13-event-mobile.png", { fullPage: false });
await mobile.locator("#telegram").scrollIntoViewIfNeeded();
await mobile.waitForTimeout(180);
await shot(mobile, "14-telegram-mobile.png", { fullPage: false });
await mobile.locator("#shared-album").scrollIntoViewIfNeeded();
await mobile.waitForTimeout(180);
await shot(mobile, "15-shared-album-mobile.png", { fullPage: false });

const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
await settle(studio);
const populatedChapter = studio.locator("details.chapter").nth(1);
await populatedChapter.evaluate((element) => { element.open = true; });
await studio.evaluate(() => {
  document.querySelectorAll(".item-preview img").forEach((image) => {
    const source = image.getAttribute("src");
    if (source && !/^(?:https?:|data:|blob:|\/|\.\.\/)/.test(source)) image.setAttribute("src", `../${source}`);
  });
});
await populatedChapter.scrollIntoViewIfNeeded();
await studio.waitForTimeout(350);
await shot(studio, "16-memory-studio.png", { fullPage: false });

await browser.close();

const files = (await fs.readdir(output)).sort();
await fs.writeFile(
  path.join(output, "manifest.json"),
  JSON.stringify({ generatedAt: new Date().toISOString(), files }, null, 2),
  "utf8"
);
console.log(`Captured ${files.length} screenshots`);
