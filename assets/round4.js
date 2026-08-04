(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    enhanceChapterRail();
    installLivePhotoSound();
    syncCensorshipFrames(Boolean(window.MEMORY_CENSORSHIP_OFF));
  });

  document.addEventListener("memory:censorship-change", function (event) {
    syncCensorshipFrames(Boolean(event.detail && event.detail.off));
  });

  function enhanceChapterRail() {
    const rail = document.getElementById("chapter-rail");
    const chapters = Array.isArray(window.MEMORY_BOOK?.chapters) ? window.MEMORY_BOOK.chapters : [];
    if (!rail || !chapters.length) return;

    const links = [...rail.querySelectorAll("a")];
    const sections = [...document.querySelectorAll("#memory-book > .memory-page")];
    links.forEach((link, index) => {
      const label = chapterLabel(chapters[index], index);
      const span = link.querySelector("span");
      if (span) {
        span.textContent = label;
        span.setAttribute("aria-label", label);
      }
      link.addEventListener("click", () => setActive(link));
    });

    let raf = 0;
    const update = () => {
      raf = 0;
      if (!sections.length) return;
      const anchor = Math.min(window.innerHeight * .32, 280);
      let active = sections[0];
      for (const section of sections) {
        if (section.getBoundingClientRect().top <= anchor) active = section;
        else break;
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
        active = sections[sections.length - 1];
      }
      const link = links.find((candidate) => candidate.getAttribute("href") === `#${active.id}`) || links[0];
      setActive(link);
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", schedule);
    schedule();

    function setActive(activeLink) {
      links.forEach((link) => link.dataset.round4Active = link === activeLink ? "true" : "false");
    }
  }

  function chapterLabel(chapter, index) {
    if (!chapter) return String(index + 1).padStart(2, "0");
    if (chapter.id === "telegram") return "TG";
    const direct = [chapter.year, chapter.title, chapter.subtitle, chapter.kicker]
      .filter(Boolean).join(" ");
    const directMatch = direct.match(/\b(?:19|20)\d{2}\b/);
    if (directMatch) return directMatch[0];
    const deepMatch = JSON.stringify(chapter.blocks || []).match(/\b(?:19|20)\d{2}\b/);
    if (deepMatch) return deepMatch[0];
    if (chapter.id === "ending") return "FIN";
    return String(chapter.number || String(index + 1).padStart(2, "0"));
  }

  function installLivePhotoSound() {
    const liveButton = document.getElementById("lightbox-live");
    const video = document.getElementById("lightbox-video");
    const caption = document.getElementById("lightbox-caption");
    if (!liveButton || !video || !caption) return;

    const controls = document.createElement("div");
    controls.className = "lightbox__live-controls";
    liveButton.before(controls);
    controls.appendChild(liveButton);

    const sound = document.createElement("button");
    sound.type = "button";
    sound.className = "lightbox__sound";
    sound.hidden = true;
    controls.appendChild(sound);

    const updateSound = () => {
      const playingLive = !liveButton.hidden && !video.hidden && Boolean(video.getAttribute("src"));
      controls.hidden = liveButton.hidden;
      sound.hidden = !playingLive;
      sound.textContent = video.muted ? "🔇" : "🔊";
      sound.setAttribute("aria-label", video.muted ? "Включить звук Live Photo" : "Выключить звук Live Photo");
      sound.title = video.muted ? "Включить звук" : "Выключить звук";
    };

    liveButton.addEventListener("click", () => {
      requestAnimationFrame(() => {
        if (!video.hidden && Boolean(video.getAttribute("src"))) video.muted = false;
        updateSound();
      });
    });
    sound.addEventListener("click", () => {
      video.muted = !video.muted;
      updateSound();
    });
    video.addEventListener("volumechange", updateSound);
    new MutationObserver(updateSound).observe(video, { attributes: true, attributeFilter: ["hidden", "src"] });
    new MutationObserver(updateSound).observe(liveButton, { attributes: true, attributeFilter: ["hidden"] });
    updateSound();
  }

  function syncCensorshipFrames(off) {
    const original = Array.isArray(window.MEMORY_CENSORED_ITEMS) ? window.MEMORY_CENSORED_ITEMS : [];
    const byKey = new Map(original.map((item, index) => [mediaKey(item, index), item]));
    document.querySelectorAll(".image-frame[data-media-key]").forEach((frame) => {
      const item = byKey.get(frame.dataset.mediaKey);
      if (!item) return;
      const censored = !off && item.censored === true;
      frame.classList.toggle("is-censored", censored);
      frame.classList.toggle("is-revealed", !censored);
      const existing = frame.querySelector(".censor-preview");
      if (censored && !existing) {
        const cover = document.createElement("span");
        cover.className = "censor-preview";
        cover.innerHTML = "<strong>Содержание скрыто</strong><small>Нажми, чтобы открыть предупреждение</small>";
        frame.appendChild(cover);
      } else if (!censored && existing) {
        existing.remove();
      }
    });
  }

  function mediaKey(item, index) {
    const kind = item.kind || (item.liveVideo ? "live" : item.poster ? "video" : "photo");
    return String(item.id || item.src || `${kind}-${index}`);
  }
})();
