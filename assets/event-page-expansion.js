(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function expandEventPages() {
    const book = window.MEMORY_BOOK;
    if (!book || !Array.isArray(book.chapters)) return;

    const sourceEvents = [];
    book.chapters.forEach((chapter, chapterIndex) => {
      (chapter.blocks || []).forEach((block, blockIndex) => {
        if (block && block.type === "event") {
          sourceEvents.push({
            block,
            chapterId: chapter.id || `chapter-${chapterIndex + 1}`,
            chapterIndex,
            blockIndex,
          });
        }
      });
    });

    const renderedEvents = [...document.querySelectorAll(".memory-block--event")];
    renderedEvents.forEach((wrapper, index) => expandEvent(wrapper, sourceEvents[index]));
    window.MEMORY_ROUND4?.classifyPolaroidCaptions?.();

    window.MEMORY_EVENT_LAYOUT = {
      eventIdentityKey,
      mediaIdentityToken,
      cardLayout,
      hash128,
    };

    function expandEvent(wrapper, context) {
      const block = context?.block;
      if (!wrapper || !block || !Array.isArray(block.items)) return;
      const preview = wrapper.querySelector(".event-preview");
      const openButton = wrapper.querySelector(".event-open");
      const countBadge = wrapper.querySelector(".event-preview__count");
      if (!preview || !openButton) return;

      const allItems = block.items.map(normalizeItem);
      const visualEntries = allItems
        .map((item, allIndex) => ({ item, allIndex }))
        .filter(({ item }) => item.kind !== "audio");
      const existingCards = [...preview.querySelectorAll(".event-preview__item")];

      /* The original Reader renders the first cards. Match those cards by their
         visual position, not only by id/src: manually copied or damaged data may
         legitimately contain duplicate identifiers and every file must remain. */
      existingCards.forEach((card, visualIndex) => {
        const entry = visualEntries[visualIndex];
        const frame = card.querySelector(".image-frame");
        if (entry && frame) {
          frame.dataset.mediaInstanceKey = mediaInstanceKey(entry.item, visualIndex);
        }
      });

      for (let visualIndex = existingCards.length; visualIndex < visualEntries.length; visualIndex += 1) {
        const entry = visualEntries[visualIndex];
        const key = mediaKey(entry.item, entry.allIndex);
        const button = createPreviewButton(entry.item, visualIndex, key);
        const frame = button.querySelector(".image-frame");
        if (frame) frame.dataset.mediaInstanceKey = mediaInstanceKey(entry.item, visualIndex);
        button.addEventListener("click", () => openAtIndex(openButton, entry.allIndex));
        preview.insertBefore(button, countBadge || null);
      }

      const eventKey = eventIdentityKey(block, context);
      preview.dataset.eventIdentitySeed = eventKey;
      applyEventLayout(preview, eventKey);
      preview.dataset.renderedItems = String(visualEntries.length);
      wrapper.classList.add("event-preview-complete");
    }

    function applyEventLayout(preview, eventKey) {
      [...preview.querySelectorAll(".event-preview__item")].forEach((card, index) => {
        const layout = cardLayout(eventKey, index);
        card.style.setProperty("--event-rotate", `${layout.rotate}deg`);
        card.style.setProperty("--event-shelf-x", `${layout.x}rem`);
        card.style.setProperty("--event-shelf-y", `${layout.y}rem`);
        card.style.setProperty("--event-layer", String(layout.layer));
      });
    }

    /* A date alone is intentionally not an identity: one day may contain many
       separate events. The key combines chapter namespace, explicit block id and
       a canonical, order-independent fingerprint of every media item. Text,
       crop, location and item order do not alter the layout. */
    function eventIdentityKey(block, context = {}) {
      const mediaTokens = (Array.isArray(block?.items) ? block.items : [])
        .map(mediaIdentityToken)
        .sort();
      const explicitId = normalizeIdentityPart(block?.id);
      const chapterId = normalizeIdentityPart(context.chapterId);
      const fallback = explicitId || mediaTokens.length
        ? []
        : [
            normalizeIdentityPart(block?.date),
            normalizeIdentityPart(block?.title),
            normalizeIdentityPart(block?.type),
            Number.isInteger(context.chapterIndex) ? context.chapterIndex : -1,
            Number.isInteger(context.blockIndex) ? context.blockIndex : -1,
          ];
      const canonical = JSON.stringify([
        "memory-event-identity-v3",
        chapterId,
        explicitId,
        mediaTokens,
        fallback,
      ]);
      return `evt-${hash128(canonical)}`;
    }

    function mediaIdentityToken(item) {
      const stable = [
        normalizeIdentityPart(item?.id),
        normalizeIdentityPart(item?.src),
        normalizeIdentityPart(item?.thumb),
        normalizeIdentityPart(item?.poster),
        normalizeIdentityPart(item?.liveVideo),
        normalizeIdentityPart(item?.takenAt || item?.date),
        normalizeIdentityPart(item?.kind),
      ];
      if (stable.some(Boolean)) return JSON.stringify(stable);
      return JSON.stringify([
        "fallback-media",
        normalizeIdentityPart(item?.kind),
        normalizeIdentityPart(item?.caption || item?.note),
        normalizeIdentityPart(item?.alt),
      ]);
    }

    function normalizeIdentityPart(value) {
      return String(value ?? "").trim().normalize("NFC");
    }

    function cardLayout(eventKey, index) {
      const random = xoshiro128(seedWords(`${eventKey}|card:${index}`));
      const column = index % 4;
      const baseX = [.5, .16, -.16, -.5][column];
      const baseY = [.35, -.25, .15, -.2][column];

      let rotate = between(random, -5.6, 5.6);
      if (Math.abs(rotate) < .85) rotate += rotate >= 0 ? .95 : -.95;

      return {
        rotate: round(rotate, 3),
        x: round(baseX + between(random, -.14, .14), 3),
        y: round(baseY + between(random, -.3, .3), 3),
        layer: 2 + Math.floor(random() * 4),
      };
    }

    function hash128(value) {
      const salts = [0x243f6a88, 0x85a308d3, 0x13198a2e, 0x03707344];
      return salts
        .map((salt, index) => hash32(`${index}|${value}`, salt).toString(16).padStart(8, "0"))
        .join("");
    }

    function hash32(value, seed) {
      let hash = (0x811c9dc5 ^ seed) >>> 0;
      for (let index = 0; index < value.length; index += 1) {
        hash ^= value.charCodeAt(index);
        hash = Math.imul(hash, 0x01000193);
        hash ^= hash >>> 13;
      }
      hash ^= hash >>> 16;
      hash = Math.imul(hash, 0x85ebca6b);
      hash ^= hash >>> 13;
      hash = Math.imul(hash, 0xc2b2ae35);
      hash ^= hash >>> 16;
      return hash >>> 0;
    }

    function seedWords(value) {
      const words = [
        hash32(`${value}|a`, 0x9e3779b9),
        hash32(`${value}|b`, 0x7f4a7c15),
        hash32(`${value}|c`, 0x94d049bb),
        hash32(`${value}|d`, 0x5bd1e995),
      ];
      if (words.every((word) => word === 0)) words[0] = 1;
      return words;
    }

    function xoshiro128(words) {
      let [a, b, c, d] = words.map((word) => word >>> 0);
      return function random() {
        const result = Math.imul(rotateLeft(Math.imul(b, 5) >>> 0, 7), 9) >>> 0;
        const temporary = (b << 9) >>> 0;
        c ^= a;
        d ^= b;
        b ^= c;
        a ^= d;
        c ^= temporary;
        d = rotateLeft(d, 11);
        return result / 4294967296;
      };
    }

    function rotateLeft(value, shift) {
      return ((value << shift) | (value >>> (32 - shift))) >>> 0;
    }

    function between(random, min, max) {
      return min + (max - min) * random();
    }

    function round(value, digits) {
      const factor = 10 ** digits;
      return Math.round(value * factor) / factor;
    }

    function openAtIndex(openButton, index) {
      openButton.click();
      const next = document.getElementById("lightbox-next");
      for (let step = 0; step < index; step += 1) next?.click();
    }

    function createPreviewButton(item, index, key) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `event-preview__item event-preview__item--${(index % 8) + 1}`;
      button.setAttribute("aria-label", item.censored ? `Открыть скрытый элемент ${index + 1}` : `Открыть элемент ${index + 1}`);
      button.appendChild(createFrame(item, key));

      const note = String(item.caption || item.note || "").trim();
      if (note) {
        const label = document.createElement("span");
        label.className = "event-preview__caption";
        label.textContent = note;
        label.title = note;
        button.appendChild(label);
      }
      return button;
    }

    function createFrame(item, key) {
      const frame = document.createElement("span");
      const hidden = item.censored && !window.MEMORY_CENSORSHIP_OFF;
      const crop = normalizeCrop(item.crop);
      frame.className = `image-frame media-kind-${safeClass(item.kind)}`;
      frame.dataset.mediaKey = key;
      frame.dataset.censored = item.censored ? "1" : "0";
      frame.classList.toggle("is-censored", hidden);

      const useSelectedVideoFrame = item.kind === "video" && item.posterTime !== null;
      const media = document.createElement(useSelectedVideoFrame ? "video" : "img");
      media.style.objectPosition = `${crop.x}% ${crop.y}%`;

      if (useSelectedVideoFrame) {
        media.muted = true;
        media.playsInline = true;
        media.preload = "metadata";
        media.poster = item.poster || "";
        media.src = item.src || "";
        media.addEventListener("loadedmetadata", () => {
          const duration = Number.isFinite(media.duration) ? media.duration : item.posterTime;
          const target = Math.min(item.posterTime, Math.max(0, duration - .01));
          try { media.currentTime = target; } catch (_) { /* poster stays visible */ }
        }, { once: true });
      } else {
        media.src = item.thumb || item.poster || item.src || "";
        media.alt = hidden ? "Скрытое воспоминание" : (item.alt || defaultAlt(item.kind));
        media.loading = "lazy";
        media.decoding = "async";
      }

      const placeholder = document.createElement("span");
      placeholder.className = "image-placeholder";
      placeholder.innerHTML = `<span>файл не найден</span><small>${escapeHtml(item.src || "")}</small>`;
      media.addEventListener("error", () => frame.classList.add("is-missing"));
      media.addEventListener(useSelectedVideoFrame ? "loadeddata" : "load", () => frame.classList.remove("is-missing"));
      frame.append(media, placeholder);

      if (item.kind === "live") {
        frame.appendChild(createBadge("media-badge media-badge--live", "LIVE"));
      } else if (item.kind === "video") {
        frame.appendChild(createBadge("media-badge media-badge--video", item.duration ? `▶ ${formatDuration(item.duration)}` : "▶ VIDEO"));
      }

      if (hidden) {
        const cover = document.createElement("span");
        cover.className = "censor-preview";
        cover.innerHTML = "<strong>Содержание скрыто</strong><small>Нажми, чтобы открыть предупреждение</small>";
        frame.appendChild(cover);
      }
      return frame;
    }

    function createBadge(className, text) {
      const badge = document.createElement("span");
      badge.className = className;
      badge.textContent = text;
      return badge;
    }

    function normalizeItem(item) {
      const kind = item.kind || (item.liveVideo ? "live" : item.poster ? "video" : "photo");
      const posterTime = item.posterTime === null || item.posterTime === undefined || item.posterTime === ""
        ? null
        : Number(item.posterTime);
      return {
        ...item,
        kind,
        censored: item.censored === true,
        posterTime: Number.isFinite(posterTime) && posterTime >= 0 ? posterTime : null,
      };
    }

    function normalizeCrop(value) {
      const x = Number(value?.x);
      const y = Number(value?.y);
      return {
        x: Number.isFinite(x) ? Math.min(100, Math.max(0, x)) : 50,
        y: Number.isFinite(y) ? Math.min(100, Math.max(0, y)) : 50,
      };
    }

    function mediaKey(item, fallbackIndex) {
      return String(item.id || item.src || `${item.kind}-${fallbackIndex}`);
    }

    function mediaInstanceKey(item, visualIndex) {
      return `${mediaKey(item, visualIndex)}::${visualIndex}`;
    }

    function defaultAlt(kind) {
      return kind === "video" ? "Видео из воспоминаний" : "Фотография из воспоминаний";
    }

    function formatDuration(seconds) {
      const total = Math.max(0, Math.round(Number(seconds) || 0));
      const hours = Math.floor(total / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      const rest = total % 60;
      if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
      return `${minutes}:${String(rest).padStart(2, "0")}`;
    }

    function safeClass(value) {
      return String(value || "photo").toLowerCase().replace(/[^a-z0-9_-]/g, "-");
    }

    function escapeHtml(value) {
      return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
  });
})();
