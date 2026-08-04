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
  const censoredCount = countCensored(book);
  window.MEMORY_CENSORSHIP_OFF = censorshipOff;
  document.documentElement.classList.toggle("censorship-off", censorshipOff);

  document.addEventListener("DOMContentLoaded", function () {
    renderSharedAlbum();
    if (settings.readerControlsEnabled === false) return;

    const controls = document.createElement("aside");
    controls.className = "reader-tools";
    controls.setAttribute("aria-label", "Настройки книги");

    const censorButton = document.createElement("button");
    censorButton.type = "button";
    censorButton.className = "reader-tools__button reader-tools__button--censor";
    updateCensorButton();
    censorButton.addEventListener("click", function () {
      const scrollX = window.scrollX;
      const scrollY = window.scrollY;
      censorshipOff = !censorshipOff;
      window.MEMORY_CENSORSHIP_OFF = censorshipOff;
      document.documentElement.classList.toggle("censorship-off", censorshipOff);

      const nextUrl = new URL(window.location.href);
      if (censorshipOff) {
        safeSessionSet(storageKey, "1");
        nextUrl.searchParams.set("censor", "off");
      } else {
        safeSessionRemove(storageKey);
        nextUrl.searchParams.delete("censor");
      }
      try { history.replaceState(history.state, "", nextUrl); }
      catch (_) { /* file:// keeps working even when history is restricted */ }

      updateCensorButton();
      document.dispatchEvent(new CustomEvent("memory:censorship-change", { detail: { off: censorshipOff } }));
      requestAnimationFrame(() => window.scrollTo(scrollX, scrollY));
    });

    const topButton = document.createElement("button");
    topButton.type = "button";
    topButton.className = "reader-tools__button reader-tools__button--top";
    topButton.innerHTML = '<span class="reader-tools__top-icon" aria-hidden="true">↑</span><strong>К обложке</strong>';
    topButton.addEventListener("click", function () {
      document.getElementById("cover")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });
    });

    controls.append(censorButton, topButton);
    document.body.appendChild(controls);

    function updateCensorButton() {
      censorButton.setAttribute("aria-pressed", censorshipOff ? "true" : "false");
      censorButton.innerHTML = censorshipOff
        ? '<span class="reader-tools__icon" aria-hidden="true"><i></i></span><strong>Вернуть цензуру</strong>'
        : `<span class="reader-tools__icon" aria-hidden="true"><i></i></span><strong>Показать всё скрытое${censoredCount ? ` · ${censoredCount}` : ""}</strong>`;
    }
  });

  function renderSharedAlbum() {
    const previewMode = params.get("shared") === "1";
    const enabled = previewMode || settings.sharedAlbumEnabled === true;
    const url = String(settings.sharedAlbumUrl || (previewMode ? "https://www.icloud.com/sharedalbum/#demo-memory" : "")).trim();
    if (!enabled || !url) return;

    const mount = document.getElementById("shared-album");
    if (!mount) return;
    const qr = previewMode ? "preview/demo-media/shared-album-qr.png" : String(settings.sharedAlbumQr || "media/shared-album-qr.png");
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
    try { await navigator.clipboard.writeText(value); return true; }
    catch (_) { return false; }
  }

  function countCensored(value) {
    let count = 0;
    walkMedia(value, (item) => { if (item.censored === true) count += 1; });
    return count;
  }

  function walkMedia(value, visitor) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) { value.forEach((item) => walkMedia(item, visitor)); return; }
    if (value.kind || value.type === "photo" || value.type === "video") visitor(value);
    Object.values(value).forEach((child) => walkMedia(child, visitor));
  }

  function safeSessionGet(key) { try { return window.sessionStorage.getItem(key); } catch (_) { return null; } }
  function safeSessionSet(key, value) { try { window.sessionStorage.setItem(key, value); } catch (_) {} }
  function safeSessionRemove(key) { try { window.sessionStorage.removeItem(key); } catch (_) {} }
  function prefersReducedMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function escapeHtml(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
  function escapeAttr(value) { return escapeHtml(value).replace(/`/g, "&#096;"); }
})();
