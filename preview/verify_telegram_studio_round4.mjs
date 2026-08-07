import { chromium } from "playwright";

const base = process.env.TELEGRAM_STUDIO_URL || "http://127.0.0.1:8765";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }

try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.setDefaultTimeout(20000);
  await page.goto(`${base}/tools/telegram_studio.html`, { waitUntil: "networkidle" });
  await page.locator("#status").filter({ hasText: "Готово" }).waitFor();

  assert(await page.locator(".studio-tabs a").count() === 2, "For You Studio does not expose both Studio tabs");
  assert((await page.locator(".studio-tabs a.is-active").textContent())?.trim() === "For You", "For You tab is not active");
  assert(await page.locator("#add-quote").count() === 0, "Legacy quote control is still available");

  await page.locator("#kicker").fill("Новая редактируемая фраза над заголовком");
  await page.locator("#add-note").click();
  const first = page.locator(".block").last();
  await first.locator("textarea").fill("Короткое пожелание");
  const before = await first.locator(".note-preview").evaluate((node) => getComputedStyle(node).clipPath);
  await first.locator("[data-shape]").click();
  const refreshed = page.locator(".block").last();
  const after = await refreshed.locator(".note-preview").evaluate((node) => getComputedStyle(node).clipPath);
  assert(before !== after, "Changing wish edge did not update constructor preview immediately");
  await refreshed.locator("[data-layout]").selectOption("left");

  await page.locator("#add-note").click();
  const second = page.locator(".block").last();
  await second.locator("textarea").fill("Второе короткое пожелание");
  await second.locator("[data-layout]").selectOption("right");

  const wishes = page.locator(".block").filter({ has: page.locator(".note-preview") });
  const a = await wishes.nth((await wishes.count()) - 2).boundingBox();
  const b = await wishes.nth((await wishes.count()) - 1).boundingBox();
  assert(a && b && Math.abs(a.y - b.y) < Math.max(a.height, b.height) * .45, "Left and right wishes were not placed on one level in Studio");

  let confirmSeen = false;
  page.once("dialog", async (dialog) => { confirmSeen = true; await dialog.dismiss(); });
  await page.locator("#reload").click();
  assert(confirmSeen, "Reload did not ask for confirmation with unsaved changes");
  assert((await page.locator("#kicker").inputValue()).includes("Новая редактируемая"), "Dismissed reload still discarded unsaved data");

  await page.locator("#save").click();
  await page.locator("#status").filter({ hasText: "Сохранено пожеланий" }).waitFor();
  const state = await page.evaluate(async () => (await fetch(`/api/telegram/state?verify=${Date.now()}`, { cache: "no-store" })).json());
  assert(state.kicker === "Новая редактируемая фраза над заголовком", "Editable For You kicker was not persisted");
  assert(state.title === "For You", `For You title changed unexpectedly: ${JSON.stringify(state)}`);
  assert(state.blocks.every((block) => block.type === "note"), `Non-note blocks survived: ${JSON.stringify(state.blocks)}`);
  const savedWishes = state.blocks.slice(-2);
  assert(savedWishes[0]?.layout === "left" && savedWishes[1]?.layout === "right", `Wish placement was not persisted: ${JSON.stringify(savedWishes)}`);

  const reader = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  let chapterResponse = null;
  reader.on("response", (response) => {
    if (new URL(response.url()).pathname === "/content/telegram.js") chapterResponse = response;
  });
  await reader.goto(`${base}/index.html?telegram=1&opened=1&verify=${Date.now()}#telegram`, { waitUntil: "networkidle" });
  await reader.locator("#telegram .telegram-note").first().waitFor({ state: "visible" });
  const renderedWishes = reader.locator("#telegram .telegram-note");
  assert(await renderedWishes.count() >= 2, "Saved For You wishes did not reach the reader preview");
  assert((await reader.locator("#telegram .chapter-title").textContent())?.includes("For You"), "Reader lost the For You chapter title");

  const renderedLeft = renderedWishes.filter({ hasText: "Короткое пожелание" });
  const renderedRight = renderedWishes.filter({ hasText: "Второе короткое пожелание" });
  assert(await renderedLeft.evaluate((node) => node.classList.contains("telegram-note--layout-left")), "Left wish layout was not applied in reader preview");
  assert(await renderedRight.evaluate((node) => node.classList.contains("telegram-note--layout-right")), "Right wish layout was not applied in reader preview");
  const leftBox = await renderedLeft.boundingBox();
  const rightBox = await renderedRight.boundingBox();
  assert(leftBox && rightBox && Math.abs(leftBox.y - rightBox.y) < Math.max(leftBox.height, rightBox.height) * .55, "Saved left/right wishes are not on the same level in reader preview");
  assert(chapterResponse, "Reader did not request content/telegram.js");
  assert((await chapterResponse.headerValue("cache-control"))?.includes("no-store"), "For You chapter response can still be served from stale browser cache");
  await reader.close();

  console.log(JSON.stringify({
    studioTabs: true,
    forYouBranding: true,
    noteOnlyWorkflow: true,
    liveShapePreview: true,
    pairedWishes: true,
    reloadConfirmation: true,
    editableKicker: true,
    savedWishesVisibleInReader: true,
    chapterPreviewNoCache: true,
  }, null, 2));
} finally {
  await browser.close();
}
