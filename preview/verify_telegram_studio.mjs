import { chromium } from "playwright";

const base = process.env.TELEGRAM_STUDIO_URL || "http://127.0.0.1:8765";
const browser = await chromium.launch({ headless: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function shapeNumber(className) {
  const match = String(className || "").match(/note-preview--shape-(\d+)/i);
  return match ? Number(match[1]) : null;
}

try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.setDefaultTimeout(20000);
  await page.goto(`${base}/tools/telegram_studio.html`, { waitUntil: "networkidle" });
  await page.locator("#status").filter({ hasText: "Готово" }).waitFor();

  await page.locator("#add-note").click();
  const note = page.locator(".block").last();
  await note.locator("textarea").fill("Моя тестовая записка для Сони.");
  const initialShape = shapeNumber(await note.locator(".note-preview").getAttribute("class"));
  await note.locator("[data-shape]").click();
  const changedNote = page.locator(".block").first();
  const changedShape = shapeNumber(await changedNote.locator(".note-preview").getAttribute("class"));
  assert(Number.isInteger(initialShape) && Number.isInteger(changedShape), "Could not read torn-paper shape classes");
  assert(changedShape !== initialShape, `Shape control did not change the edge: ${initialShape} -> ${changedShape}`);

  await page.locator("#add-quote").click();
  const quote = page.locator(".block").last();
  await quote.locator("select").selectOption("me");
  await quote.locator("textarea").fill("Тестовое сообщение от Артёма.");
  const fileInput = quote.locator("input[type=file]");
  await fileInput.setInputFiles("media/telegram/chat-05.jpg");
  await quote.locator(".shot-preview img").waitFor({ state: "visible" });

  await page.locator("#add-note").click();
  const disposable = page.locator(".block").last();
  await disposable.locator("[data-remove]").click();
  assert(await page.locator(".block").count() === 2, "Telegram block remove control did not work after rendering");

  await page.locator("#save").click();
  await page.locator("#status").filter({ hasText: "Сохранено" }).waitFor();

  const state = await page.evaluate(async () => {
    const response = await fetch("/api/telegram/state", { cache: "no-store" });
    return response.json();
  });
  assert(state.blocks.length === 2, `Unexpected saved block count: ${JSON.stringify(state)}`);
  assert(state.blocks[0].type === "note", `First block is not a note: ${JSON.stringify(state.blocks[0])}`);
  assert(state.blocks[0].shape === changedShape, `Shape control did not persist: expected ${changedShape}, got ${JSON.stringify(state.blocks[0])}`);
  assert(state.blocks[1].type === "quote" && state.blocks[1].speaker === "me", `Speaker did not persist: ${JSON.stringify(state.blocks[1])}`);
  assert(Boolean(state.blocks[1].screenshot), `Optional screenshot did not persist: ${JSON.stringify(state.blocks[1])}`);

  const generated = await page.evaluate(async () => {
    const response = await fetch("/content/telegram.js", { cache: "no-store" });
    return response.text();
  });
  assert(generated.includes('"telegramKind": "note"'), "Generated chapter has no note block");
  assert(generated.includes('"speaker": "me"'), "Generated chapter has no Artem quote");
  assert(generated.includes('"screenshot": "media/telegram/'), "Generated chapter has no optional screenshot");

  console.log(JSON.stringify({
    initialShape,
    changedShape,
    blocks: state.blocks.map(({ type, speaker, shape, screenshot }) => ({ type, speaker, shape, screenshot: Boolean(screenshot) })),
    generated: "ok",
  }, null, 2));
} finally {
  await browser.close();
}
