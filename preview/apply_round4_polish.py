#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    write(path, text)


# Reader HTML: final override layer, editable open-button label and Live Photo sound control.
replace_once(
    "index.html",
    '  <link rel="stylesheet" href="assets/cursor-scrapbook-pencil-final-v19.css" />',
    '  <link rel="stylesheet" href="assets/cursor-scrapbook-pencil-final-v19.css" />\n  <link rel="stylesheet" href="assets/round4-polish.css" />',
)
replace_once(
    "index.html",
    '        <span>Открыть книгу</span>',
    '        <span id="cover-open-label">Открыть книгу</span>',
)
replace_once(
    "index.html",
    '      <button class="lightbox__live" id="lightbox-live" type="button" hidden>▶ Оживить фото</button>',
    '      <div class="lightbox__live-controls">\n        <button class="lightbox__live" id="lightbox-live" type="button" hidden>▶ Оживить фото</button>\n        <button class="lightbox__sound" id="lightbox-live-sound" type="button" hidden aria-pressed="false" aria-label="Выключить звук" title="Выключить звук">🔊</button>\n      </div>',
)
replace_once(
    "index.html",
    '  <script src="assets/telegram-enhancements.js"></script>',
    '  <script src="assets/telegram-enhancements.js"></script>\n  <script src="assets/round4-polish.js"></script>',
)

# Reader internals: preserve original censorship flags and let the preference layer toggle them without reload.
replace_once(
    "assets/app.js",
    '  restoreReaderChrome();',
    '  restoreReaderChrome();\n  document.addEventListener("memory:censorship-change", (event) => {\n    if (!event.detail?.off) revealedCensored.clear();\n    if (!lightbox.hidden) updateLightbox();\n  });',
)
replace_once(
    "assets/app.js",
    '    const isCensored = item.censored && !locallyRevealed;',
    '    const isCensored = item.censored && !window.MEMORY_CENSORSHIP_OFF && !locallyRevealed;',
)
replace_once(
    "assets/app.js",
    '    frame.dataset.mediaKey = key;',
    '    frame.dataset.mediaKey = key;\n    frame.dataset.censored = item.censored ? "1" : "0";',
)
replace_once(
    "assets/app.js",
    '    if (item.censored && !revealedCensored.has(mediaKey(item))) {',
    '    if (!window.MEMORY_CENSORSHIP_OFF && item.censored && !revealedCensored.has(mediaKey(item))) {',
)
replace_once(
    "assets/app.js",
    '    return Boolean(item && item.censored && !revealedCensored.has(mediaKey(item)));',
    '    return Boolean(item && !window.MEMORY_CENSORSHIP_OFF && item.censored && !revealedCensored.has(mediaKey(item)));',
)

# Preferences are rewritten so censorship toggles in place and uses one geometrically stable icon.
write(
    "assets/preferences.js",
    r'''(function () {
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
''',
)

# Final reader behavior: year labels, reliable active chapter, in-place censorship, adaptive captions,
# Live Photo sound and Telegram scrapbook placement.
write(
    "assets/round4-polish.js",
    r'''(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function initRound4() {
    const data = window.MEMORY_BOOK || { meta: {}, chapters: [] };
    applyEditableCoverMeta(data.meta || {});
    refreshChapterLabels();
    bindReliableChapterState();
    classifyPolaroidCaptions();
    bindCensorshipFrames();
    bindLivePhotoSound();
    arrangeTelegramNotes();

    window.MEMORY_ROUND4 = { refreshChapterLabels, classifyPolaroidCaptions, arrangeTelegramNotes };

    function applyEditableCoverMeta(meta) {
      const openLabel = document.getElementById("cover-open-label");
      if (openLabel && meta.openLabel) openLabel.textContent = meta.openLabel;
      const inner = document.querySelector(".cover__inner");
      if (inner) inner.dataset.archiveLabel = meta.archiveLabel || deriveArchiveLabel(data.chapters || []);
    }

    function deriveArchiveLabel(chapters) {
      const years = chapters.map((chapter) => String(chapter.title || "").match(/\b(?:19|20)\d{2}\b/)?.[0]).filter(Boolean);
      if (!years.length) return "АРХИВ ВОСПОМИНАНИЙ";
      return `АРХИВ · ${years[0]}${years.length > 1 ? `—${years[years.length - 1]}` : ""}`;
    }

    function chapterLabel(chapter, index) {
      const explicit = String(chapter.navLabel || chapter.year || "").trim();
      if (explicit) return explicit;
      const year = String(chapter.title || "").match(/\b(?:19|20)\d{2}\b/)?.[0];
      if (year) return year;
      return String(chapter.number || String(index + 1).padStart(2, "0"));
    }

    function refreshChapterLabels() {
      const chapters = data.chapters || [];
      const pages = [...document.querySelectorAll("#memory-book > .memory-page")];
      const links = [...document.querySelectorAll("#chapter-rail a")];
      chapters.forEach((chapter, index) => {
        const label = chapterLabel(chapter, index);
        const heading = pages[index]?.querySelector(".chapter-heading__number");
        const railLabel = links[index]?.querySelector("span");
        if (heading) heading.textContent = label;
        if (railLabel) railLabel.textContent = label;
      });
    }

    function bindReliableChapterState() {
      const pages = [...document.querySelectorAll("#memory-book > .memory-page")];
      const links = [...document.querySelectorAll("#chapter-rail a")];
      if (!pages.length || !links.length) return;
      let frame = 0;
      const update = () => {
        frame = 0;
        const anchor = window.scrollY + Math.min(window.innerHeight * .34, 360);
        let active = 0;
        pages.forEach((page, index) => { if (page.offsetTop <= anchor) active = index; });
        links.forEach((link, index) => link.classList.toggle("is-active", index === active));
      };
      const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
      window.addEventListener("scroll", schedule, { passive: true });
      window.addEventListener("resize", schedule);
      window.addEventListener("hashchange", schedule);
      links[0].classList.add("is-active");
      update();
    }

    function captionSize(text) {
      const length = [...String(text || "").trim()].length;
      if (length <= 18) return "short";
      if (length <= 42) return "medium";
      return "long";
    }

    function classifyPolaroidCaptions() {
      document.querySelectorAll(".event-preview__caption").forEach((caption) => {
        caption.classList.remove("event-preview__caption--short", "event-preview__caption--medium", "event-preview__caption--long");
        caption.classList.add(`event-preview__caption--${captionSize(caption.textContent)}`);
      });
      document.querySelectorAll(".polaroid figcaption").forEach((caption) => {
        const text = caption.querySelector(".hand-caption")?.textContent || "";
        caption.dataset.captionSize = captionSize(text);
      });
    }

    function bindCensorshipFrames() {
      const apply = (off, forceRestore = false) => {
        document.querySelectorAll(".image-frame[data-censored='1']").forEach((frame) => {
          const shouldHide = !off;
          if (shouldHide) {
            if (forceRestore) frame.classList.remove("is-revealed");
            frame.classList.remove("is-globally-revealed");
            frame.classList.add("is-censored");
            if (!frame.querySelector(".censor-preview")) {
              const cover = document.createElement("span");
              cover.className = "censor-preview";
              cover.innerHTML = "<strong>Содержание скрыто</strong><small>Нажми, чтобы открыть предупреждение</small>";
              frame.appendChild(cover);
            }
          } else {
            frame.classList.remove("is-censored");
            frame.classList.add("is-globally-revealed");
            frame.querySelector(".censor-preview")?.remove();
          }
        });
      };
      apply(Boolean(window.MEMORY_CENSORSHIP_OFF));
      document.addEventListener("memory:censorship-change", (event) => apply(Boolean(event.detail?.off), !event.detail?.off));
    }

    function bindLivePhotoSound() {
      const liveButton = document.getElementById("lightbox-live");
      const soundButton = document.getElementById("lightbox-live-sound");
      const video = document.getElementById("lightbox-video");
      if (!liveButton || !soundButton || !video) return;

      const renderSound = () => {
        const active = !video.hidden && !liveButton.hidden && Boolean(video.currentSrc || video.getAttribute("src"));
        soundButton.hidden = !active;
        if (!active) return;
        soundButton.textContent = video.muted ? "🔇" : "🔊";
        soundButton.setAttribute("aria-pressed", video.muted ? "true" : "false");
        soundButton.setAttribute("aria-label", video.muted ? "Включить звук" : "Выключить звук");
        soundButton.title = video.muted ? "Включить звук" : "Выключить звук";
      };

      liveButton.addEventListener("click", () => {
        requestAnimationFrame(() => {
          if (!video.hidden && (video.currentSrc || video.getAttribute("src"))) {
            video.muted = false;
            video.volume = 1;
            video.play().catch(() => { video.muted = true; renderSound(); });
          }
          renderSound();
        });
      });
      soundButton.addEventListener("click", () => {
        video.muted = !video.muted;
        if (!video.muted) video.play().catch(() => { video.muted = true; });
        renderSound();
      });
      new MutationObserver(renderSound).observe(video, { attributes: true, attributeFilter: ["hidden", "src"] });
      new MutationObserver(renderSound).observe(liveButton, { attributes: true, childList: true, subtree: true });
      video.addEventListener("volumechange", renderSound);
      renderSound();
    }

    function arrangeTelegramNotes() {
      const chapter = window.TELEGRAM_CHAPTER;
      const root = document.getElementById("telegram");
      if (!root || !chapter || !Array.isArray(chapter.blocks)) return;
      const rendered = [...root.querySelectorAll(".chapter-content > .memory-block")];
      const offsetsX = [-.55, .35, -.2, .6, -.4, .25, -.65, .45];
      const offsetsY = [.35, -.25, .7, -.4, .1, .55, -.15, .3];
      chapter.blocks.forEach((block, index) => {
        const element = rendered[index];
        if (!element || block.telegramKind !== "note") return;
        const layout = ["left", "right"].includes(block.layout) ? block.layout : "auto";
        element.classList.add(`telegram-note--layout-${layout}`);
        element.style.setProperty("--telegram-offset-x", `${offsetsX[index % offsetsX.length]}rem`);
        element.style.setProperty("--telegram-offset-y", `${offsetsY[index % offsetsY.length]}rem`);
      });
    }
  });
})();
''',
)

write(
    "assets/round4-polish.css",
    r'''/* Round 4: navigation, censorship, Live Photo sound, captions and Telegram scrapbook flow. */
.cover__inner::before { content: attr(data-archive-label); }

.chapter-heading__number {
  min-width: 4.4rem;
  letter-spacing: .08em;
  white-space: nowrap;
}
.chapter-rail a span {
  width: 2.55rem;
  height: 2.55rem;
  font-size: .55rem;
  letter-spacing: -.02em;
}

.reader-tools__icon {
  position: relative;
  width: 1.18rem;
  height: 1.18rem;
  flex: 0 0 1.18rem;
  display: grid;
  place-items: center;
  border: 2px solid currentColor;
  border-radius: 50%;
}
.reader-tools__icon i {
  width: .48rem;
  height: .48rem;
  border-radius: 50%;
  background: currentColor;
  opacity: 0;
  transform: scale(.35);
  transition: opacity .18s ease, transform .18s ease;
}
.reader-tools__button--censor[aria-pressed="true"] .reader-tools__icon i {
  opacity: 1;
  transform: scale(1);
}
.reader-tools__top-icon { width: 1.18rem; text-align: center; }

.event-preview__item { padding-bottom: 2.65rem; }
.event-preview__item::after {
  left: 14%;
  right: 14%;
  bottom: .56rem;
}
.event-preview__caption {
  left: .72rem;
  right: .72rem;
  bottom: .86rem;
  height: 1.35rem;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-preview__caption--short { font-size: 1.08rem; font-weight: 700; }
.event-preview__caption--medium { font-size: .86rem; font-weight: 650; }
.event-preview__caption--long { font-size: .69rem; font-weight: 650; }
.polaroid figcaption[data-caption-size="short"] .hand-caption { font-size: 1.34rem; line-height: 1.3; text-align: center; }
.polaroid figcaption[data-caption-size="medium"] .hand-caption { font-size: 1.05rem; line-height: 1.42; text-align: center; }
.polaroid figcaption[data-caption-size="long"] .hand-caption {
  display: -webkit-box;
  overflow: hidden;
  font-size: .86rem;
  line-height: 1.35;
  text-align: center;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.lightbox__live-controls {
  grid-column: 1;
  grid-row: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .5rem;
  margin-top: .15rem;
}
.lightbox__live-controls .lightbox__live {
  position: static;
  margin: 0;
  transform: none;
}
.lightbox__sound {
  width: 2.55rem;
  height: 2.55rem;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255,255,255,.7);
  border-radius: 50%;
  padding: 0;
  color: #fff;
  background: rgba(20,18,16,.72);
  cursor: pointer;
  font: 400 1rem/1 var(--sans);
  backdrop-filter: blur(8px);
}
.lightbox__sound:hover { background: rgba(255,255,255,.16); }

#telegram .chapter-content { grid-auto-flow: row dense; }
#telegram .telegram-note {
  position: relative;
  top: var(--telegram-offset-y, 0);
  left: var(--telegram-offset-x, 0);
  width: fit-content;
  max-width: min(100%, 58rem);
}
#telegram .telegram-note .paper-note {
  width: fit-content;
  min-width: min(15rem, 100%);
  max-width: min(100%, 48rem);
  margin: 0;
}
#telegram .telegram-note .paper-note p { max-width: 42rem; }
#telegram .telegram-note--layout-auto { grid-column: 1 / -1; justify-self: center; }
#telegram .telegram-note--layout-left { grid-column: 1 / span 6; justify-self: start; }
#telegram .telegram-note--layout-right { grid-column: 7 / span 6; justify-self: end; }

@media (max-width: 760px) {
  .chapter-heading__number { min-width: 3.5rem; font-size: .64rem; }
  .chapter-rail a span { width: 2.25rem; height: 2.25rem; font-size: .5rem; }
  #telegram .telegram-note--layout-left,
  #telegram .telegram-note--layout-right { grid-column: 1 / -1; justify-self: center; }
  #telegram .telegram-note { left: 0; }
}
''',
)

# Telegram server data model: editable kicker and explicit note placement.
replace_once(
    "tools/telegram_server.py",
    'DEFAULT_STATE: dict[str, Any] = {\n    "title": "То, что осталось в переписке",',
    'DEFAULT_STATE: dict[str, Any] = {\n    "kicker": "Слова, которые остались",\n    "title": "То, что осталось в переписке",',
)
replace_once(
    "tools/telegram_server.py",
    '            "shape": clamp_shape(value.get("shape"), index),\n        }',
    '            "shape": clamp_shape(value.get("shape"), index),\n            "layout": str(value.get("layout") or "auto") if str(value.get("layout") or "auto") in {"auto", "left", "right"} else "auto",\n        }',
)
replace_once(
    "tools/telegram_server.py",
    '    return {\n        "title": str(value.get("title") or DEFAULT_STATE["title"]).strip(),',
    '    return {\n        "kicker": str(value.get("kicker") or DEFAULT_STATE["kicker"]).strip(),\n        "title": str(value.get("title") or DEFAULT_STATE["title"]).strip(),',
)
replace_once(
    "tools/telegram_server.py",
    '                "rotate": rotate,\n            })',
    '                "rotate": rotate,\n                "layout": item.get("layout") if item.get("layout") in {"left", "right"} else "auto",\n            })',
)
replace_once(
    "tools/telegram_server.py",
    '        "kicker": "Слова, которые остались",',
    '        "kicker": state.get("kicker") or DEFAULT_STATE["kicker"],',
)

# Telegram Studio is replaced as a coherent editor rather than patched around the old layout.
write(
    "tools/telegram_studio.html",
    r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Telegram Studio · Memory Site</title>
  <style>
    :root{--paper:#f5ecdd;--ink:#2d2925;--muted:#75695d;--line:#d5c5ad;--accent:#9c3f43;--blue:#4b7692;--danger:#8a3636;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    *{box-sizing:border-box}body{margin:0;color:var(--ink);background:linear-gradient(120deg,#aa987f,#cdbc9f 50%,#9e896d)}button,input,textarea,select{font:inherit}button{cursor:pointer}[hidden]{display:none!important}
    .top{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;padding:.8rem 1rem;color:#fff;background:rgba(35,31,28,.95);backdrop-filter:blur(12px)}
    .top h1{margin:0 auto 0 0;font:700 1rem Georgia,serif}.top button,.top a{border:0;padding:.65rem .9rem;color:#2b2723;background:#f7efdf;text-decoration:none;font-weight:800}.top .primary{color:#fff;background:var(--accent)}.status{width:100%;color:#d8cec0;font-size:.76rem}
    main{width:min(1220px,calc(100% - 2rem));margin:1rem auto 5rem;display:grid;gap:1rem}.panel{padding:1.2rem;background:var(--paper);box-shadow:0 1rem 2.5rem rgba(45,32,20,.2)}
    .intro{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.field{display:grid;gap:.35rem}.field span{font-size:.75rem;font-weight:800}.field input,.field textarea,.field select{width:100%;border:1px solid var(--line);padding:.72rem;background:#fffaf2}.field textarea{min-height:5rem;resize:vertical}
    .builder-head{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap}.builder-head h2{margin:0 auto 0 0;font:700 1.3rem Georgia,serif}.builder-head button{border:1px solid var(--line);padding:.65rem .85rem;background:#fffaf2;font-weight:800}.builder-head .add-note{color:#6e4c25}.builder-head .add-quote{color:#fff;background:var(--blue);border-color:var(--blue)}
    .help{margin:.8rem 0 0;color:var(--muted);font-size:.86rem;line-height:1.55}.blocks{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-flow:row dense;gap:1rem;align-items:start}.empty{grid-column:1/-1;padding:3rem 1rem;text-align:center;color:var(--muted);border:2px dashed rgba(75,61,45,.25)}
    .block{position:relative;grid-column:1/-1;padding:1rem;border:1px solid var(--line);background:#fff9ef;box-shadow:0 .7rem 1.3rem rgba(42,31,20,.12);cursor:grab}.block.note-layout-left{grid-column:1/span 6;transform:translate(-.35rem,.25rem)}.block.note-layout-right{grid-column:7/span 6;transform:translate(.4rem,-.2rem)}.block.dragging{opacity:.35}.block.drop-before{box-shadow:0 -6px 0 var(--blue),0 .7rem 1.3rem rgba(42,31,20,.12)}
    .block-head{display:flex;align-items:center;gap:.55rem;margin-bottom:.8rem}.block-number{display:grid;place-items:center;width:2rem;height:2rem;border-radius:50%;background:#e9dcc7;font-weight:900}.block-kind{font:800 .76rem/1 sans-serif;letter-spacing:.08em;text-transform:uppercase}.block-head .spacer{flex:1}.block-head button{border:0;padding:.45rem .6rem;background:#e7dac7;font-size:.72rem;font-weight:800}.block-head .remove{color:var(--danger);background:#f0d3d3}
    .note-preview{width:fit-content;min-width:min(13rem,100%);max-width:100%;margin:.4rem auto 1rem;padding:1.15rem 1.35rem;background:#f4e4bd;font:400 1.05rem/1.6 Georgia,serif;overflow-wrap:anywhere}.note-preview--shape-0{clip-path:polygon(0 5%,5% 2%,11% 6%,18% 1%,25% 5%,33% 2%,41% 6%,50% 1%,59% 5%,68% 2%,77% 6%,87% 1%,100% 5%,98% 93%,91% 97%,83% 92%,74% 98%,65% 93%,56% 98%,47% 92%,38% 97%,29% 93%,20% 98%,11% 92%,2% 96%)}.note-preview--shape-1{clip-path:polygon(0 3%,8% 6%,16% 2%,24% 7%,33% 1%,43% 5%,53% 2%,63% 7%,73% 2%,84% 6%,93% 1%,100% 4%,97% 96%,89% 92%,80% 98%,70% 93%,60% 97%,50% 92%,40% 98%,30% 93%,19% 97%,9% 92%,1% 95%)}.note-preview--shape-2{clip-path:polygon(0 6%,7% 1%,15% 5%,23% 2%,31% 7%,40% 1%,49% 6%,58% 2%,67% 5%,76% 1%,86% 7%,94% 2%,100% 6%,98% 94%,90% 98%,81% 93%,72% 97%,63% 92%,54% 98%,45% 93%,36% 97%,27% 92%,18% 98%,9% 93%,1% 97%)}.note-preview--shape-3{clip-path:polygon(0 4%,6% 7%,14% 1%,22% 5%,30% 2%,38% 6%,47% 1%,56% 5%,65% 2%,74% 7%,83% 1%,92% 5%,100% 2%,97% 95%,88% 98%,79% 92%,70% 97%,61% 93%,52% 98%,43% 92%,34% 97%,25% 93%,16% 98%,7% 92%,1% 96%)}.note-preview--shape-4{clip-path:polygon(0 2%,9% 6%,18% 1%,27% 5%,36% 2%,45% 7%,54% 1%,63% 5%,72% 2%,81% 6%,90% 1%,100% 5%,98% 97%,89% 92%,80% 98%,71% 93%,62% 97%,53% 92%,44% 98%,35% 93%,26% 97%,17% 92%,8% 98%,1% 94%)}
    .note-fields{display:grid;grid-template-columns:minmax(0,1fr) minmax(12rem,.45fr);gap:.8rem;align-items:start}.quote-grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:1rem}.quote-card{padding:1rem;color:#fff;background:var(--blue)}.quote-card.sonya{background:var(--accent)}.quote-card textarea{min-height:9rem;color:inherit;background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.35)}.quote-card select{color:#2d2925}
    .shot{display:grid;gap:.55rem;align-content:start}.shot-preview{min-height:220px;display:grid;place-items:center;overflow:hidden;border:2px dashed #b7a88f;background:#eee3d1}.shot-preview img{width:100%;height:100%;max-height:300px;object-fit:contain}.shot-preview.is-empty{color:var(--muted);text-align:center;padding:1rem}.shot-tools{display:flex;gap:.45rem;flex-wrap:wrap}.shot-tools button{border:1px solid var(--line);padding:.55rem .7rem;background:#fff;font-weight:800}.shot-tools .remove-shot{color:var(--danger)}.hidden-file{display:none}.progress{position:fixed;right:1rem;bottom:1rem;z-index:40;min-width:18rem;padding:.9rem 1rem;color:#fff;background:#2d2925;box-shadow:0 1rem 3rem rgba(0,0,0,.3)}
    @media(max-width:820px){.intro,.quote-grid,.note-fields{grid-template-columns:1fr}.block.note-layout-left,.block.note-layout-right{grid-column:1/-1;transform:none}.top{position:relative}.shot-preview{min-height:180px}}
  </style>
</head>
<body>
  <header class="top">
    <h1>Telegram Studio</h1>
    <button id="reload" type="button">Перезагрузить</button>
    <a href="../index.html?telegram=1&opened=1#telegram" target="_blank" rel="noopener">Открыть предпросмотр</a>
    <button class="primary" id="save" type="button">Сохранить главу</button>
    <div class="status" id="status">Подключение к локальному серверу…</div>
  </header>
  <main>
    <section class="panel intro">
      <label class="field"><span>Фраза над заголовком</span><input id="kicker" /></label>
      <label class="field"><span>Название главы</span><input id="title" /></label>
      <label class="field"><span>Подзаголовок</span><textarea id="subtitle"></textarea></label>
    </section>
    <section class="panel">
      <div class="builder-head"><h2>Блоки Telegram-главы</h2><button class="add-note" id="add-note" type="button">＋ Записка</button><button class="add-quote" id="add-quote" type="button">＋ Цитата сообщения</button></div>
      <p class="help">Перетаскивай блоки в нужном порядке. Для двух коротких записок на одном уровне поставь первой «слева», второй — «справа»: в книге появятся небольшие случайные смещения, чтобы глава не выглядела построенной по линейке.</p>
    </section>
    <section class="blocks" id="blocks"></section>
  </main>
  <div class="progress" id="progress" hidden></div>
  <script>
    "use strict";
    let state={kicker:"",title:"",subtitle:"",blocks:[]},dragged=-1,dirty=false;
    const $=id=>document.getElementById(id),blocks=$("blocks"),status=$("status"),progress=$("progress");
    load();

    async function load(){
      try{
        const response=await fetch("/api/telegram/state",{cache:"no-store"});if(!response.ok)throw new Error("Не удалось прочитать состояние");
        state=await response.json();if(!Array.isArray(state.blocks))state.blocks=[];
        $("kicker").value=state.kicker||"";$("title").value=state.title||"";$("subtitle").value=state.subtitle||"";
        dirty=false;render();status.textContent="Готово. Всё работает локально и не загружается в интернет.";
      }catch(error){status.textContent=`Ошибка: ${error.message}. Запусти python3 tools/telegram_server.py`;}
    }
    function markDirty(){dirty=true;status.textContent="Есть несохранённые изменения."}
    function uid(prefix){return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`}
    function addNote(){state.blocks.push({id:uid("note"),type:"note",text:"",shape:Math.floor(Math.random()*5),layout:"auto"});markDirty();render(true)}
    function addQuote(){state.blocks.push({id:uid("quote"),type:"quote",text:"",speaker:"sonya",screenshot:"",screenshotName:"",screenshotMode:"paper",shape:Math.floor(Math.random()*5)});markDirty();render(true)}
    function render(scrollToEnd=false){
      blocks.innerHTML="";state.blocks.forEach((block,index)=>blocks.appendChild(block.type==="quote"?renderQuote(block,index):renderNote(block,index)));
      if(!state.blocks.length)blocks.innerHTML='<div class="empty">Добавь первую записку или цитату сообщения.</div>';
      if(scrollToEnd)requestAnimationFrame(()=>blocks.lastElementChild?.scrollIntoView({behavior:"smooth",block:"center"}));
    }
    function shell(block,index,label,shapeButton=false){
      const article=document.createElement("article");article.className="block";article.draggable=true;
      article.innerHTML=`<div class="block-head"><span class="block-number">${index+1}</span><strong class="block-kind">${label}</strong><span class="spacer"></span>${shapeButton?'<button type="button" data-shape>Сменить край</button>':""}<button class="remove" type="button" data-remove>Удалить</button></div>`;
      article.addEventListener("dragstart",event=>{if(event.target.closest("input,textarea,select,button")){event.preventDefault();return}dragged=index;article.classList.add("dragging")});
      article.addEventListener("dragend",()=>{dragged=-1;document.querySelectorAll(".drop-before").forEach(x=>x.classList.remove("drop-before"));article.classList.remove("dragging")});
      article.addEventListener("dragover",event=>{event.preventDefault();article.classList.add("drop-before")});article.addEventListener("dragleave",()=>article.classList.remove("drop-before"));
      article.addEventListener("drop",event=>{event.preventDefault();article.classList.remove("drop-before");if(dragged<0||dragged===index)return;const [moved]=state.blocks.splice(dragged,1);state.blocks.splice(dragged<index?index-1:index,0,moved);markDirty();render()});
      article.querySelector("[data-remove]").addEventListener("click",()=>{state.blocks.splice(index,1);markDirty();render()});
      article.querySelector("[data-shape]")?.addEventListener("click",()=>{block.shape=((Number(block.shape)||0)+1)%5;markDirty();render()});
      return article;
    }
    function renderNote(block,index){
      block.layout=["left","right"].includes(block.layout)?block.layout:"auto";
      const article=shell(block,index,"Записка",true);article.classList.add(`note-layout-${block.layout}`);
      article.insertAdjacentHTML("beforeend",`<div class="note-preview note-preview--shape-${Number(block.shape||0)%5}">${esc(block.text||"Напутствие на рваной бумаге")}</div><div class="note-fields"><label class="field"><span>Текст записки</span><textarea placeholder="Напиши здесь то, что хочешь оставить ей…">${esc(block.text||"")}</textarea></label><label class="field"><span>Расположение</span><select data-layout><option value="auto"${block.layout==="auto"?" selected":""}>Авто · отдельная строка</option><option value="left"${block.layout==="left"?" selected":""}>Слева · половина строки</option><option value="right"${block.layout==="right"?" selected":""}>Справа · половина строки</option></select></label></div>`);
      const preview=article.querySelector(".note-preview"),textarea=article.querySelector("textarea"),layout=article.querySelector("[data-layout]");
      textarea.addEventListener("input",event=>{block.text=event.target.value;preview.textContent=block.text||"Напутствие на рваной бумаге";markDirty()});
      layout.addEventListener("change",event=>{block.layout=event.target.value;markDirty();render()});return article;
    }
    function renderQuote(block,index){
      const article=shell(block,index,"Цитата сообщения");
      article.insertAdjacentHTML("beforeend",`<div class="quote-grid"><div class="quote-card ${block.speaker==="sonya"?"sonya":"me"}"><label class="field"><span>Чья цитата</span><select><option value="sonya"${block.speaker==="sonya"?" selected":""}>Соня — акцентный цвет</option><option value="me"${block.speaker==="me"?" selected":""}>Артём — синий цвет</option></select></label><label class="field"><span>Текст сообщения</span><textarea placeholder="Текст сообщения…">${esc(block.text||"")}</textarea></label></div><div class="shot"><div class="shot-preview ${block.screenshot?"":"is-empty"}">${block.screenshot?`<img src="../${escAttr(block.screenshot)}" alt="" />`:"Скрин сообщения необязателен"}</div><div class="shot-tools"><button type="button" data-upload>${block.screenshot?"Заменить скрин":"Добавить скрин"}</button>${block.screenshot?'<button class="remove-shot" type="button" data-remove-shot>Убрать скрин</button>':""}<input class="hidden-file" type="file" accept="image/png,image/jpeg,image/webp" /></div></div></div>`);
      const select=article.querySelector("select"),textarea=article.querySelector("textarea"),file=article.querySelector("input[type=file]");
      select.addEventListener("change",event=>{block.speaker=event.target.value;markDirty();render()});textarea.addEventListener("input",event=>{block.text=event.target.value;markDirty()});
      article.querySelector("[data-upload]").addEventListener("click",()=>file.click());file.addEventListener("change",()=>uploadScreenshot(file.files[0],block));
      article.querySelector("[data-remove-shot]")?.addEventListener("click",()=>{block.screenshot="";block.screenshotName="";block.screenshotMode="paper";markDirty();render()});return article;
    }
    async function uploadScreenshot(file,block){
      if(!file)return;if(!/^image\/(png|jpeg|webp)$/.test(file.type)){alert("Поддерживаются PNG, JPG и WEBP");return}
      progress.hidden=false;progress.textContent=`Загрузка: ${file.name}`;
      try{const data=await toDataUrl(file),response=await fetch("/api/telegram/upload",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:file.name,data})}),result=await response.json();if(!response.ok)throw new Error(result.error||"Ошибка загрузки");block.screenshot=result.src;block.screenshotName=result.name;block.screenshotMode=result.mode||"paper";markDirty();render()}catch(error){alert(`${file.name}: ${error.message}`)}finally{progress.hidden=true}
    }
    ["kicker","title","subtitle"].forEach(id=>$(id).addEventListener("input",markDirty));
    $("add-note").addEventListener("click",addNote);$("add-quote").addEventListener("click",addQuote);
    $("reload").addEventListener("click",()=>{if(dirty&&!confirm("Перезагрузить конструктор и потерять все несохранённые изменения?"))return;load()});
    $("save").addEventListener("click",async()=>{
      state.kicker=$("kicker").value;state.title=$("title").value;state.subtitle=$("subtitle").value;status.textContent="Сохраняю…";
      try{const response=await fetch("/api/telegram/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(state)}),result=await response.json();if(!response.ok)throw new Error(result.error||"Ошибка сохранения");dirty=false;status.textContent=`Сохранено: ${result.notes} записок и ${result.quotes} цитат. Открой предпросмотр с telegram=1.`}catch(error){status.textContent=`Ошибка сохранения: ${error.message}`}
    });
    window.addEventListener("beforeunload",event=>{if(!dirty)return;event.preventDefault();event.returnValue=""});
    function toDataUrl(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(file)})}
    function esc(value){return String(value).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}
    function escAttr(value){return esc(value).replace(/`/g,"&#096;")}
  </script>
</body>
</html>
''',
)

# Telegram rendered notes receive layout classes and subtle offsets in the final reader.
# The existing enhancement file still handles shapes and optional screenshots.

# Memory Studio extension: editable cover and chapter metadata without rewriting the mature media editor.
replace_once(
    "tools/studio.html",
    '  <title>Memory Studio</title>',
    '  <title>Memory Studio</title>\n  <link rel="stylesheet" href="studio-round4.css" />',
)
replace_once(
    "tools/studio.html",
    '</body>',
    '  <script src="studio-round4.js"></script>\n</body>',
)
write(
    "tools/studio-round4.css",
    r'''.book-settings{margin:1rem 0;padding:1rem 1.2rem;background:#fff8ec;box-shadow:0 .6rem 1.4rem rgba(40,30,20,.12)}
.book-settings h2{margin:0 0 .85rem;font:700 1.15rem Georgia,serif}.book-settings__grid,.chapter-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.book-settings label,.chapter-meta label{display:grid;gap:.3rem;color:#6b5e50;font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}.book-settings input,.book-settings textarea,.chapter-meta input,.chapter-meta textarea{width:100%;border:1px solid var(--line);padding:.6rem;color:var(--ink);background:#fff}.book-settings textarea,.chapter-meta textarea{min-height:4.5rem;resize:vertical}.book-settings .wide,.chapter-meta .wide{grid-column:1/-1}.chapter-meta{margin:0 1.2rem 1rem;padding:1rem;border:1px solid var(--line);background:rgba(255,249,239,.72)}
@media(max-width:720px){.book-settings__grid,.chapter-meta{grid-template-columns:1fr}.book-settings .wide,.chapter-meta .wide{grid-column:auto}}
''',
)
write(
    "tools/studio-round4.js",
    r'''(function () {
  const baseNormalizeBook = normalizeBook;
  normalizeBook = function round4NormalizeBook() {
    baseNormalizeBook();
    book.meta ||= {};
    book.chapters.forEach((chapter) => {
      const year = String(chapter.title || "").match(/\b(?:19|20)\d{2}\b/)?.[0];
      if (year && (!chapter.number || /^\d{1,2}$/.test(String(chapter.number)))) chapter.number = year;
      chapter.kicker ||= "Глава по времени";
      chapter.subtitle ||= "";
    });
    const years = book.chapters.map((chapter) => String(chapter.title || "").match(/\b(?:19|20)\d{2}\b/)?.[0]).filter(Boolean);
    book.meta.archiveLabel ||= years.length ? `АРХИВ · ${years[0]}${years.length > 1 ? `—${years[years.length - 1]}` : ""}` : "АРХИВ ВОСПОМИНАНИЙ";
    book.meta.openLabel ||= "Открыть книгу";
  };

  const baseRenderChapter = renderChapter;
  renderChapter = function round4RenderChapter(chapter, chapterIndex) {
    const details = baseRenderChapter(chapter, chapterIndex);
    const summary = details.querySelector("summary");
    summary.insertAdjacentHTML("afterend", `
      <section class="chapter-meta">
        <label><span>Год / метка главы</span><input data-chapter-field="number" value="${escapeAttr(chapter.number || "")}" /></label>
        <label><span>Надпись над заголовком</span><input data-chapter-field="kicker" value="${escapeAttr(chapter.kicker || "")}" /></label>
        <label><span>Крупный заголовок</span><input data-chapter-field="title" value="${escapeAttr(chapter.title || "")}" /></label>
        <label class="wide"><span>Текст под заголовком</span><textarea data-chapter-field="subtitle">${escapeHtml(chapter.subtitle || "")}</textarea></label>
      </section>`);
    details.querySelectorAll("[data-chapter-field]").forEach((input) => {
      input.addEventListener("change", () => {
        snapshot();
        chapter[input.dataset.chapterField] = input.value;
        render();
      });
    });
    return details;
  };

  const baseRender = render;
  render = function round4Render() {
    baseRender();
    renderBookSettings();
  };

  function renderBookSettings() {
    let panel = document.getElementById("book-settings");
    if (!panel) {
      panel = document.createElement("section");
      panel.id = "book-settings";
      panel.className = "book-settings";
      workspace.before(panel);
    }
    const meta = book.meta ||= {};
    panel.innerHTML = `
      <h2>Обложка и финальная подпись</h2>
      <div class="book-settings__grid">
        ${field("eyebrow", "Маленькая надпись сверху", meta.eyebrow)}
        ${field("archiveLabel", "Боковая архивная метка", meta.archiveLabel)}
        ${field("title", "Главный заголовок", meta.title)}
        ${field("subtitle", "Рукописная подпись", meta.subtitle)}
        ${field("openLabel", "Текст кнопки открытия", meta.openLabel)}
        ${area("note", "Пояснение на обложке", meta.note)}
        ${area("footer", "Финальная подпись после книги", meta.footer, true)}
      </div>`;
    panel.querySelectorAll("[data-meta-field]").forEach((input) => {
      input.addEventListener("change", () => {
        snapshot();
        meta[input.dataset.metaField] = input.value;
        status.textContent = "Подписи книги изменены. Экспортируй memories.js, чтобы применить их.";
      });
    });
  }

  function field(key, label, value) {
    return `<label><span>${label}</span><input data-meta-field="${key}" value="${escapeAttr(value || "")}" /></label>`;
  }
  function area(key, label, value, wide = false) {
    return `<label class="${wide ? "wide" : ""}"><span>${label}</span><textarea data-meta-field="${key}">${escapeHtml(value || "")}</textarea></label>`;
  }

  normalizeBook();
  render();
})();
''',
)

# New imports use real years and grammatically correct event counts by default.
importer = read("tools/import_memories.py")
pattern = re.compile(r"def build_book\(events: list\[Event\]\) -> dict\[str, Any\]:\n[\s\S]*?\n\ndef write_outputs", re.MULTILINE)
replacement = r'''def russian_plural(number: int, one: str, few: str, many: str) -> str:
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return few
    return many


def build_book(events: list[Event]) -> dict[str, Any]:
    by_year: dict[int, list[Event]] = defaultdict(list)
    for event in events:
        by_year[event.start.year].append(event)
    years = sorted(by_year)
    chapters = []
    for chapter_index, year in enumerate(years):
        blocks = []
        for event_index, event in enumerate(by_year[year]):
            blocks.append({
                "type": "event", "id": f"event-{year}-{event_index + 1:03d}", "title": format_event_title(event),
                "caption": "Добавь сюда одну короткую деталь об этом дне.", "date": event.start.isoformat(timespec="minutes"),
                "layout": "stack" if len(event.items) > 8 else "collage", "items": [media_to_dict(item) for item in event.items],
            })
        count = len(by_year[year])
        chapters.append({
            "id": f"year-{year}", "number": str(year), "kicker": "Глава по времени", "title": str(year),
            "subtitle": f"{count} {russian_plural(count, 'событие', 'события', 'событий')}, собранных автоматически по датам, месту и визуальной близости.",
            "layout": LAYOUTS[chapter_index % len(LAYOUTS)], "theme": THEMES[chapter_index % len(THEMES)], "blocks": blocks,
        })
    archive_label = "АРХИВ" if not years else f"АРХИВ · {years[0]}" + (f"—{years[-1]}" if len(years) > 1 else "")
    return {
        "meta": {"eyebrow": "Личная книга воспоминаний", "title": "Наши три года", "subtitle": "Не идеальные. Настоящие.", "note": "Сначала собраны автоматически. Потом — поправлены вручную.", "openLabel": "Открыть книгу", "archiveLabel": archive_label, "footer": "Спасибо за всё, что было между первой и последней страницей.", "accent": "#9c3f43"},
        "chapters": chapters,
    }


def write_outputs'''
importer, count = pattern.subn(replacement, importer, count=1)
if count != 1:
    raise SystemExit("Could not replace build_book in tools/import_memories.py")
write("tools/import_memories.py", importer)

# Functional coverage for the exact regressions reported by the user.
write(
    "preview/verify_round4.mjs",
    r'''import { chromium } from "playwright";

const base = process.env.PREVIEW_URL || "http://127.0.0.1:4173";
const browser = await chromium.launch({ headless: true });
function assert(value, message) { if (!value) throw new Error(message); }

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

  const shortCaption = page.locator('[data-media-key="d01"]').locator("xpath=ancestor::button[1]").locator(".event-preview__caption");
  const longCaption = page.locator('[data-media-key="d05"]').locator("xpath=ancestor::button[1]").locator(".event-preview__caption");
  const shortSize = parseFloat(await shortCaption.evaluate((node) => getComputedStyle(node).fontSize));
  const longSize = parseFloat(await longCaption.evaluate((node) => getComputedStyle(node).fontSize));
  assert(shortSize > longSize, `Adaptive caption sizes are reversed: ${shortSize} <= ${longSize}`);
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

  console.log(JSON.stringify({ activeFirst: true, yearLabels: true, censorshipWithoutScroll: true, adaptiveCaptions: true, liveSound: true }, null, 2));
} finally {
  await browser.close();
}
''',
)
write(
    "preview/verify_telegram_studio_round4.mjs",
    r'''import { chromium } from "playwright";
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
''',
)

# Permanent functional workflow learns about the new scripts and assertions.
workflow = read(".github/workflows/crop-editor-functional.yml")
workflow = workflow.replace(
    '      - "assets/cursor-*.css"',
    '      - "assets/cursor-*.css"\n      - "assets/round4-polish.css"\n      - "assets/round4-polish.js"\n      - "assets/preferences.js"\n      - "assets/production.css"',
)
workflow = workflow.replace(
    '      - "tools/telegram_studio.html"',
    '      - "tools/telegram_studio.html"\n      - "tools/studio-round4.css"\n      - "tools/studio-round4.js"\n      - "preview/verify_round4.mjs"\n      - "preview/verify_telegram_studio_round4.mjs"',
)
workflow = workflow.replace(
    '          node --check assets/telegram-enhancements.js',
    '          node --check assets/telegram-enhancements.js\n          node --check assets/round4-polish.js\n          node --check tools/studio-round4.js',
)
workflow = workflow.replace(
    '          node --check preview/verify_round3.mjs',
    '          node --check preview/verify_round3.mjs\n          node --check preview/verify_round4.mjs\n          node --check preview/verify_telegram_studio_round4.mjs',
)
workflow = workflow.replace(
    '          node preview/verify_round3.mjs\n          node preview/verify_crop_editor.mjs',
    '          node preview/verify_round3.mjs\n          node preview/verify_round4.mjs\n          node preview/verify_crop_editor.mjs',
)
workflow = workflow.replace(
    '          node preview/verify_telegram_studio.mjs',
    '          node preview/verify_telegram_studio.mjs\n          node preview/verify_telegram_studio_round4.mjs',
)
write(".github/workflows/crop-editor-functional.yml", workflow)

print("Round 4 UX patch applied")
