(function () {
  "use strict";

  const book = window.MEMORY_BOOK;
  if (!book || !Array.isArray(book.chapters)) return;

  const mediaByPath = new Map();
  collectMedia(book, (item) => {
    [item.src, item.thumb, item.poster, item.liveVideo].forEach((path) => {
      const key = canonicalPath(path);
      if (key && !mediaByPath.has(key)) mediaByPath.set(key, item);
    });
  });

  document.addEventListener("DOMContentLoaded", () => {
    const lightbox = document.getElementById("lightbox");
    const figure = lightbox?.querySelector(".lightbox__figure");
    const image = document.getElementById("lightbox-image");
    const video = document.getElementById("lightbox-video");
    const censor = document.getElementById("lightbox-censor");
    if (!lightbox || !figure || !image || !video || !censor) return;

    let badge = document.getElementById("lightbox-location");
    if (!badge) {
      badge = document.createElement("div");
      badge.id = "lightbox-location";
      badge.className = "lightbox__location";
      badge.hidden = true;
      badge.setAttribute("aria-live", "polite");
      figure.prepend(badge);
    }

    let scheduled = false;
    const scheduleSync = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        syncLocation();
      });
    };

    const observer = new MutationObserver(scheduleSync);
    observer.observe(lightbox, {
      subtree: true,
      attributes: true,
      attributeFilter: ["src", "hidden", "class"],
    });
    lightbox.addEventListener("click", scheduleSync);
    document.addEventListener("keydown", scheduleSync);
    syncLocation();

    function syncLocation() {
      if (lightbox.hidden || !censor.hidden) {
        setBadge("");
        return;
      }
      const activeMedia = !video.hidden && video.getAttribute("src") ? video : image;
      const path = canonicalPath(activeMedia.getAttribute("src") || activeMedia.src || "");
      const item = mediaByPath.get(path);
      setBadge(String(item?.location || "").trim());
    }

    function setBadge(location) {
      const next = String(location || "").trim();
      if (!next) {
        badge.hidden = true;
        badge.textContent = "";
        return;
      }
      const label = `⌖ ${next}`;
      if (badge.textContent !== label) badge.textContent = label;
      badge.hidden = false;
    }
  });

  function collectMedia(value, visitor) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach((item) => collectMedia(item, visitor));
      return;
    }
    if (value.id && (value.src || value.thumb || value.poster || value.liveVideo)) visitor(value);
    Object.values(value).forEach((child) => collectMedia(child, visitor));
  }

  function canonicalPath(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    try {
      return decodeURIComponent(new URL(raw, window.location.href).pathname).replace(/\/{2,}/g, "/");
    } catch (_) {
      return raw.split(/[?#]/, 1)[0].replace(/^\.\//, "");
    }
  }
})();
