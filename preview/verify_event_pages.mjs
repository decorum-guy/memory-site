import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${base}/?opened=1`, { waitUntil: "networkidle" });

  const event = page.locator(".memory-block--event").first();
  await event.scrollIntoViewIfNeeded();
  const cards = event.locator(".event-preview__item");
  assert(await cards.count() === 13, `Expected 13 event cards, got ${await cards.count()}`);

  const firstBox = await cards.nth(0).boundingBox();
  const lastBox = await cards.nth(12).boundingBox();
  const previewBox = await event.locator(".event-preview").boundingBox();
  assert(firstBox && lastBox && previewBox, "Event geometry is unavailable");
  assert(lastBox.y > firstBox.y + firstBox.height, "All cards stayed in one row instead of growing the event vertically");
  assert(previewBox.height > firstBox.height * 4, "Event preview did not grow for all full-size rows");

  const firstCard = cards.nth(0);
  const caption = firstCard.locator(".event-preview__caption");
  const cardBox = await firstCard.boundingBox();
  const frameBox = await firstCard.locator(".image-frame").boundingBox();
  const captionBox = await caption.boundingBox();
  assert(cardBox && frameBox && captionBox, "Polaroid geometry is unavailable");

  const cardState = await firstCard.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      aspectRatio: style.aspectRatio,
      paddingTop: parseFloat(style.paddingTop),
      paddingRight: parseFloat(style.paddingRight),
      paddingBottom: parseFloat(style.paddingBottom),
      width: node.getBoundingClientRect().width,
      height: node.getBoundingClientRect().height,
    };
  });
  assert(cardState.aspectRatio === "4 / 5", `Original 4:5 polaroid proportion was lost: ${JSON.stringify(cardState)}`);
  assert(cardState.width >= 260, `Desktop polaroid became too small: ${JSON.stringify(cardState)}`);
  assert(cardState.paddingTop >= 8 && cardState.paddingRight >= 8, `Top/side paper margin collapsed: ${JSON.stringify(cardState)}`);
  assert(cardState.paddingBottom >= 40, `Lower white paper strip collapsed: ${JSON.stringify(cardState)}`);
  assert(frameBox.x >= cardBox.x + 7 && frameBox.y >= cardBox.y + 7, "Photo touches the top or side card edge");
  assert(cardBox.y + cardBox.height - (frameBox.y + frameBox.height) >= 60, "White lower polaroid area is no longer visible");

  assert(captionBox.x >= cardBox.x, "Caption escapes the left card edge");
  assert(captionBox.x + captionBox.width <= cardBox.x + cardBox.width, "Caption escapes the right card edge");

  const captionState = await caption.evaluate((node) => {
    const style = getComputedStyle(node);
    const frame = node.parentElement.querySelector(".image-frame");
    return {
      whiteSpace: style.whiteSpace,
      lineClamp: style.webkitLineClamp,
      overflowWrap: style.overflowWrap,
      overflow: style.overflow,
      clientHeight: node.clientHeight,
      scrollHeight: node.scrollHeight,
      width: node.getBoundingClientRect().width,
      cardWidth: node.closest(".event-preview__item").getBoundingClientRect().width,
      frameBottom: frame.offsetTop + frame.offsetHeight,
      captionTop: node.offsetTop,
    };
  });
  assert(captionState.captionTop >= captionState.frameBottom + 4, "Caption overlaps the photo or has no upper gap");
  assert(captionState.whiteSpace === "normal", "Caption is still forced into one line");
  assert(captionState.lineClamp === "4", `Expected four-line clamp, got ${captionState.lineClamp}`);
  assert(["anywhere", "break-word"].includes(captionState.overflowWrap), "Long words cannot wrap inside the caption");
  assert(captionState.overflow === "hidden", "Overflowing caption is not clipped");
  assert(captionState.scrollHeight > captionState.clientHeight, "Long fixture caption was not actually clamped");
  assert(captionState.width <= captionState.cardWidth * 0.8, "Caption is wider than the decorative lower rule");

  await cards.nth(12).click();
  await page.locator("#lightbox-counter").waitFor({ state: "visible" });
  assert((await page.locator("#lightbox-counter").textContent())?.trim() === "13 / 13", "Last visible card did not open the thirteenth item");
  await page.locator("#lightbox-close").click();

  const favicon = page.locator('link[rel="icon"]');
  assert(await favicon.count() === 1, "Offline favicon link is missing");
  assert((await favicon.getAttribute("href")) === "assets/memory-book-icon.svg", "Unexpected favicon path");

  console.log(JSON.stringify({
    renderedCards: 13,
    multiRowHeight: true,
    originalPolaroidSize: true,
    originalPaperMargins: true,
    captionBelowMedia: true,
    captionFourLineClamp: true,
    lastCardOpensCorrectItem: true,
    offlineFavicon: true,
  }, null, 2));
} finally {
  await browser.close();
}
