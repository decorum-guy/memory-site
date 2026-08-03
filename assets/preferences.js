(function () {
  "use strict";

  const settings = window.MEMORY_SETTINGS || {};
  const book = window.MEMORY_BOOK;
  if (!book || !Array.isArray(book.chapters)) return;

  const params = new URLSearchParams(window.location.search);
  const telegramEnabled = params.get("telegram") === "1" || settings.telegramEnabled === true;
  if (telegramEnabled && window.TELEGRAM_CHAPTER && !book.chapters.some((chapter) => chapter.id === "telegram")) {
    book.chapters.push(JSON.parse(JSON.stringify(window.TELEGRAM_CHAPTER)));
  }

  book.chapters = book.chapters.filter((chapter) => chapter.enabled !== false);

  const storageKey = "memory-censorship-disabled";
  const queryCensorshipOff = params.get("censor") === "off";
  const sessionCensorshipOff = safeSessionGet(storageKey) === "1";
  const defaultOff = settings.censorshipEnabledByDefault === false;
  const censorshipOff = queryCensorshipOff || sessionCensorshipOff || defaultOff;
  const censoredCount = countCensored(book);

  if (censorshipOff) {
    revealAllInData(book);
    document.documentElement.classList.add("censorship-off");
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (settings.readerControlsEnabled === false) return;

    const controls = document.createElement("aside");
    controls.className = "reader-tools";
    controls.setAttribute("aria-label", "Настройки книги");

    const censorButton = document.createElement("button");
    censorButton.type = "button";
    censorButton.className = "reader-tools__button reader-tools__button--censor";
    censorButton.setAttribute("aria-pressed", censorshipOff ? "true" : "false");
    censorButton.innerHTML = censorshipOff
      ? "<span>◉</span><strong>Вернуть цензуру</strong>"
      : `<span>◌</span><strong>Показать всё скрытое${censoredCount ? ` · ${censoredCount}` : ""}</strong>`;
    censorButton.addEventListener("click", function () {
      const nextUrl = new URL(window.location.href);
      if (censorshipOff) {
        safeSessionRemove(storageKey);
        nextUrl.searchParams.delete("censor");
      } else {
        safeSessionSet(storageKey, "1");
        nextUrl.searchParams.set("censor", "off");
      }
      window.location.href = nextUrl.toString();
    });

    const topButton = document.createElement("button");
    topButton.type = "button";
    topButton.className = "reader-tools__button reader-tools__button--top";
    topButton.innerHTML = "<span>↑</span><strong>К обложке</strong>";
    topButton.addEventListener("click", function () {
      document.getElementById("cover")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });
    });

    controls.append(censorButton, topButton);
    document.body.appendChild(controls);
  });

  function countCensored(value) {
    let count = 0;
    walkMedia(value, function (item) {
      if (item.censored === true) count += 1;
    });
    return count;
  }

  function revealAllInData(value) {
    walkMedia(value, function (item) {
      item.censored = false;
    });
  }

  function walkMedia(value, visitor) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach((item) => walkMedia(item, visitor));
      return;
    }
    if (value.kind || value.type === "photo" || value.type === "video") visitor(value);
    Object.values(value).forEach((child) => walkMedia(child, visitor));
  }

  function safeSessionGet(key) {
    try { return window.sessionStorage.getItem(key); }
    catch (_) { return null; }
  }

  function safeSessionSet(key, value) {
    try { window.sessionStorage.setItem(key, value); }
    catch (_) { /* query parameter remains the fallback */ }
  }

  function safeSessionRemove(key) {
    try { window.sessionStorage.removeItem(key); }
    catch (_) { /* no-op */ }
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
})();
