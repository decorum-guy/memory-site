(function () {
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
      const rail = document.getElementById("chapter-rail");
      const openButton = document.getElementById("open-book");
      if (!pages.length || !links.length || !rail) return;
      let frame = 0;
      let applying = false;
      let lockedIndex = null;
      let lockUntil = 0;

      const lock = (index, duration = 1100) => {
        lockedIndex = index;
        lockUntil = performance.now() + duration;
        update();
        window.setTimeout(schedule, duration + 20);
      };
      const activeIndex = () => {
        if (lockedIndex !== null && performance.now() < lockUntil) return lockedIndex;
        lockedIndex = null;
        const anchor = window.scrollY + Math.min(window.innerHeight * .12, 120);
        let active = 0;
        pages.forEach((page, index) => { if (page.offsetTop <= anchor) active = index; });
        return active;
      };
      const update = () => {
        frame = 0;
        applying = true;
        const active = activeIndex();
        links.forEach((link, index) => link.classList.toggle("is-active", index === active));
        applying = false;
      };
      const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };

      rail.addEventListener("click", (event) => {
        const link = event.target.closest("a");
        const index = links.indexOf(link);
        if (index >= 0) lock(index);
      }, true);
      openButton?.addEventListener("click", () => lock(0), true);
      window.addEventListener("scroll", schedule, { passive: true });
      window.addEventListener("resize", schedule);
      window.addEventListener("hashchange", schedule);
      new MutationObserver(() => {
        if (!applying) schedule();
      }).observe(rail, { subtree: true, attributes: true, attributeFilter: ["class"] });
      lock(0, 450);
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
