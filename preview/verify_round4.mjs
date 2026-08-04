import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }

async function downloadText(download) {
  const stream = await download.createReadStream();
  assert(stream, "Exported memories.js stream is unavailable");
  let text = "";
  for await (const chunk of stream) text += chunk.toString("utf8");
  return text;
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?telegram=1&shared=1`, { waitUntil: "networkidle" });
  await page.locator("#open-book").click();

  await page.locator("#beginning").scrollIntoViewIfNeeded();
  await page.waitForTimeout(220);
  assert(await page.locator("#chapter-rail a").first().evaluate((node) => node.classList.contains("is-active")), "First chapter did not receive active state");

  await page.evaluate(() => { window.MEMORY_BOOK.chapters[0].title = "2023"; window.MEMORY_ROUND4.refreshChapterLabels(); });
  assert((await page.locator("#chapter-rail a span").first().textContent()) === "2023", "Rail did not switch from sequence number to year");
  assert((await page.locator("#beginning .chapter-heading__number").textContent()) === "2023", "Chapter heading did not switch to year");

  await page.locator("#ordinary-days").scrollIntoViewIfNeeded();
  await page.waitForTimeout(160);
  const before = await page.evaluate(() => window.scrollY);
  const censor = page.locator(".reader-tools__button--censor");
  const iconBefore = await censor.locator(".reader-tools__icon").boundingBox();
  await censor.click();
  await page.waitForTimeout(80);
  const afterOff = await page.evaluate(() => window.scrollY);
  assert(Math.abs(afterOff - before) < 6, `Censorship toggle moved the page: ${before} -> ${afterOff}`);
  assert(!(await page.locator('[data-media-key="d04"]').evaluate((node) => node.classList.contains("is-censored"))), "Censored preview stayed hidden after in-place toggle");
  await censor.click();
  await page.waitForTimeout(80);
  const afterOn = await page.evaluate(() => window.scrollY);
  assert(Math.abs(afterOn - before) < 6, `Restoring censorship moved the page: ${before} -> ${afterOn}`);
  assert(await page.locator('[data-media-key="d04"]').evaluate((node) => node.classList.contains("is-censored")), "Censorship was not restored");
  const iconAfter = await censor.locator(".reader-tools__icon").boundingBox();
  assert(iconBefore && iconAfter && Math.abs(iconBefore.width - iconAfter.width) < .5 && Math.abs(iconBefore.height - iconAfter.height) < .5, "Censorship icon geometry changes between states");

  await page.evaluate(() => {
    const captions = [...document.querySelectorAll(".event-preview__caption")];
    if (captions.length < 2) throw new Error("Not enough event captions for adaptive-size verification");
    captions[0].textContent = "Кино";
    captions[1].textContent = "Очень длинная подпись к фотографии, которая обязательно должна стать компактнее и обрезаться";
    window.MEMORY_ROUND4.classifyPolaroidCaptions();
  });
  const shortCaption = page.locator(".event-preview__caption").nth(0);
  const longCaption = page.locator(".event-preview__caption").nth(1);
  assert(await shortCaption.evaluate((node) => node.classList.contains("event-preview__caption--short")), "Short caption was not classified as short");
  assert(await longCaption.evaluate((node) => node.classList.contains("event-preview__caption--long")), "Long caption was not classified as long");
  const shortSize = parseFloat(await shortCaption.evaluate((node) => getComputedStyle(node).fontSize));
  const longSize = parseFloat(await longCaption.evaluate((node) => getComputedStyle(node).fontSize));
  assert(shortSize > longSize, `Adaptive caption sizes are reversed: ${shortSize} <= ${longSize}`);
  const longOverflow = await longCaption.evaluate((node) => ({
    overflow: getComputedStyle(node).overflow,
    textOverflow: getComputedStyle(node).textOverflow,
    whiteSpace: getComputedStyle(node).whiteSpace,
  }));
  assert(longOverflow.overflow === "hidden" && longOverflow.textOverflow === "ellipsis" && longOverflow.whiteSpace === "nowrap", `Long caption is not safely truncated: ${JSON.stringify(longOverflow)}`);
  const captionBottom = parseFloat(await longCaption.evaluate((node) => getComputedStyle(node).bottom));
  const lineBottom = parseFloat(await longCaption.evaluate((node) => getComputedStyle(node.closest("button"), "::after").bottom));
  assert(captionBottom > lineBottom, `Caption is not above the decorative line: ${captionBottom} <= ${lineBottom}`);

  await page.locator("#journeys").scrollIntoViewIfNeeded();
  await page.locator('[data-media-key="t05"]').click();
  await page.locator("#lightbox-live").click();
  await page.waitForTimeout(150);
  const sound = page.locator("#lightbox-live-sound");
  assert(await sound.isVisible(), "Live Photo sound control is hidden during playback");
  assert(!(await page.locator("#lightbox-video").evaluate((video) => video.muted)), "Live Photo did not start with audible sound");
  await sound.click();
  assert(await page.locator("#lightbox-video").evaluate((video) => video.muted), "Mute control did not mute Live Photo");
  await sound.click();
  assert(!(await page.locator("#lightbox-video").evaluate((video) => video.muted)), "Mute control did not restore Live Photo sound");

  const studio = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await studio.goto(`${base}/tools/studio.html`, { waitUntil: "networkidle" });
  await studio.locator("#book-settings").waitFor({ state: "visible" });
  assert(await studio.locator('[data-meta-field="title"]').count() === 1, "Editable cover title field is missing");
  assert(await studio.locator('[data-chapter-field="number"]').count() > 0, "Editable chapter year field is missing");
  assert(await studio.locator('[data-chapter-field="kicker"]').count() > 0, "Editable chapter kicker field is missing");
  assert(await studio.locator('[data-chapter-field="subtitle"]').count() > 0, "Editable chapter subtitle field is missing");

  await studio.locator('[data-meta-field="title"]').fill("Редактируемая обложка");
  await studio.locator('[data-meta-field="title"]').press("Tab");
  await studio.locator('[data-meta-field="openLabel"]').fill("Открыть наши воспоминания");
  await studio.locator('[data-meta-field="openLabel"]').press("Tab");

  const changeChapterField = async (field, value) => {
    const input = studio.locator(`[data-chapter-field="${field}"]`).first();
    await input.fill(value);
    await input.press("Tab");
    await studio.waitForTimeout(60);
  };
  await changeChapterField("number", "2023");
  await changeChapterField("kicker", "Глава, которую можно переименовать");
  await changeChapterField("title", "Наш 2023");
  await changeChapterField("subtitle", "Редактируемый текст под годом и заголовком.");

  const downloadPromise = studio.waitForEvent("download");
  await studio.locator("#export").click();
  const exported = await downloadText(await downloadPromise);
  assert(exported.includes('"title": "Редактируемая обложка"'), "Edited cover title did not reach exported memories.js");
  assert(exported.includes('"openLabel": "Открыть наши воспоминания"'), "Edited cover button label did not reach exported memories.js");
  assert(exported.includes('"number": "2023"'), "Edited chapter year did not reach exported memories.js");
  assert(exported.includes('"kicker": "Глава, которую можно переименовать"'), "Edited chapter kicker did not reach exported memories.js");
  assert(exported.includes('"title": "Наш 2023"'), "Edited chapter title did not reach exported memories.js");
  assert(exported.includes('"subtitle": "Редактируемый текст под годом и заголовком."'), "Edited chapter subtitle did not reach exported memories.js");
  await studio.close();

  console.log(JSON.stringify({
    activeFirst: true,
    yearLabels: true,
    censorshipWithoutScroll: true,
    adaptiveCaptions: true,
    liveSound: true,
    editableBookMetadataExport: true,
  }, null, 2));
} finally {
  await browser.close();
}
