import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);

  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  const cover = await page.evaluate(() => {
    const seal = document.querySelector(".cover__seal");
    const title = document.querySelector(".cover__title");
    return {
      sealWidth: seal.getBoundingClientRect().width,
      heartSize: parseFloat(getComputedStyle(seal.querySelector("span")).fontSize),
      titleLetterSpacing: parseFloat(getComputedStyle(title).letterSpacing),
    };
  });
  assert(cover.sealWidth >= 118, `cover seal is still too small: ${JSON.stringify(cover)}`);
  assert(cover.heartSize >= 44, `cover heart is still too small: ${JSON.stringify(cover)}`);
  assert(cover.titleLetterSpacing > -1, `cover title tracking is still too tight: ${JSON.stringify(cover)}`);

  await page.goto(`${base}/?telegram=1&opened=1#telegram`, { waitUntil: "networkidle" });
  await page.locator("#telegram").scrollIntoViewIfNeeded();
  assert(await page.locator("#telegram .telegram-note").count() >= 1, "Telegram note block was not enhanced");
  assert(await page.locator("#telegram .telegram-message--sonya").count() >= 1, "Sonya quote style is missing");
  assert(await page.locator("#telegram .telegram-message--me").count() >= 1, "Artem quote style is missing");
  assert(await page.locator("#telegram .telegram-message__shot").count() >= 1, "Optional Telegram screenshot is missing");
  await page.locator("#telegram .telegram-message__shot").first().click();
  await page.locator("#telegram-shot-modal:not([hidden])").waitFor();
  await page.keyboard.press("Escape");

  await page.goto(`${base}/?opened=1`, { waitUntil: "networkidle" });
  const liveBadge = page.locator(".media-badge--live").first();
  await liveBadge.waitFor({ state: "visible" });
  await liveBadge.locator("xpath=ancestor::button[1]").click();
  const liveButton = page.locator("#lightbox-live");
  await liveButton.waitFor({ state: "visible" });

  async function assertNoOverlap(label) {
    const geometry = await page.evaluate(() => {
      const caption = document.getElementById("lightbox-caption").getBoundingClientRect();
      const button = document.getElementById("lightbox-live").getBoundingClientRect();
      return {
        captionTop: caption.top,
        captionBottom: caption.bottom,
        buttonTop: button.top,
        buttonBottom: button.bottom,
      };
    });
    assert(geometry.buttonTop >= geometry.captionBottom - 1, `${label}: Live Photo button overlaps caption: ${JSON.stringify(geometry)}`);
  }

  await assertNoOverlap("idle");
  await liveButton.click();
  await page.waitForTimeout(400);
  await assertNoOverlap("playing");

  console.log(JSON.stringify({ cover, telegram: "ok", liveControls: "ok" }, null, 2));
} finally {
  await browser.close();
}
