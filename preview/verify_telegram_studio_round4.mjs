import { chromium } from "playwright";
const base = process.env.TELEGRAM_STUDIO_URL || "http://127.0.0.1:8765";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.setDefaultTimeout(20000);
  await page.goto(`${base}/tools/telegram_studio.html`, { waitUntil: "networkidle" });
  await page.locator("#status").filter({ hasText: "Готово" }).waitFor();
  await page.locator("#kicker").fill("Новая редактируемая фраза над заголовком");
  await page.locator("#add-note").click();
  const first = page.locator(".block").last();
  await first.locator("textarea").fill("Короткая записка");
  const before = await first.locator(".note-preview").evaluate((node) => getComputedStyle(node).clipPath);
  await first.locator("[data-shape]").click();
  const refreshed = page.locator(".block").last();
  const after = await refreshed.locator(".note-preview").evaluate((node) => getComputedStyle(node).clipPath);
  assert(before !== after, "Changing note edge did not update constructor preview immediately");
  await refreshed.locator("[data-layout]").selectOption("left");
  await page.locator("#add-note").click();
  const second = page.locator(".block").last();
  await second.locator("textarea").fill("Вторая короткая");
  await second.locator("[data-layout]").selectOption("right");
  const notes = page.locator(".block").filter({ has: page.locator(".note-preview") });
  const a = await notes.nth((await notes.count()) - 2).boundingBox();
  const b = await notes.nth((await notes.count()) - 1).boundingBox();
  assert(a && b && Math.abs(a.y - b.y) < Math.max(a.height, b.height) * .45, "Left and right notes were not placed on one level in Studio");

  let confirmSeen = false;
  page.once("dialog", async (dialog) => { confirmSeen = true; await dialog.dismiss(); });
  await page.locator("#reload").click();
  assert(confirmSeen, "Reload did not ask for confirmation with unsaved changes");
  assert((await page.locator("#kicker").inputValue()).includes("Новая редактируемая"), "Dismissed reload still discarded unsaved data");

  await page.locator("#save").click();
  await page.locator("#status").filter({ hasText: "Сохранено" }).waitFor();
  const state = await page.evaluate(async () => (await fetch("/api/telegram/state", { cache: "no-store" })).json());
  assert(state.kicker === "Новая редактируемая фраза над заголовком", "Editable Telegram kicker was not persisted");
  const savedNotes = state.blocks.filter((block) => block.type === "note").slice(-2);
  assert(savedNotes[0]?.layout === "left" && savedNotes[1]?.layout === "right", `Note placement was not persisted: ${JSON.stringify(savedNotes)}`);
  console.log(JSON.stringify({ liveShapePreview: true, pairedNotes: true, reloadConfirmation: true, editableKicker: true }, null, 2));
} finally { await browser.close(); }
