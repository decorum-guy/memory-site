(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function expandEventPages() {
    const book = window.MEMORY_BOOK;
    if (!book || !Array.isArray(book.chapters)) return;

    const sourceEvents = [];
    book.chapters.forEach((chapter) => {
      (chapter.blocks || []).forEach((block) => {
        if (block && block.type === "event") sourceEvents.push(block);
      });
    });

    const renderedEvents = [...document.querySelectorAll(".memory-block--event")];
    renderedEvents.forEach((wrapper, index) => expandEvent(wrapper, sourceEvents[index]));
    window.MEMORY_ROUND4?.classifyPolaroidCaptions?.();

    function expandEvent(wrapper, block) {
      if (!wrapper || !block || !Array.isArray(block.items)) return;
      const preview = wrapper.querySelector(".event-preview");
      const openButton = wrapper.querySelector(".event-open");
      const countBadge = wrapper.querySelector(".event-preview__count");
      if (!preview || !openButton) return;

      const allItems = block.items.map(normalizeItem);
      const visualItems = allItems.filter((item) => item.kind !== "audio");
      const existingKeys = new Set(
        [...preview.querySelectorAll(".image-frame[data-media-key]")]
          .map((frame) => frame.dataset.mediaKey)
          .filter(Boolean)
      );

      visualItems.forEach((item, visualIndex) => {
        const allIndex = allItems.findIndex((candidate) => candidate === item);
        const key = mediaKey(item, allIndex);
        if (existingKeys.has(key)) return;
        const button = createPreviewButton(item, visualIndex, key);
        button.addEventListener("click", () => openAtIndex(openButton, allIndex));
        preview.insertBefore(button, countBadge || null);
        existingKeys.add(key);
      });

      preview.dataset.renderedItems = String(visualItems.length);
      wrapper.classList.add("event-preview-complete");
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
      button.style.setProperty("--event-rotate", `${[-5, 3, -2, 6, -4, 2, -1, 4][index % 8]}deg`);
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
