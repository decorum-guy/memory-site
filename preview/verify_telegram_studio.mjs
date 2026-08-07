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

  assert((await page.title()).startsWith("For You Studio"), `Unexpected Studio title: ${await page.title()}`);
  assert((await page.locator(".studio-tabs a.is-active").textContent())?.trim() === "For You", "For You tab is not active");
  assert(await page.locator("#add-quote").count() === 0, "Legacy quote button is still visible");
  assert(await page.locator("#title").inputValue() === "For You", "For You title is not the default");

  await page.locator("#add-note").click();
  const first = page.locator(".block").last();
  await first.locator("textarea").fill("Первое тестовое пожелание для Сони.");
  const initialShape = shapeNumber(await first.locator(".note-preview").getAttribute("class"));
  await first.locator("[data-shape]").click();
  const changedFirst = page.locator(".block").last();
  const changedShape = shapeNumber(await changedFirst.locator(".note-preview").getAttribute("class"));
  assert(Number.isInteger(initialShape) && Number.isInteger(changedShape), "Could not read torn-paper shape classes");
  assert(changedShape !== initialShape, `Shape control did not change the edge: ${initialShape} -> ${changedShape}`);
  await changedFirst.locator("[data-layout]").selectOption("left");

  await page.locator("#add-note").click();
  const second = page.locator(".block").last();
  await second.locator("textarea").fill("Второе тестовое пожелание.");
  await second.locator("[data-layout]").selectOption("right");

  await page.locator("#add-note").click();
  const disposable = page.locator(".block").last();
  await disposable.locator("[data-remove]").click();
  assert(await page.locator(".block").count() === 2, "Wish remove control did not work after rendering");

  await page.locator("#save").click();
  await page.locator("#status").filter({ hasText: "Сохранено пожеланий: 2" }).waitFor();

  const state = await page.evaluate(async () => {
    const response = await fetch("/api/telegram/state", { cache: "no-store" });
    return response.json();
  });
  assert(state.title === "For You", `For You title did not persist: ${JSON.stringify(state)}`);
  assert(state.blocks.length === 2, `Unexpected saved block count: ${JSON.stringify(state)}`);
  assert(state.blocks.every((block) => block.type === "note"), `Non-note blocks survived: ${JSON.stringify(state.blocks)}`);
  assert(state.blocks[0].shape === changedShape, `Shape control did not persist: expected ${changedShape}, got ${JSON.stringify(state.blocks[0])}`);
  assert(state.blocks[0].layout === "left" && state.blocks[1].layout === "right", `Wish placement did not persist: ${JSON.stringify(state.blocks)}`);

  const generated = await page.evaluate(async () => {
    const response = await fetch("/content/telegram.js", { cache: "no-store" });
    return response.text();
  });
  assert(generated.includes('"title": "For You"'), "Generated chapter lost the For You title");
  assert(generated.includes('"number": "FY"'), "Generated chapter still exposes the TG rail label");
  assert((generated.match(/"telegramKind": "note"/g) || []).length === 2, "Generated chapter has the wrong number of wishes");
  assert(!generated.includes('"telegramKind": "message"'), "Generated chapter still contains message quotes");

  console.log(JSON.stringify({
    forYouStudio: true,
    legacyQuotesRemoved: true,
    initialShape,
    changedShape,
    wishes: state.blocks.map(({ type, shape, layout }) => ({ type, shape, layout })),
    generated: "ok",
  }, null, 2));
} finally {
  await browser.close();
}
