#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Не найден фрагмент для {label}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count == 0:
        raise RuntimeError(f"Не найден regex-фрагмент для {label}")
    return updated


def patch_core() -> None:
    # 1. Крестик внутри предупреждения цензуры.
    path = "index.html"
    text = read(path)
    text = replace_once(
        text,
        '<div class="lightbox__censor-card">\n          <span aria-hidden="true">!</span>',
        '<div class="lightbox__censor-card">\n          <button class="lightbox__censor-close" id="lightbox-censor-close" type="button" aria-label="Закрыть предупреждение">×</button>\n          <span aria-hidden="true">!</span>',
        "censor close button",
    )
    write(path, text)

    # 2–4, 9. Галерея, раскрытие цензуры, подписи и слои.
    path = "assets/app.js"
    text = read(path)
    text = replace_once(
        text,
        '  const lightboxCensorShow = byId("lightbox-censor-show");',
        '  const lightboxCensorShow = byId("lightbox-censor-show");\n  const lightboxCensorClose = byId("lightbox-censor-close");',
        "censor close const",
    )
    text = replace_once(
        text,
        '  observeChapters();',
        '  observeChapters();\n  restoreReaderChrome();',
        "reader chrome init",
    )

    event_function = r'''  function renderEventBlock(wrapper, block, uniqueId) {
    const items = (block.items || []).map(normalizeMedia);
    const layout = block.layout || (items.length > 8 ? "stack" : "collage");
    const previewItems = items.filter((item) => item.kind !== "audio").slice(0, layout === "stack" ? 5 : 8);
    wrapper.classList.add(`event-layout-${safeClass(layout)}`, `event-count-${Math.min(items.length, 8)}`);
    wrapper.innerHTML = `
      <header class="event-heading">
        <div>
          <p class="event-heading__date">${escapeHtml(block.title || formatDate(block.date))}</p>
          ${renderCaption(block.caption || "", block.captionStyle || "scribble", uniqueId)}
        </div>
        <button class="event-open" type="button">Открыть ${items.length} ${plural(items.length, "момент", "момента", "моментов")}</button>
      </header>
      <div class="event-preview" aria-label="Предпросмотр события"></div>
    `;
    const preview = wrapper.querySelector(".event-preview");
    previewItems.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `event-preview__item event-preview__item--${(index % 8) + 1}`;
      button.style.setProperty("--event-rotate", `${[-5, 3, -2, 6, -4, 2, -1, 4][index % 8]}deg`);
      button.setAttribute("aria-label", item.censored ? `Открыть скрытый элемент ${index + 1}` : `Открыть элемент ${index + 1}`);
      button.appendChild(createMediaPreview(item));
      const note = mediaNote(item);
      if (note) {
        const label = document.createElement("span");
        label.className = "event-preview__caption";
        label.textContent = note;
        label.title = note;
        button.appendChild(label);
      }
      button.addEventListener("click", () => openGallery(items, items.indexOf(item)));
      preview.appendChild(button);
    });
    const count = document.createElement("span");
    count.className = "event-preview__count";
    count.textContent = `${items.length} файлов`;
    preview.appendChild(count);
    wrapper.querySelector(".event-open").addEventListener("click", () => openGallery(items, 0));
    return wrapper;
  }

'''
    text = regex_once(
        text,
        r"  function renderEventBlock\(wrapper, block, uniqueId\) \{.*?\n  \}\n\n  function renderPhotoBlock",
        event_function + "  function renderPhotoBlock",
        "renderEventBlock",
    )

    preview_function = r'''  function createMediaPreview(item) {
    const frame = document.createElement("span");
    const key = mediaKey(item);
    const locallyRevealed = revealedCensored.has(key);
    const isCensored = item.censored && !locallyRevealed;
    frame.className = `image-frame media-kind-${safeClass(item.kind)}`;
    frame.dataset.mediaKey = key;
    frame.classList.toggle("is-censored", isCensored);
    frame.classList.toggle("is-revealed", locallyRevealed);

    const image = document.createElement("img");
    image.src = item.thumb || item.poster || item.src || "";
    image.alt = isCensored ? "Скрытое воспоминание" : (item.alt || (item.kind === "video" ? "Видео из воспоминаний" : "Фотография из воспоминаний"));
    image.loading = "lazy";
    image.decoding = "async";

    const placeholder = document.createElement("span");
    placeholder.className = "image-placeholder";
    placeholder.innerHTML = `<span>файл не найден</span><small>${escapeHtml(item.src || "")}</small>`;
    image.addEventListener("error", () => frame.classList.add("is-missing"));
    image.addEventListener("load", () => frame.classList.remove("is-missing"));
    frame.append(image, placeholder);

    if (item.kind === "live") {
      const badge = document.createElement("span");
      badge.className = "media-badge media-badge--live";
      badge.textContent = "LIVE";
      frame.appendChild(badge);
    } else if (item.kind === "video") {
      const badge = document.createElement("span");
      badge.className = "media-badge media-badge--video";
      badge.textContent = item.duration ? `▶ ${formatDuration(item.duration)}` : "▶ VIDEO";
      frame.appendChild(badge);
    }

    if (isCensored) {
      const cover = document.createElement("span");
      cover.className = "censor-preview";
      cover.innerHTML = "<strong>Содержание скрыто</strong><small>Нажми, чтобы открыть предупреждение</small>";
      frame.appendChild(cover);
    }
    return frame;
  }

'''
    text = regex_once(
        text,
        r"  function createMediaPreview\(item\) \{.*?\n  \}\n\n  function renderRail",
        preview_function + "  function renderRail",
        "createMediaPreview",
    )

    text = replace_once(
        text,
        '    lightboxCensorShow.addEventListener("click", revealCurrentCensored);',
        '    lightboxCensorShow.addEventListener("click", revealCurrentCensored);\n    lightboxCensorClose.addEventListener("click", closeGallery);',
        "bind censor close",
    )
    text = replace_once(
        text,
        '    previousFocus = document.activeElement;\n    revealedCensored.clear();\n    updateLightbox();',
        '    previousFocus = document.activeElement;\n    updateLightbox();',
        "keep revealed state",
    )
    text = replace_once(
        text,
        '    lightboxCaption.textContent = item.caption || item.alt || "";',
        '    lightboxCaption.innerHTML = renderMediaCaption(item);',
        "lightbox two captions",
    )
    text = replace_once(
        text,
        '    revealedCensored.add(mediaKey(item));\n    lightboxCensor.hidden = true;',
        '    revealedCensored.add(mediaKey(item));\n    revealPreviewCopies(item);\n    lightboxCensor.hidden = true;',
        "reveal preview copies",
    )

    normalize_function = r'''  function normalizeMedia(item) {
    const inferred = item.kind || (item.liveVideo ? "live" : item.poster ? "video" : "photo");
    const takenAt = item.takenAt || "";
    const rawCaption = item.caption || item.note || "";
    return {
      id: item.id || "",
      kind: inferred,
      src: item.src || "",
      thumb: item.thumb || "",
      poster: item.poster || "",
      liveVideo: item.liveVideo || "",
      alt: item.alt || (inferred === "video" ? "Видео из воспоминаний" : "Фотография из воспоминаний"),
      caption: isGeneratedDateCaption(rawCaption, takenAt) ? "" : rawCaption,
      takenAt,
      duration: numberOr(item.duration, 0),
      censored: item.censored === true
    };
  }

  function restoreReaderChrome() {
    const update = () => {
      const cover = byId("cover");
      const threshold = cover ? Math.min(160, cover.offsetHeight * .12) : 80;
      if (window.scrollY > threshold || window.location.hash) document.body.classList.add("book-opened");
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("pageshow", () => requestAnimationFrame(update));
  }

  function revealPreviewCopies(item) {
    const key = mediaKey(item);
    document.querySelectorAll(".image-frame[data-media-key]").forEach((frame) => {
      if (frame.dataset.mediaKey !== key) return;
      frame.classList.remove("is-censored");
      frame.classList.add("is-revealed");
      frame.querySelector(".censor-preview")?.remove();
      const image = frame.querySelector("img");
      if (image) image.alt = item.alt || (item.kind === "video" ? "Видео из воспоминаний" : "Фотография из воспоминаний");
    });
  }

  function renderMediaCaption(item) {
    const date = formatTakenAt(item.takenAt);
    const note = mediaNote(item);
    return `${date ? `<span class="lightbox__datetime">${escapeHtml(date)}</span>` : ""}${note ? `<span class="lightbox__note">${escapeHtml(note)}</span>` : ""}`;
  }

  function mediaNote(item) {
    const caption = String(item.caption || "").trim();
    return isGeneratedDateCaption(caption, item.takenAt) ? "" : caption;
  }

  function formatTakenAt(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString("ru-RU", {
      day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit"
    }).replace(",", " ·");
  }

  function isGeneratedDateCaption(caption, takenAt) {
    if (!caption || !takenAt) return false;
    const normalized = String(caption).toLowerCase().replace(/\s+/g, " ").replace(/,/g, " ·").trim();
    return normalized === formatTakenAt(takenAt).toLowerCase().replace(/\s+/g, " ").trim();
  }

'''
    text = regex_once(
        text,
        r"  function normalizeMedia\(item\) \{.*?\n  \}\n\n  function formatDate",
        normalize_function + "  function formatDate",
        "normalizeMedia helpers",
    )
    text = text.replace('function mediaKey(item) {\n    return item.id || item.src || `${item.kind}-${activeIndex}`;\n  }', 'function mediaKey(item, fallbackIndex = activeIndex) {\n    return String(item.id || item.src || `${item.kind}-${fallbackIndex}`);\n  }')
    write(path, text)

    # 1, 4, 9. Визуальные состояния галереи и карточек.
    path = "assets/media.css"
    text = read(path)
    additions = r'''

/* Review round 2: подписи полароидов, локальное раскрытие цензуры и безопасные слои. */
.lightbox__censor-close {
  position: absolute;
  z-index: 3;
  top: .65rem;
  right: .7rem;
  width: 2.2rem;
  height: 2.2rem;
  display: grid;
  place-items: center;
  border: 0 !important;
  padding: 0 !important;
  color: rgba(255,255,255,.78) !important;
  background: transparent !important;
  font: 300 1.9rem/1 var(--sans) !important;
  letter-spacing: 0 !important;
}
.lightbox__censor-close:hover { color: #fff !important; transform: scale(1.06); }
.image-frame.is-revealed > img { filter: saturate(.92) contrast(.97); transform: none; }
.event-preview__item:hover,
.event-preview__item:focus-visible { z-index: 70; }
.event-preview__count { z-index: 80; }
.event-preview__item--8 { right: 1%; bottom: 1%; }
.event-preview__caption {
  position: absolute;
  z-index: 6;
  left: .7rem;
  right: .7rem;
  bottom: .32rem;
  overflow: hidden;
  color: #3d342c;
  font: 600 .72rem/1.2 var(--hand);
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
}
.lightbox__caption { display: grid; gap: .38rem; }
.lightbox__datetime {
  display: block;
  color: rgba(242,231,213,.62);
  font: 700 .69rem/1.3 var(--sans);
  letter-spacing: .08em;
  text-transform: uppercase;
}
.lightbox__note {
  display: block;
  color: #f2e7d5;
  font: 400 1.02rem/1.5 var(--hand);
}
'''
    if "Review round 2: подписи полароидов" not in text:
        text += additions
    write(path, text)

    # 5–7. Полностью обновлённая Studio с корректными путями и двумя полями.
    write("tools/studio.html", STUDIO_HTML)

    # 4. Дата живёт в takenAt, подпись создаётся пустой.
    path = "tools/import_memories.py"
    text = read(path)
    text = text.replace('"caption": media.caption,', '"caption": "",')
    write(path, text)

    # CI-превью: больше не нужен ручной path hack, добавляем проверки новых состояний.
    path = "preview/capture.mjs"
    text = read(path)
    old_hack = '''await studio.evaluate(() => {
  document.querySelectorAll(".item-preview img").forEach((image) => {
    const source = image.getAttribute("src");
    if (source && !/^(?:https?:|data:|blob:|\\/|\\.\\.\\/)/.test(source)) image.setAttribute("src", `../${source}`);
  });
});
'''
    text = text.replace(old_hack, "")
    text = replace_once(
        text,
        'await desktop.locator("#lightbox-close").click();',
        'await desktop.locator("#lightbox-close").click();\nawait censoredFrame.scrollIntoViewIfNeeded();\nawait desktop.waitForTimeout(100);\nawait shot(desktop, "11-local-censorship-stays-revealed.png", { fullPage: false });',
        "capture local reveal",
    )
    text = text.replace('"11-global-censorship-off.png"', '"12-global-censorship-off.png"')
    text = text.replace('"12-cover-mobile.png"', '"13-cover-mobile.png"')
    text = text.replace('"13-event-mobile.png"', '"14-event-mobile.png"')
    text = text.replace('"14-telegram-mobile.png"', '"15-telegram-mobile.png"')
    text = text.replace('"15-shared-album-mobile.png"', '"16-shared-album-mobile.png"')
    text = text.replace('"16-memory-studio.png"', '"17-memory-studio.png"')
    text = replace_once(
        text,
        'await shot(studio, "17-memory-studio.png", { fullPage: false });',
        'await shot(studio, "17-memory-studio.png", { fullPage: false });\nconst expandButton = studio.locator("[data-expand]").first();\nawait expandButton.click();\nawait studio.waitForTimeout(100);\nawait shot(studio, "18-memory-studio-expanded-caption.png", { fullPage: false });',
        "capture studio expanded",
    )
    write(path, text)

    checklist = r'''# Проверка ветки `review-round-2-polish`

Эта ветка не слита в `main`. Проверяй её отдельно.

## Как скачать ветку

```bash
cd ~/Desktop/memory-site
git fetch origin
git switch review-round-2-polish
git pull
```

Затем пересоздай тест, потому что структура подписи изменилась:

```bash
source .memory-venv/bin/activate
python3 tools/import_workflow.py reset test --yes
python3 tools/import_workflow.py test "$HOME/Desktop/memory-test-input" --open
```

Открыть тестовую Studio:

```bash
python3 tools/studio_workflow.py open test
```

## Чек-лист

- [ ] У предупреждения цензуры есть крестик справа сверху внутри карточки.
- [ ] Крестик закрывает весь просмотр, не раскрывая файл.
- [ ] После кнопки «Показать» и закрытия галереи конкретная карточка остаётся раскрытой до перезагрузки страницы.
- [ ] Глобальный переключатель цензуры продолжает работать.
- [ ] После применения `memories.test-edited.js` и автоматического открытия страницы слева видны главы, справа видны кнопки читателя.
- [ ] На полароидной карточке показывается отдельная человеческая подпись; длинная строка заканчивается многоточием.
- [ ] В полноэкранном просмотре первая строка — дата и время, вторая — человеческая подпись.
- [ ] В Studio превью фото и постеры видео отображаются, а не показывают битую иконку.
- [ ] Под вводной инструкцией Studio есть расшифровка всех кнопок.
- [ ] У файла в Studio отдельно отображаются дата/время и подпись.
- [ ] Кнопка «Развернуть» увеличивает карточку и поле подписи.
- [ ] Drag-and-drop внутри события и между событиями работает после изменения формы карточки.
- [ ] При 1 файле написано «1 файл», при 2–4 — «файла», при 5+ — «файлов».
- [ ] Событие с одним рядом стало компактнее, но композиция осталась воздушной.
- [ ] Событие с 8 файлами показывает два ряда, счётчик читается поверх композиции.
- [ ] При наведении крайняя правая фотография поднимается над соседними и не режется.
- [ ] Ни одна фотография не залезает на заголовок следующего события.
- [ ] Видео открываются, запускаются и перематываются.

## Отдельный коммит пункта о высоте

Коммит с компактностью событий, окончаниями слова «файл» и геометрией рядов будет иметь сообщение:

```text
fix(layout): compact event heights and safe row geometry
```

Его можно откатить независимо от остальных правок.
'''
    write("REVIEW_ROUND_2_CHECKLIST.md", checklist)


def patch_layout() -> None:
    # Пункт 8 — отдельный коммит: окончания, компактность и безопасная геометрия.
    path = "assets/app.js"
    text = read(path)
    text = replace_once(
        text,
        '    const layout = block.layout || (items.length > 8 ? "stack" : "collage");',
        '    const layout = block.layout === "stack" && items.length > 8 ? "stack" : "collage";',
        "eight item collage",
    )
    text = replace_once(
        text,
        '    wrapper.classList.add(`event-layout-${safeClass(layout)}`, `event-count-${Math.min(items.length, 8)}`);',
        '    const rowCount = layout === "stack" ? 0 : (previewItems.length <= 4 ? 1 : 2);\n    wrapper.classList.add(`event-layout-${safeClass(layout)}`, `event-count-${Math.min(items.length, 8)}`);\n    if (rowCount) wrapper.classList.add(`event-rows-${rowCount}`);',
        "event row class",
    )
    text = replace_once(
        text,
        '    count.textContent = `${items.length} файлов`;',
        '    count.textContent = `${items.length} ${plural(items.length, "файл", "файла", "файлов")}`;',
        "file plural",
    )
    write(path, text)

    path = "assets/media.css"
    text = read(path)
    additions = r'''

/* Отдельный layout-коммит: один ряд компактнее; максимум два ряда, затем стопка. */
.event-rows-1 .event-preview {
  min-height: clamp(19rem, 34vw, 28rem);
}
.event-rows-1 .event-preview::before { inset: 8% 5% 5%; }
.event-rows-2 .event-preview {
  min-height: clamp(34rem, 52vw, 41rem);
}
.event-layout-stack .event-preview {
  min-height: clamp(28rem, 46vw, 38rem);
}
@media (max-width: 760px) {
  .event-rows-1 .event-preview { min-height: 15.5rem; }
  .event-rows-2 .event-preview { min-height: 31rem; }
  .event-layout-stack .event-preview { min-height: 27rem; }
}
'''
    if "Отдельный layout-коммит" not in text:
        text += additions
    write(path, text)

    path = "tools/import_memories.py"
    text = read(path)
    text = text.replace('"layout": "stack" if len(event.items) > 7 else "collage"', '"layout": "stack" if len(event.items) > 8 else "collage"')
    write(path, text)

    path = "preview/demo_memories.js"
    text = read(path)
    text = text.replace('          layout: "stack",\n          items: [\n            { id: "t01"', '          layout: "collage",\n          items: [\n            { id: "t01"')
    one_event = r'''
        {
          type: "event",
          id: "demo-single",
          title: "Один тихий кадр",
          caption: "Проверка компактной высоты события с одним файлом.",
          layout: "collage",
          items: [
            { id: "single-01", kind: "photo", src: "preview/demo-media/photo-01.jpg", thumb: "preview/demo-media/photo-01.jpg", caption: "Один кадр тоже может быть целой страницей.", takenAt: "2023-10-02T20:14:00" }
          ]
        },
'''
    marker = '        {\n          type: "event",\n          id: "demo-day-one",'
    if "demo-single" not in text:
        text = text.replace(marker, one_event + marker, 1)
    write(path, text)

    path = "preview/capture.mjs"
    text = read(path)
    insert = '''const singleEvent = desktop.locator("#ordinary-days .memory-block--event").first();
await singleEvent.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(120);
await singleEvent.screenshot({ path: path.join(output, "19-single-row-event.png"), animations: "disabled" });
const eightEvent = desktop.locator("#journeys .memory-block--event").first();
await eightEvent.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(120);
await eightEvent.screenshot({ path: path.join(output, "20-eight-item-event.png"), animations: "disabled" });

'''
    if "19-single-row-event.png" not in text:
        text = text.replace("await browser.close();", insert + "await browser.close();")
    write(path, text)


STUDIO_HTML = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Memory Studio</title>
  <style>
    :root{--paper:#f2eadb;--ink:#28231f;--accent:#9c3f43;--line:#d6c8b2;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    *{box-sizing:border-box}body{margin:0;background:#c9b89e;color:var(--ink)}button,input,textarea{font:inherit}button{cursor:pointer}
    .top{position:sticky;top:0;z-index:100;display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;padding:.8rem 1rem;background:rgba(35,31,27,.95);color:#fff;backdrop-filter:blur(12px)}
    .top h1{margin:0 auto 0 0;font:700 1rem Georgia,serif}.top button,.top label{border:0;padding:.65rem .85rem;background:#f5ecdd;color:#27231f;font-weight:750}.top .primary{background:var(--accent);color:#fff}.top input[type=file]{display:none}.status{width:100%;font-size:.76rem;color:#d8cebf}
    main{width:min(1500px,calc(100% - 2rem));margin:1rem auto 5rem}.intro,.button-guide{padding:1rem 1.2rem;background:#fff8ec;box-shadow:0 .6rem 1.4rem rgba(40,30,20,.12);line-height:1.5}.intro strong{color:var(--accent)}
    .button-guide{margin-top:.8rem}.button-guide h2{margin:0 0 .7rem;font:700 1rem Georgia,serif}.button-guide dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.55rem 1rem;margin:0}.button-guide div{display:grid;grid-template-columns:auto 1fr;gap:.5rem}.button-guide dt{font-weight:850}.button-guide dd{margin:0;color:#675c50;font-size:.82rem}
    .chapter{margin:1.2rem 0;background:var(--paper);box-shadow:0 1rem 2rem rgba(45,34,25,.18)}.chapter>summary{display:flex;gap:1rem;align-items:center;padding:1rem 1.2rem;cursor:pointer;font:700 1.25rem Georgia,serif}.chapter>summary small{margin-left:auto;font:500 .75rem Inter,sans-serif;color:#716557}.chapter-tools{display:flex;gap:.5rem;padding:0 1.2rem 1rem}.chapter-tools button{border:1px solid var(--line);background:#fff9ef;padding:.5rem .7rem}
    .events{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:1rem;padding:0 1rem 1rem}.event{min-width:0;padding:.9rem;background:#fffaf1;border:1px solid #d7cab7;box-shadow:0 .5rem 1rem rgba(45,34,25,.1)}.event.dragover{outline:4px solid rgba(156,63,67,.35)}
    .event-head{display:grid;grid-template-columns:1fr auto;gap:.5rem}.event-head input,.event-head textarea{width:100%;border:1px solid var(--line);background:#fff;padding:.55rem}.event-head textarea{grid-column:1/-1;min-height:3.5rem;resize:vertical}.event-actions{display:flex;gap:.35rem;align-items:start}.event-actions button{border:0;background:#e8ddca;padding:.45rem .55rem}.event-actions .danger{background:#f2d8d8;color:#7b2020}
    .items{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.7rem;margin-top:.8rem;min-height:7rem;padding:.25rem}.item{position:relative;min-width:0;padding:.4rem;background:#eee4d3;border:1px solid #cfc1aa;cursor:grab;transition:grid-column .2s ease}.item.is-expanded{grid-column:span 2}.item.dragging{opacity:.35}.item.drop-before{box-shadow:-5px 0 0 var(--accent)}
    .item-preview{position:relative;overflow:hidden;background:#b9ad9b}.item-preview img{display:block;width:100%;aspect-ratio:1;object-fit:cover}.item-preview__missing{display:none;position:absolute;inset:0;place-items:center;padding:.7rem;text-align:center;color:#6b5e4e;background:repeating-linear-gradient(135deg,#d7cbb8 0 10px,#cfc2ad 10px 20px);font-size:.7rem}.item-preview.is-missing img{display:none}.item-preview.is-missing .item-preview__missing{display:grid}.item.is-censored .item-preview img{filter:blur(13px) saturate(.5) brightness(.72);transform:scale(1.12)}
    .item-meta{position:absolute;left:.35rem;top:.35rem;z-index:3;padding:.2rem .35rem;border-radius:999px;background:rgba(20,18,16,.76);color:#fff;font-size:.58rem;font-weight:800}.item-fields{display:grid;gap:.35rem;margin-top:.35rem}.item-fields label{display:grid;gap:.2rem}.item-fields label>span{color:#756857;font-size:.6rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}.item-fields input,.item-fields textarea{width:100%;border:1px solid #c9bba5;background:#fff9ef;padding:.42rem;font-size:.72rem}.item-fields textarea{min-height:2.15rem;resize:vertical}.item.is-expanded .item-fields textarea{min-height:8rem}.expand-caption{border:0;padding:.38rem;background:#e7dac5;font-size:.65rem;font-weight:800}.item-tools{display:flex;gap:.3rem;margin-top:.35rem}.item-tools button{position:static;flex:1;border:0;padding:.38rem .25rem;background:#ded1bc;font-size:.65rem;font-weight:750}.item-tools .censor-on{background:#302b27;color:#fff}.item-tools .remove{flex:0 0 2rem;background:#f0d5d5;color:#741f1f}
    .empty{grid-column:1/-1;padding:2rem;border:2px dashed #cbbda7;text-align:center;color:#7b7061}dialog{width:min(540px,calc(100% - 2rem));border:0;padding:1rem;background:#fffaf1;box-shadow:0 2rem 5rem rgba(0,0,0,.35)}dialog::backdrop{background:rgba(24,20,17,.65)}dialog label{display:grid;gap:.35rem;margin:.8rem 0}dialog input,dialog textarea{width:100%;padding:.65rem;border:1px solid var(--line)}dialog textarea{min-height:8rem}dialog menu{display:flex;justify-content:flex-end;gap:.5rem;padding:0}
    @media(max-width:650px){.events{grid-template-columns:1fr}.top h1{width:100%}.top{position:relative}.item.is-expanded{grid-column:1/-1}}
  </style>
</head>
<body>
  <header class="top">
    <h1>Memory Studio</h1>
    <button id="open-book">Открыть книгу ↗</button><button id="undo">↶ Отменить</button><button id="save-local">Сохранить черновик</button><button id="restore-local">Вернуть черновик</button>
    <label>Открыть memories.js<input id="load-file" type="file" accept=".js,.json" /></label><button class="primary" id="export">Экспортировать memories.js</button>
    <div class="status" id="status">Загрузка книги…</div>
  </header>
  <main>
    <section class="intro">Автоматическая группировка — <strong>первый черновик, а не точная истина</strong>. Перетаскивай карточки между событиями и внутри события, меняй две отдельные сущности: автоматическую дату/время и человеческую подпись. «Скрыть» включает цензуру.</section>
    <section class="button-guide"><h2>Что делают кнопки</h2><dl>
      <div><dt>↑ / ↓</dt><dd>Передвигают целое событие выше или ниже.</dd></div><div><dt>⇧+</dt><dd>Объединяет событие с предыдущим.</dd></div><div><dt>× события</dt><dd>Убирает событие из книги; исходники остаются на диске.</dd></div><div><dt>Drag & Drop</dt><dd>Переставляет файл или переносит его в другое событие.</dd></div><div><dt>Развернуть</dt><dd>Увеличивает карточку и поле длинной подписи.</dd></div><div><dt>Скрыть</dt><dd>Добавляет предупреждение и блюр в книге.</dd></div><div><dt>× файла</dt><dd>Убирает только этот файл из книги.</dd></div><div><dt>Черновик / экспорт</dt><dd>Черновик живёт в браузере; экспорт создаёт файл для применения к книге.</dd></div>
    </dl></section>
    <div id="workspace"></div>
  </main>
  <dialog id="new-event-dialog"><form method="dialog"><h2>Новое событие</h2><label>Название<input id="new-event-title" value="Новое событие" /></label><label>Подпись<textarea id="new-event-caption">Добавь сюда одну короткую деталь.</textarea></label><menu><button value="cancel">Отмена</button><button id="confirm-new-event" value="default">Создать</button></menu></form></dialog>
  <script src="../content/memories.js"></script>
  <script>
    "use strict";
    let book=clone(window.MEMORY_BOOK||{meta:{},chapters:[]}),dragged=null,targetChapterIndex=0;
    const history=[],expandedItems=new Set(),workspace=document.getElementById("workspace"),status=document.getElementById("status"),dialog=document.getElementById("new-event-dialog");
    const testMode=location.pathname.includes("/.memory-test/site/")||location.pathname.includes("/memory-test/site/");
    const draftKey=testMode?"memory-studio-draft-test":"memory-studio-draft-production";
    normalizeBook();render();
    function clone(v){return JSON.parse(JSON.stringify(v))}
    function normalizeBook(){book.chapters||=[];book.chapters.forEach((chapter,ci)=>{chapter.id||=`chapter-${ci+1}`;chapter.blocks||=[];chapter.blocks=chapter.blocks.filter(Boolean);chapter.blocks.forEach((block,ei)=>{if(block.type!=="event")return;block.id||=`event-${ci}-${ei}`;block.items||=[];block.layout||=block.items.length>8?"stack":"collage";block.items.forEach((item,ii)=>{item.id||=`${block.id}-item-${ii}`;item.censored=item.censored===true;if(isGeneratedDateCaption(item.caption,item.takenAt))item.caption=""})})})}
    function snapshot(){history.push(JSON.stringify(book));if(history.length>40)history.shift()}
    function render(){workspace.innerHTML="";book.chapters.forEach((c,i)=>workspace.appendChild(renderChapter(c,i)));const events=book.chapters.reduce((n,c)=>n+c.blocks.filter(b=>b.type==="event").length,0),items=book.chapters.reduce((n,c)=>n+c.blocks.reduce((m,b)=>m+(b.items?.length||0),0),0),censored=book.chapters.reduce((n,c)=>n+c.blocks.reduce((m,b)=>m+(b.items?.filter(i=>i.censored).length||0),0),0);status.textContent=`${testMode?"TEST · ":"PRODUCTION · "}${book.chapters.length} глав · ${events} событий · ${items} файлов · ${censored} скрыто`}
    function renderChapter(chapter,chapterIndex){const details=document.createElement("details");details.className="chapter";details.open=chapterIndex===0;const events=chapter.blocks.filter(b=>b.type==="event");details.innerHTML=`<summary>${escapeHtml(chapter.title||`Глава ${chapterIndex+1}`)}<small>${events.length} событий</small></summary><div class="chapter-tools"><button data-add>＋ Добавить событие</button></div><div class="events"></div>`;details.querySelector("[data-add]").onclick=()=>{targetChapterIndex=chapterIndex;dialog.showModal()};const container=details.querySelector(".events");events.forEach(e=>container.appendChild(renderEvent(e,chapterIndex,chapter.blocks.indexOf(e))));if(!events.length)container.innerHTML='<div class="empty">В этой главе пока нет событий.</div>';return details}
    function renderEvent(event,ci,bi){const card=document.createElement("article");card.className="event";card.innerHTML=`<div class="event-head"><input data-title value="${escapeAttr(event.title||"Событие")}" aria-label="Название события"/><div class="event-actions"><button data-up title="Выше">↑</button><button data-down title="Ниже">↓</button><button data-merge title="Объединить с предыдущим">⇧+</button><button class="danger" data-delete title="Удалить событие">×</button></div><textarea data-caption aria-label="Подпись события">${escapeHtml(event.caption||"")}</textarea></div><div class="items"></div>`;const items=card.querySelector(".items");event.items.forEach((item,ii)=>items.appendChild(renderItem(item,ci,bi,ii)));if(!event.items.length)items.innerHTML='<div class="empty">Перетащи сюда фото или видео</div>';card.querySelector("[data-title]").onchange=e=>{snapshot();event.title=e.target.value;render()};card.querySelector("[data-caption]").onchange=e=>{snapshot();event.caption=e.target.value;render()};card.querySelector("[data-up]").onclick=()=>moveBlock(ci,bi,-1);card.querySelector("[data-down]").onclick=()=>moveBlock(ci,bi,1);card.querySelector("[data-merge]").onclick=()=>mergePrevious(ci,bi);card.querySelector("[data-delete]").onclick=()=>deleteEvent(ci,bi);card.ondragover=e=>{e.preventDefault();card.classList.add("dragover")};card.ondragleave=()=>card.classList.remove("dragover");card.ondrop=e=>{if(e.target.closest(".item"))return;e.preventDefault();card.classList.remove("dragover");if(dragged)moveItem(dragged.chapterIndex,dragged.blockIndex,dragged.itemIndex,ci,bi,event.items.length)};return card}
    function renderItem(item,ci,bi,ii){const card=document.createElement("div");card.className=`item${item.censored?" is-censored":""}${expandedItems.has(item.id)?" is-expanded":""}`;card.draggable=true;const previewSrc=resolveMediaPath(item.thumb||item.poster||item.src||""),kind=item.kind==="live"?"LIVE":item.kind==="video"?`VIDEO${item.duration?` · ${formatDuration(item.duration)}`:""}`:"PHOTO";card.innerHTML=`<div class="item-preview"><img loading="lazy" src="${escapeAttr(previewSrc)}" alt=""/><span class="item-preview__missing">Не удалось открыть превью</span><span class="item-meta">${escapeHtml(kind)}</span></div><div class="item-fields"><label><span>Дата и время</span><input data-taken type="datetime-local" value="${escapeAttr(toDatetimeLocal(item.takenAt))}"/></label><label><span>Подпись к кадру</span><textarea data-caption rows="1" placeholder="Например: тот самый вечер">${escapeHtml(item.caption||"")}</textarea></label><button class="expand-caption" data-expand type="button">${expandedItems.has(item.id)?"Свернуть":"Развернуть подпись"}</button></div><div class="item-tools"><button data-censor class="${item.censored?"censor-on":""}">${item.censored?"Скрыто":"Скрыть"}</button><button data-remove class="remove" title="Убрать из книги">×</button></div>`;const image=card.querySelector("img"),preview=card.querySelector(".item-preview");image.onerror=()=>preview.classList.add("is-missing");image.onload=()=>preview.classList.remove("is-missing");card.ondragstart=e=>{if(e.target.closest("input,textarea,button")){e.preventDefault();return}dragged={chapterIndex:ci,blockIndex:bi,itemIndex:ii};card.classList.add("dragging")};card.ondragend=()=>{dragged=null;card.classList.remove("dragging");document.querySelectorAll(".drop-before").forEach(el=>el.classList.remove("drop-before"))};card.ondragover=e=>{e.preventDefault();e.stopPropagation();card.classList.add("drop-before")};card.ondragleave=()=>card.classList.remove("drop-before");card.ondrop=e=>{e.preventDefault();e.stopPropagation();card.classList.remove("drop-before");if(dragged)moveItem(dragged.chapterIndex,dragged.blockIndex,dragged.itemIndex,ci,bi,ii)};card.querySelector("[data-taken]").onchange=e=>{snapshot();item.takenAt=e.target.value?`${e.target.value}:00`:""};card.querySelector("[data-caption]").onchange=e=>{snapshot();item.caption=e.target.value};card.querySelector("[data-expand]").onclick=()=>{expandedItems.has(item.id)?expandedItems.delete(item.id):expandedItems.add(item.id);render()};card.querySelector("[data-censor]").onclick=()=>{snapshot();item.censored=!item.censored;render()};card.querySelector("[data-remove]").onclick=()=>{snapshot();book.chapters[ci].blocks[bi].items.splice(ii,1);render()};return card}
    function moveItem(fc,fb,fi,tc,tb,ti){snapshot();const source=book.chapters[fc].blocks[fb].items,target=book.chapters[tc].blocks[tb].items,[item]=source.splice(fi,1);if(!item){render();return}if(source===target&&fi<ti)ti--;target.splice(Math.max(0,Math.min(ti,target.length)),0,item);render()}
    function moveBlock(ci,bi,d){const blocks=book.chapters[ci].blocks;let next=bi+d;while(next>=0&&next<blocks.length&&blocks[next].type!=="event")next+=d;if(next<0||next>=blocks.length)return;snapshot();[blocks[bi],blocks[next]]=[blocks[next],blocks[bi]];render()}
    function mergePrevious(ci,bi){const blocks=book.chapters[ci].blocks;let p=bi-1;while(p>=0&&blocks[p].type!=="event")p--;if(p<0)return;snapshot();blocks[p].items.push(...(blocks[bi].items||[]));blocks.splice(bi,1);render()}
    function deleteEvent(ci,bi){const event=book.chapters[ci].blocks[bi];if(event.items?.length&&!confirm("В событии есть файлы. Удалить их из книги? Исходники останутся."))return;snapshot();book.chapters[ci].blocks.splice(bi,1);render()}
    document.getElementById("confirm-new-event").onclick=()=>{snapshot();book.chapters[targetChapterIndex].blocks.push({type:"event",id:`manual-${Date.now()}`,title:document.getElementById("new-event-title").value,caption:document.getElementById("new-event-caption").value,layout:"collage",items:[]});setTimeout(render,0)};
    document.getElementById("open-book").onclick=()=>window.open("../index.html","_blank");document.getElementById("undo").onclick=()=>{const p=history.pop();if(p){book=JSON.parse(p);render()}};document.getElementById("save-local").onclick=()=>{try{localStorage.setItem(draftKey,JSON.stringify(book));status.textContent="Черновик сохранён в этом браузере."}catch(e){status.textContent=`Не удалось сохранить: ${e.message}`}};document.getElementById("restore-local").onclick=()=>{const v=localStorage.getItem(draftKey);if(v){snapshot();book=JSON.parse(v);normalizeBook();render()}};
    document.getElementById("load-file").onchange=async e=>{const file=e.target.files[0];if(!file)return;const text=await file.text(),match=text.match(/window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$/);try{snapshot();book=JSON.parse(match?match[1]:text);normalizeBook();render()}catch(error){alert(`Не удалось прочитать файл: ${error.message}`)}};
    document.getElementById("export").onclick=()=>{const text="// Экспортировано из tools/studio.html\nwindow.MEMORY_BOOK = "+JSON.stringify(book,null,2)+";\n",blob=new Blob([text],{type:"text/javascript;charset=utf-8"}),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=testMode?"memories.test-edited.js":"memories.js";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);status.textContent="Экспорт готов. Примени его через tools/studio_workflow.py apply …"};
    function resolveMediaPath(value){const s=String(value||"");return /^(?:https?:|data:|blob:|file:|\/|\.\.\/)/.test(s)?s:`../${s.replace(/^\.\//,"")}`}
    function toDatetimeLocal(value){if(!value)return"";const match=String(value).match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);return match?`${match[1]}T${match[2]}`:""}
    function formatTakenAt(value){if(!value)return"";const d=new Date(value);return Number.isNaN(d.getTime())?String(value):d.toLocaleString("ru-RU",{day:"numeric",month:"long",year:"numeric",hour:"2-digit",minute:"2-digit"}).replace(","," ·")}
    function isGeneratedDateCaption(caption,takenAt){if(!caption||!takenAt)return false;return String(caption).toLowerCase().replace(/\s+/g," ").replace(/,/g," ·").trim()===formatTakenAt(takenAt).toLowerCase().replace(/\s+/g," ").trim()}
    function formatDuration(seconds){const t=Math.max(0,Math.round(Number(seconds)||0)),h=Math.floor(t/3600),m=Math.floor((t%3600)/60),s=t%60;return h?`${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`:`${m}:${String(s).padStart(2,"0")}`}
    function escapeHtml(v){return String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;")}function escapeAttr(v){return escapeHtml(v).replace(/`/g,"&#096;")}
  </script>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["core", "layout"])
    args = parser.parse_args()
    if args.phase == "core":
        patch_core()
    else:
        patch_layout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
