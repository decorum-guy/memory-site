(function () {
  "use strict";

  const data = window.MEMORY_BOOK;
  if (!data || !Array.isArray(data.chapters)) {
    document.body.innerHTML = '<div class="fatal-error">Не найден content/memories.js или в нём есть ошибка.</div>';
    return;
  }

  const book = byId("memory-book");
  const rail = byId("chapter-rail");
  const openBookButton = byId("open-book");
  const footer = byId("book-footer");
  const lightbox = byId("lightbox");
  const lightboxImage = byId("lightbox-image");
  const lightboxVideo = byId("lightbox-video");
  const lightboxLive = byId("lightbox-live");
  const lightboxCaption = byId("lightbox-caption");
  const lightboxCounter = byId("lightbox-counter");
  const lightboxClose = byId("lightbox-close");
  const lightboxPrev = byId("lightbox-prev");
  const lightboxNext = byId("lightbox-next");
  const lightboxCensor = byId("lightbox-censor");
  const lightboxCensorShow = byId("lightbox-censor-show");
  const lightboxCensorClose = byId("lightbox-censor-close");

  let activeGallery = [];
  let activeIndex = 0;
  let previousFocus = null;
  let livePlaying = false;
  const revealedCensored = new Set();

  applyMeta();
  renderBook();
  renderRail();
  bindNavigation();
  observeChapters();
  restoreReaderChrome();

  function byId(id) { return document.getElementById(id); }

  function applyMeta() {
    const meta = data.meta || {};
    setText("cover-eyebrow", meta.eyebrow);
    setText("cover-title", meta.title);
    setText("cover-subtitle", meta.subtitle);
    setText("cover-note", meta.note);
    if (meta.footer && footer) footer.querySelector("p").textContent = meta.footer;
    if (meta.accent) document.documentElement.style.setProperty("--accent", meta.accent);
    if (meta.title) document.title = meta.title;
  }

  function setText(id, value) {
    if (!value) return;
    const element = byId(id);
    if (element) element.textContent = value;
  }

  function renderBook() {
    const fragment = document.createDocumentFragment();
    data.chapters.forEach((chapter, chapterIndex) => {
      const section = document.createElement("section");
      section.className = `memory-page memory-page--${safeClass(chapter.layout || "story")} theme-${safeClass(chapter.theme || "paper")}`;
      section.id = chapter.id || `chapter-${chapterIndex + 1}`;
      section.dataset.chapterIndex = String(chapterIndex);
      section.innerHTML = `
        <div class="page-binding" aria-hidden="true"><span></span><span></span><span></span></div>
        <div class="page-shadow" aria-hidden="true"></div>
        <header class="chapter-heading">
          <p class="chapter-heading__number">${escapeHtml(chapter.number || pad(chapterIndex + 1))}</p>
          <div>
            <p class="chapter-heading__kicker">${escapeHtml(chapter.kicker || "")}</p>
            <h2>${escapeHtml(chapter.title || "Без названия")}</h2>
            ${chapter.subtitle ? `<p class="chapter-heading__subtitle">${escapeHtml(chapter.subtitle)}</p>` : ""}
          </div>
        </header>
        <div class="chapter-content"></div>
        <p class="page-number">${pad(chapterIndex + 1)}</p>
      `;
      const content = section.querySelector(".chapter-content");
      (chapter.blocks || []).forEach((block, blockIndex) => {
        content.appendChild(renderBlock(block, `${section.id}-${blockIndex}`));
      });
      fragment.appendChild(section);
    });
    book.appendChild(fragment);
  }

  function renderBlock(block, uniqueId) {
    const wrapper = document.createElement("article");
    wrapper.className = `memory-block memory-block--${safeClass(block.type || "note")}`;
    wrapper.style.setProperty("--rotate", `${numberOr(block.rotate, 0)}deg`);
    if (block.width) wrapper.dataset.width = block.width;
    if (block.align) wrapper.dataset.align = block.align;

    switch (block.type) {
      case "event": return renderEventBlock(wrapper, block, uniqueId);
      case "photo": return renderPhotoBlock(wrapper, block, uniqueId);
      case "stack": return renderStackBlock(wrapper, block, uniqueId);
      case "collage": return renderCollageBlock(wrapper, block, uniqueId);
      case "video": return renderVideoBlock(wrapper, block);
      case "audio": return renderAudioBlock(wrapper, block);
      case "quote": return renderQuoteBlock(wrapper, block);
      case "sticker": return renderStickerBlock(wrapper, block);
      case "caption": return renderCaptionBlock(wrapper, block, uniqueId);
      case "letter": return renderLetterBlock(wrapper, block);
      case "note":
      default: return renderNoteBlock(wrapper, block);
    }
  }

  function renderEventBlock(wrapper, block, uniqueId) {
    const items = (block.items || []).map(normalizeMedia);
    const layout = block.layout === "stack" && items.length > 8 ? "stack" : "collage";
    const previewItems = items.filter((item) => item.kind !== "audio").slice(0, layout === "stack" ? 5 : 8);
    const rowCount = layout === "stack" ? 0 : (previewItems.length <= 4 ? 1 : 2);
    wrapper.classList.add(`event-layout-${safeClass(layout)}`, `event-count-${Math.min(items.length, 8)}`);
    if (rowCount) wrapper.classList.add(`event-rows-${rowCount}`);
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
    count.textContent = `${items.length} ${plural(items.length, "файл", "файла", "файлов")}`;
    preview.appendChild(count);
    wrapper.querySelector(".event-open").addEventListener("click", () => openGallery(items, 0));
    return wrapper;
  }

  function renderPhotoBlock(wrapper, block, uniqueId) {
    const photo = normalizeMedia({ ...block, kind: block.liveVideo ? "live" : "photo" });
    wrapper.innerHTML = `
      <figure class="polaroid tape-${safeClass(block.tape || "cream")}">
        <button class="photo-button" type="button" aria-label="Открыть фотографию крупно"></button>
        <figcaption>
          ${renderCaption(block.caption || "", block.captionStyle, uniqueId)}
          ${block.date ? `<span class="photo-date">${escapeHtml(block.date)}</span>` : ""}
        </figcaption>
      </figure>
    `;
    const button = wrapper.querySelector(".photo-button");
    button.appendChild(createMediaPreview(photo));
    button.addEventListener("click", () => openGallery([photo], 0));
    return wrapper;
  }

  function renderStackBlock(wrapper, block, uniqueId) {
    const photos = (block.photos || []).map((photo) => normalizeMedia({ ...photo, kind: photo.liveVideo ? "live" : "photo" }));
    wrapper.innerHTML = `
      <div class="stack-copy">
        ${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}
        ${renderCaption(block.caption || "", block.captionStyle || "scribble", uniqueId)}
      </div>
      <div class="photo-stack" aria-label="Стопка из ${photos.length} фотографий"></div>
    `;
    const stack = wrapper.querySelector(".photo-stack");
    photos.slice(0, 5).forEach((photo, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "photo-stack__item";
      button.style.setProperty("--stack-index", String(index));
      button.style.setProperty("--stack-rotate", `${stackRotation(index)}deg`);
      button.setAttribute("aria-label", `Открыть фотографию ${index + 1} из ${photos.length}`);
      button.appendChild(createMediaPreview(photo));
      button.addEventListener("click", () => openGallery(photos, index));
      stack.appendChild(button);
    });
    const badge = document.createElement("span");
    badge.className = "photo-stack__count";
    badge.textContent = `${photos.length} фото`;
    stack.appendChild(badge);
    return wrapper;
  }

  function renderCollageBlock(wrapper, block, uniqueId) {
    const photos = (block.photos || []).map((photo) => normalizeMedia({ ...photo, kind: photo.liveVideo ? "live" : "photo" }));
    wrapper.innerHTML = `
      <header class="collage-heading">
        ${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}
        ${renderCaption(block.caption || "", "scribble", uniqueId)}
      </header>
      <div class="scrap-collage" aria-label="Коллаж из ${photos.length} фотографий"></div>
    `;
    const collage = wrapper.querySelector(".scrap-collage");
    photos.forEach((photo, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `scrap-collage__item scrap-collage__item--${(index % 7) + 1}`;
      button.setAttribute("aria-label", `Открыть фотографию ${index + 1}`);
      button.appendChild(createMediaPreview(photo));
      button.addEventListener("click", () => openGallery(photos, index));
      collage.appendChild(button);
    });
    return wrapper;
  }

  function renderVideoBlock(wrapper, block) {
    const videoItem = normalizeMedia({ ...block, kind: "video" });
    wrapper.innerHTML = `
      <figure class="video-card aspect-${safeClass(block.aspect || "landscape")}">
        <button class="video-card__frame" type="button" aria-label="Открыть видео"></button>
        <figcaption>
          ${block.caption ? `<p>${escapeHtml(block.caption)}</p>` : ""}
          ${block.date ? `<span>${escapeHtml(block.date)}</span>` : ""}
        </figcaption>
      </figure>
    `;
    const button = wrapper.querySelector(".video-card__frame");
    button.appendChild(createMediaPreview(videoItem));
    button.addEventListener("click", () => openGallery([videoItem], 0));
    return wrapper;
  }

  function renderAudioBlock(wrapper, block) {
    wrapper.innerHTML = `
      <div class="audio-card">
        <div class="audio-card__icon" aria-hidden="true">♫</div>
        <div class="audio-card__copy">
          <h3>${escapeHtml(block.title || "Аудиозапись")}</h3>
          ${block.caption ? `<p>${escapeHtml(block.caption)}</p>` : ""}
          <audio controls preload="metadata" src="${escapeAttr(block.src || "")}"></audio>
        </div>
      </div>
    `;
    return wrapper;
  }

  function renderQuoteBlock(wrapper, block) {
    wrapper.innerHTML = `<blockquote class="memory-quote"><span aria-hidden="true">“</span><p>${escapeHtml(block.text || "")}</p>${block.author ? `<cite>${escapeHtml(block.author)}</cite>` : ""}</blockquote>`;
    return wrapper;
  }

  function renderStickerBlock(wrapper, block) {
    wrapper.innerHTML = `<div class="sticker"><span>${escapeHtml(block.icon || "✦")}</span>${escapeHtml(block.text || "")}</div>`;
    return wrapper;
  }

  function renderCaptionBlock(wrapper, block, uniqueId) {
    wrapper.innerHTML = renderCaption(block.text || "", block.style || "scribble", uniqueId);
    return wrapper;
  }

  function renderLetterBlock(wrapper, block) {
    const paragraphs = Array.isArray(block.text) ? block.text : [block.text || ""];
    wrapper.innerHTML = `<div class="letter-sheet">${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}${paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("")}${block.signature ? `<div class="letter-signature">${escapeHtml(block.signature)}</div>` : ""}</div>`;
    return wrapper;
  }

  function renderNoteBlock(wrapper, block) {
    wrapper.innerHTML = `<div class="paper-note paper-note--${safeClass(block.style || "plain")}"><p>${escapeHtml(block.text || "")}</p></div>`;
    return wrapper;
  }

  function renderCaption(text, style, uniqueId) {
    if (!text) return "";
    if (style === "curve") {
      const pathId = `curve-${uniqueId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
      return `<svg class="caption-curve" viewBox="0 0 520 110" role="img" aria-label="${escapeAttr(text)}"><defs><path id="${pathId}" d="M 18 78 Q 260 8 502 72" /></defs><text><textPath href="#${pathId}" startOffset="50%" text-anchor="middle">${escapeHtml(text)}</textPath></text></svg>`;
    }
    return `<p class="hand-caption hand-caption--${safeClass(style || "scribble")}">${escapeHtml(text)}</p>`;
  }

  function createMediaPreview(item) {
    const frame = document.createElement("span");
    const key = mediaKey(item);
    const locallyRevealed = revealedCensored.has(key);
    const isCensored = item.censored && !locallyRevealed;
    const crop = normalizeCrop(item.crop);
    frame.className = `image-frame media-kind-${safeClass(item.kind)}`;
    frame.dataset.mediaKey = key;
    frame.classList.toggle("is-censored", isCensored);
    frame.classList.toggle("is-revealed", locallyRevealed);

    const useSelectedVideoFrame = item.kind === "video" && item.posterTime !== null;
    const media = document.createElement(useSelectedVideoFrame ? "video" : "img");
    media.style.objectPosition = `${crop.x}% ${crop.y}%`;

    if (useSelectedVideoFrame) {
      media.muted = true;
      media.playsInline = true;
      media.preload = "auto";
      media.poster = item.poster || "";
      media.src = item.src || "";
      media.dataset.posterTime = String(item.posterTime);
    } else {
      media.src = item.thumb || item.poster || item.src || "";
      media.alt = isCensored ? "Скрытое воспоминание" : (item.alt || (item.kind === "video" ? "Видео из воспоминаний" : "Фотография из воспоминаний"));
      media.loading = "lazy";
      media.decoding = "async";
    }

    const placeholder = document.createElement("span");
    placeholder.className = "image-placeholder";
    placeholder.innerHTML = `<span>файл не найден</span><small>${escapeHtml(item.src || "")}</small>`;
    media.addEventListener("error", () => frame.classList.add("is-missing"));
    media.addEventListener(useSelectedVideoFrame ? "loadeddata" : "load", () => frame.classList.remove("is-missing"));
    frame.append(media, placeholder);
    if (useSelectedVideoFrame) seekPreviewVideo(media, item.posterTime);

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

  function seekPreviewVideo(video, time) {
    const requested = Math.max(0, Number(time) || 0);
    let attempts = 0;
    const seek = () => {
      if (!video.isConnected && attempts < 8) {
        attempts += 1;
        window.setTimeout(seek, 40 * attempts);
        return;
      }
      const duration = Number.isFinite(video.duration) ? video.duration : Infinity;
      const safe = duration === Infinity ? requested : Math.min(requested, Math.max(0, duration - .01));
      try {
        if (Math.abs(video.currentTime - safe) > .03) video.currentTime = safe;
        video.pause();
      } catch (_) {
        if (attempts < 8) {
          attempts += 1;
          window.setTimeout(seek, 60 * attempts);
        }
      }
    };
    ["loadedmetadata", "loadeddata", "canplay"].forEach((name) => video.addEventListener(name, seek));
    video.addEventListener("seeked", () => {
      video.pause();
      video.dataset.frameReady = "1";
    });
    requestAnimationFrame(seek);
  }

  function renderRail() {
    const list = document.createElement("ol");
    data.chapters.forEach((chapter, index) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = `#${chapter.id || `chapter-${index + 1}`}`;
      link.innerHTML = `<span>${escapeHtml(chapter.number || pad(index + 1))}</span><em>${escapeHtml(chapter.kicker || chapter.title || "Глава")}</em>`;
      item.appendChild(link);
      list.appendChild(item);
    });
    rail.appendChild(list);
  }

  function bindNavigation() {
    openBookButton.addEventListener("click", () => {
      document.body.classList.add("book-opened");
      const first = book.querySelector(".memory-page");
      if (first) first.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth" });
    });

    rail.addEventListener("click", (event) => {
      const link = event.target.closest("a");
      if (!link) return;
      event.preventDefault();
      const target = document.querySelector(link.getAttribute("href"));
      if (target) target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
    });

    lightboxClose.addEventListener("click", closeGallery);
    lightboxPrev.addEventListener("click", () => moveGallery(-1));
    lightboxNext.addEventListener("click", () => moveGallery(1));
    lightboxLive.addEventListener("click", toggleLive);
    lightboxCensorShow.addEventListener("click", revealCurrentCensored);
    lightboxCensorClose.addEventListener("click", closeGallery);
    lightbox.addEventListener("click", (event) => { if (event.target === lightbox) closeGallery(); });
    document.addEventListener("keydown", (event) => {
      if (lightbox.hidden) return;
      if (event.key === "Escape") closeGallery();
      if (event.key === "ArrowLeft") moveGallery(-1);
      if (event.key === "ArrowRight") moveGallery(1);
      if (event.key === " ") {
        const current = activeGallery[activeIndex];
        if (current && current.kind === "live" && !isCurrentCensoredLocked()) {
          event.preventDefault();
          toggleLive();
        }
      }
    });
  }

  function observeChapters() {
    const sections = [...book.querySelectorAll(".memory-page")];
    const links = [...rail.querySelectorAll("a")];
    if (!("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((link) => link.classList.toggle("is-active", link.getAttribute("href") === `#${entry.target.id}`));
      });
    }, { rootMargin: "-25% 0px -60% 0px", threshold: 0.01 });
    sections.forEach((section) => observer.observe(section));
  }

  function openGallery(items, index) {
    if (!items.length) return;
    activeGallery = items;
    activeIndex = Math.max(0, Math.min(index, items.length - 1));
    previousFocus = document.activeElement;
    updateLightbox();
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    if (isCurrentCensoredLocked()) lightboxCensorShow.focus();
    else lightboxClose.focus();
  }

  function closeGallery() {
    stopMedia();
    lightbox.hidden = true;
    lightboxCensor.hidden = true;
    document.body.classList.remove("lightbox-open");
    lightboxImage.removeAttribute("src");
    lightboxVideo.removeAttribute("src");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
  }

  function moveGallery(direction) {
    if (!activeGallery.length) return;
    activeIndex = (activeIndex + direction + activeGallery.length) % activeGallery.length;
    updateLightbox();
  }

  function updateLightbox() {
    stopMedia();
    const item = activeGallery[activeIndex];
    lightboxCaption.innerHTML = renderMediaCaption(item);
    lightboxCounter.textContent = `${activeIndex + 1} / ${activeGallery.length}`;
    const multi = activeGallery.length > 1;
    lightboxPrev.hidden = !multi;
    lightboxNext.hidden = !multi;
    lightbox.classList.toggle("is-video", item.kind === "video");
    lightbox.classList.toggle("is-live", item.kind === "live");

    if (item.censored && !revealedCensored.has(mediaKey(item))) {
      lockCensoredItem();
      return;
    }
    renderLightboxMedia(item);
  }

  function lockCensoredItem() {
    stopMedia();
    lightboxImage.hidden = true;
    lightboxVideo.hidden = true;
    lightboxLive.hidden = true;
    lightboxCensor.hidden = false;
  }

  function revealCurrentCensored() {
    const item = activeGallery[activeIndex];
    if (!item) return;
    revealedCensored.add(mediaKey(item));
    revealPreviewCopies(item);
    lightboxCensor.hidden = true;
    renderLightboxMedia(item);
    lightboxClose.focus();
  }

  function renderLightboxMedia(item) {
    lightboxCensor.hidden = true;
    if (item.kind === "video") {
      lightboxImage.hidden = true;
      lightboxVideo.hidden = false;
      lightboxVideo.poster = item.poster || "";
      lightboxVideo.controls = true;
      lightboxVideo.muted = false;
      lightboxVideo.loop = false;
      lightboxVideo.preload = "metadata";
      lightboxVideo.src = item.src || "";
      lightboxLive.hidden = true;
    } else {
      lightboxVideo.hidden = true;
      lightboxImage.hidden = false;
      lightboxImage.src = item.src || "";
      lightboxImage.alt = item.alt || "Фотография";
      lightboxLive.hidden = item.kind !== "live" || !item.liveVideo;
      lightboxLive.textContent = "▶ Оживить фото";
    }
  }

  function toggleLive() {
    const item = activeGallery[activeIndex];
    if (!item || item.kind !== "live" || !item.liveVideo || isCurrentCensoredLocked()) return;
    if (livePlaying) {
      stopMedia();
      lightboxImage.hidden = false;
      lightboxVideo.hidden = true;
      lightboxLive.textContent = "▶ Оживить фото";
      return;
    }
    livePlaying = true;
    lightboxImage.hidden = true;
    lightboxVideo.hidden = false;
    lightboxVideo.controls = false;
    lightboxVideo.muted = true;
    lightboxVideo.loop = true;
    lightboxVideo.poster = item.src || "";
    lightboxVideo.preload = "auto";
    lightboxVideo.src = item.liveVideo;
    lightboxVideo.play().catch(() => {
      lightboxVideo.controls = true;
      lightboxLive.textContent = "Нажми Play";
    });
    lightboxLive.textContent = "■ Остановить";
  }

  function stopMedia() {
    livePlaying = false;
    lightboxVideo.pause();
    lightboxVideo.removeAttribute("src");
    lightboxVideo.load();
  }

  function isCurrentCensoredLocked() {
    const item = activeGallery[activeIndex];
    return Boolean(item && item.censored && !revealedCensored.has(mediaKey(item)));
  }

  function mediaKey(item, fallbackIndex = activeIndex) {
    return String(item.id || item.src || `${item.kind}-${fallbackIndex}`);
  }

  function normalizeMedia(item) {
    const inferred = item.kind || (item.liveVideo ? "live" : item.poster ? "video" : "photo");
    const takenAt = item.takenAt || "";
    const rawCaption = item.caption || item.note || "";
    const posterTimeValue = item.posterTime === null || item.posterTime === undefined || item.posterTime === ""
      ? null
      : Number(item.posterTime);
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
      censored: item.censored === true,
      crop: normalizeCrop(item.crop),
      posterTime: Number.isFinite(posterTimeValue) && posterTimeValue >= 0 ? posterTimeValue : null
    };
  }

  function normalizeCrop(value) {
    const x = Number(value?.x);
    const y = Number(value?.y);
    return {
      x: Number.isFinite(x) ? Math.min(100, Math.max(0, x)) : 50,
      y: Number.isFinite(y) ? Math.min(100, Math.max(0, y)) : 50
    };
  }

  function restoreReaderChrome() {
    const params = new URLSearchParams(window.location.search);
    const forcedOpen = params.get("opened") === "1" || window.location.hash === "#memory-book";
    const update = () => {
      const cover = byId("cover");
      const threshold = cover ? Math.min(160, cover.offsetHeight * .12) : 80;
      if (forcedOpen || window.scrollY > threshold || window.location.hash) {
        document.body.classList.add("book-opened");
      }
    };
    update();
    [80, 250, 700, 1500].forEach((delay) => window.setTimeout(update, delay));
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("pageshow", () => requestAnimationFrame(update));
    window.addEventListener("hashchange", update);
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

  function formatDate(value) {
    if (!value) return "Воспоминание";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    return `${minutes}:${String(secs).padStart(2, "0")}`;
  }

  function plural(number, one, few, many) {
    const mod10 = number % 10;
    const mod100 = number % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
    return many;
  }

  function stackRotation(index) { return [-7, 5, -2, 8, -4][index % 5]; }
  function pad(value) { return String(value).padStart(2, "0"); }
  function numberOr(value, fallback) { return Number.isFinite(Number(value)) ? Number(value) : fallback; }
  function safeClass(value) { return String(value).toLowerCase().replace(/[^a-z0-9_-]/g, "-"); }
  function reducedMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function escapeHtml(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
  function escapeAttr(value) { return escapeHtml(value).replace(/`/g, "&#096;"); }
})();
