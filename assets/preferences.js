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
  let censorshipOff = queryCensorshipOff || sessionCensorshipOff || defaultOff;
  const censoredItems = collectCensored(book);
  const censoredCount = censoredItems.length;

  window.MEMORY_CENSORED_ITEMS = censoredItems;
  applyCensorshipState(censorshipOff, false);

  document.addEventListener("DOMContentLoaded", function () {
    renderSharedAlbum();
    if (settings.readerControlsEnabled === false) return;

    const controls = document.createElement("aside");
    controls.className = "reader-tools";
    controls.setAttribute("aria-label", "Настройки книги");

    const censorButton = document.createElement("button");
    censorButton.type = "button";
    censorButton.className = "reader-tools__button reader-tools__button--censor";
    updateCensorButton(censorButton);
    censorButton.addEventListener("click", function () {
      censorshipOff = !censorshipOff;
      if (censorshipOff) safeSessionSet(storageKey, "1");
      else safeSessionRemove(storageKey);

      const nextUrl = new URL(window.location.href);
      if (censorshipOff) nextUrl.searchParams.set("censor", "off");
      else nextUrl.searchParams.delete("censor");
      try { window.history.replaceState(null, "", nextUrl.toString()); }
      catch (_) { /* file:// and older browsers still keep the in-memory state */ }

      applyCensorshipState(censorshipOff, true);
      updateCensorButton(censorButton);
    });

    const topButton = document.createElement("button");
    topButton.type = "button";
    topButton.className = "reader-tools__button reader-tools__button--top";
    topButton.innerHTML = "<span aria-hidden=\"true\">↑</span><strong>К обложке</strong>";
    topButton.addEventListener("click", function () {
      document.getElementById("cover")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });
    });

    controls.append(censorButton, topButton);
    document.body.appendChild(controls);
  });

  function updateCensorButton(button) {
    button.setAttribute("aria-pressed", censorshipOff ? "true" : "false");
    button.innerHTML = censorshipOff
      ? '<span class="reader-tools__icon" aria-hidden="true"></span><strong>Вернуть цензуру</strong>'
      : `<span class="reader-tools__icon" aria-hidden="true"></span><strong>Показать всё скрытое${censoredCount ? ` · ${censoredCount}` : ""}</strong>`;
  }

  function applyCensorshipState(off, notify) {
    censoredItems.forEach((item) => { item.censored = !off; });
    window.MEMORY_CENSORSHIP_OFF = off;
    document.documentElement.classList.toggle("censorship-off", off);
    if (notify) {
      document.dispatchEvent(new CustomEvent("memory:censorship-change", { detail: { off } }));
    }
  }

  function renderSharedAlbum() {
    const previewMode = params.get("shared") === "1";
    const enabled = previewMode || settings.sharedAlbumEnabled === true;
    const url = String(settings.sharedAlbumUrl || (previewMode ? "https://www.icloud.com/sharedalbum/#demo-memory" : "")).trim();
    if (!enabled || !url) return;

    const mount = document.getElementById("shared-album");
    if (!mount) return;

    const qr = previewMode
      ? "preview/demo-media/shared-album-qr.png"
      : String(settings.sharedAlbumQr || "media/shared-album-qr.png");
    const title = settings.sharedAlbumTitle || "Все фотографии и видео — ещё и в Shared Album";
    const text = settings.sharedAlbumText || "Открой альбом на телефоне или компьютере.";

    mount.hidden = false;
    mount.innerHTML = `
      <article class="shared-album-card">
        <span class="shared-album-card__tape" aria-hidden="true"></span>
        <div class="shared-album-card__copy">
          <p class="shared-album-card__eyebrow">Запасной путь к воспоминаниям</p>
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(text)}</p>
          <a class="shared-album-card__button" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">Открыть Shared Album <span aria-hidden="true">↗</span></a>
          <a class="shared-album-card__url" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
          <button class="shared-album-card__copy-button" type="button">Скопировать ссылку</button>
        </div>
        <a class="shared-album-card__qr" href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer" aria-label="Открыть Shared Album по QR-коду">
          <img src="${escapeAttr(qr)}" alt="QR-код Shared Album" />
          <span>Наведи камеру</span>
        </a>
      </article>`;

    const copyButton = mount.querySelector(".shared-album-card__copy-button");
    copyButton.addEventListener("click", async function () {
      const copied = await copyText(url);
      copyButton.textContent = copied ? "Ссылка скопирована" : "Выдели ссылку выше";
      window.setTimeout(() => { copyButton.textContent = "Скопировать ссылку"; }, 2200);
    });
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_) {
      return false;
    }
  }

  function collectCensored(value) {
    const items = [];
    walkMedia(value, function (item) {
      if (item.censored === true) items.push(item);
    });
    return items;
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

  function escapeHtml(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }
})();
