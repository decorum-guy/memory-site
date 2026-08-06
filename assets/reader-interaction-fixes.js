(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function installReaderInteractionFixes() {
    enforceVisibleEventOrder();
    alignLocationBadge();
    installRegularVideoPlayback();

    function enforceVisibleEventOrder() {
      const rotations = [-1.8, 1.35, -.9, 1.7, 1.05, -1.4, .75, -1.1];
      document.querySelectorAll(".memory-block--event .event-preview").forEach((preview) => {
        [...preview.querySelectorAll(".event-preview__item")].forEach((card, index) => {
          card.dataset.mediaOrder = String(index);
          card.style.order = String(index);
          card.style.setProperty("--event-ordered-rotate", `${rotations[index % rotations.length]}deg`);
        });
      });
    }

    function alignLocationBadge() {
      const badge = document.getElementById("lightbox-location");
      if (!badge) return;

      const render = () => {
        if (badge.querySelector(".lightbox__location-text")) return;
        const raw = String(badge.textContent || "").replace(/^\s*⌖\s*/, "").trim();
        if (!raw) return;
        const icon = document.createElement("span");
        icon.className = "lightbox__location-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "⌖ ";
        const text = document.createElement("span");
        text.className = "lightbox__location-text";
        text.textContent = raw;
        badge.replaceChildren(icon, text);
      };

      new MutationObserver(render).observe(badge, { childList: true, characterData: true, subtree: true });
      render();
    }

    function installRegularVideoPlayback() {
      const lightbox = document.getElementById("lightbox");
      const video = document.getElementById("lightbox-video");
      if (!lightbox || !video) return;

      let sourceGeneration = 0;
      let userPointerDown = false;
      let desiredTime = null;
      let desiredAt = 0;
      let retryFrame = 0;
      let stableSamples = 0;

      const isRegularVideo = () => Boolean(
        !lightbox.hidden
        && lightbox.classList.contains("is-video")
        && !lightbox.classList.contains("is-live")
        && !video.hidden
        && (video.currentSrc || video.getAttribute("src"))
      );

      const resetSeekState = () => {
        desiredTime = null;
        desiredAt = 0;
        stableSamples = 0;
        if (retryFrame) cancelAnimationFrame(retryFrame);
        retryFrame = 0;
      };

      const reapplyDesiredTime = () => {
        if (retryFrame || desiredTime === null || !isRegularVideo()) return;
        retryFrame = requestAnimationFrame(() => {
          retryFrame = 0;
          if (desiredTime === null || !isRegularVideo()) return;
          try { video.currentTime = desiredTime; }
          catch (_) { /* metadata/progressive download can become ready one tick later */ }
        });
      };

      const rememberSeek = () => {
        if (!isRegularVideo()) return;
        const current = Number(video.currentTime);
        if (!Number.isFinite(current)) return;
        const now = performance.now();
        const looksLikeStaleReset = desiredTime !== null
          && desiredTime > 1
          && current < .35
          && now - desiredAt < 4000
          && Math.abs(current - desiredTime) > .8;
        if (looksLikeStaleReset) {
          reapplyDesiredTime();
          return;
        }
        desiredTime = current;
        desiredAt = now;
        stableSamples = 0;
      };

      const stabilizeSeek = () => {
        if (desiredTime === null || !isRegularVideo()) return;
        const current = Number(video.currentTime);
        if (!Number.isFinite(current)) return;
        if (Math.abs(current - desiredTime) <= .35) {
          stableSamples += 1;
          if (stableSamples >= 2 && !video.seeking) {
            desiredTime = null;
            stableSamples = 0;
          }
          return;
        }
        stableSamples = 0;
        if (performance.now() - desiredAt < 5000) reapplyDesiredTime();
        else desiredTime = null;
      };

      const tryAutoplay = (generation) => {
        if (generation !== sourceGeneration || !isRegularVideo()) return;
        video.preload = "auto";
        video.autoplay = true;
        video.muted = false;
        video.playsInline = true;
        const result = video.play();
        if (result && typeof result.catch === "function") result.catch(() => {});
      };

      const syncSource = () => {
        if (!isRegularVideo()) {
          resetSeekState();
          return;
        }
        const generation = ++sourceGeneration;
        resetSeekState();
        tryAutoplay(generation);
        [40, 140, 350, 800].forEach((delay) => {
          window.setTimeout(() => tryAutoplay(generation), delay);
        });
      };

      video.addEventListener("pointerdown", () => { userPointerDown = true; }, true);
      window.addEventListener("pointerup", () => {
        window.setTimeout(() => { userPointerDown = false; }, 120);
      }, true);
      video.addEventListener("seeking", () => {
        if (userPointerDown || desiredTime === null) rememberSeek();
        else stabilizeSeek();
      });
      video.addEventListener("seeked", stabilizeSeek);
      video.addEventListener("timeupdate", stabilizeSeek);
      video.addEventListener("progress", stabilizeSeek);
      video.addEventListener("loadedmetadata", () => tryAutoplay(sourceGeneration));
      video.addEventListener("canplay", () => tryAutoplay(sourceGeneration));
      video.addEventListener("emptied", resetSeekState);

      const observer = new MutationObserver(syncSource);
      observer.observe(lightbox, { attributes: true, attributeFilter: ["hidden", "class"] });
      observer.observe(video, { attributes: true, attributeFilter: ["hidden", "src"] });
      syncSource();

      window.MEMORY_READER_VIDEO = {
        getState() {
          return {
            regular: isRegularVideo(),
            desiredTime,
            currentTime: Number.isFinite(video.currentTime) ? video.currentTime : 0,
            paused: video.paused,
          };
        },
      };
    }
  });
})();
