(function () {
  "use strict";

  const data = window.MEMORY_BOOK;
  if (!data || !Array.isArray(data.chapters)) {
    document.body.innerHTML = '<div class="fatal-error">Не найден файл content/memories.js или в нём есть ошибка.</div>';
    return;
  }

  const book = document.getElementById("memory-book");
  const rail = document.getElementById("chapter-rail");
  const openBookButton = document.getElementById("open-book");
  const footer = document.getElementById("book-footer");

  const lightbox = document.getElementById("lightbox");
  const lightboxImage = document.getElementById("lightbox-image");
  const lightboxCaption = document.getElementById("lightbox-caption");
  const lightboxCounter = document.getElementById("lightbox-counter");
  const lightboxClose = document.getElementById("lightbox-close");
  const lightboxPrev = document.getElementById("lightbox-prev");
  const lightboxNext = document.getElementById("lightbox-next");

  let activeGallery = [];
  let activeIndex = 0;
  let previousFocus = null;

  applyMeta();
  renderBook();
  renderRail();
  bindNavigation();
  observeChapters();

  function applyMeta() {
    const meta = data.meta || {};
    setText("cover-eyebrow", meta.eyebrow);
    setText("cover-title", meta.title);
    setText("cover-subtitle", meta.subtitle);
    setText("cover-note", meta.note);
    if (meta.footer) footer.querySelector("p").textContent = meta.footer;
    if (meta.accent) document.documentElement.style.setProperty("--accent", meta.accent);
    if (meta.title) document.title = meta.title;
  }

  function setText(id, value) {
    if (!value) return;
    const element = document.getElementById(id);
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

  function renderPhotoBlock(wrapper, block, uniqueId) {
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
    button.appendChild(createImage(block));
    button.addEventListener("click", () => openGallery([normalizePhoto(block)], 0));
    return wrapper;
  }

  function renderStackBlock(wrapper, block, uniqueId) {
    const photos = (block.photos || []).map(normalizePhoto);
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
      button.appendChild(createImage(photo));
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
    const photos = (block.photos || []).map(normalizePhoto);
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
      button.appendChild(createImage(photo));
      button.addEventListener("click", () => openGallery(photos, index));
      collage.appendChild(button);
    });
    return wrapper;
  }

  function renderVideoBlock(wrapper, block) {
    wrapper.innerHTML = `
      <figure class="video-card aspect-${safeClass(block.aspect || "landscape")}">
        <div class="video-card__frame">
          <video controls playsinline preload="metadata" ${block.poster ? `poster="${escapeAttr(block.poster)}"` : ""}>
            <source src="${escapeAttr(block.src || "")}" />
            Ваш браузер не поддерживает видео.
          </video>
          <div class="media-placeholder"><span>Добавь видео</span><small>${escapeHtml(block.src || "media/videos/video.mp4")}</small></div>
        </div>
        <figcaption>
          ${block.caption ? `<p>${escapeHtml(block.caption)}</p>` : ""}
          ${block.date ? `<span>${escapeHtml(block.date)}</span>` : ""}
        </figcaption>
      </figure>
    `;
    const video = wrapper.querySelector("video");
    video.addEventListener("error", () => wrapper.classList.add("is-missing"));
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
    wrapper.innerHTML = `
      <blockquote class="memory-quote">
        <span aria-hidden="true">“</span>
        <p>${escapeHtml(block.text || "")}</p>
        ${block.author ? `<cite>${escapeHtml(block.author)}</cite>` : ""}
      </blockquote>
    `;
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
    wrapper.innerHTML = `
      <div class="letter-sheet">
        ${block.title ? `<h3>${escapeHtml(block.title)}</h3>` : ""}
        ${paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
        ${block.signature ? `<div class="letter-signature">${escapeHtml(block.signature)}</div>` : ""}
      </div>
    `;
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
      return `
        <svg class="caption-curve" viewBox="0 0 520 110" role="img" aria-label="${escapeAttr(text)}">
          <defs><path id="${pathId}" d="M 18 78 Q 260 8 502 72" /></defs>
          <text><textPath href="#${pathId}" startOffset="50%" text-anchor="middle">${escapeHtml(text)}</textPath></text>
        </svg>
      `;
    }
    return `<p class="hand-caption hand-caption--${safeClass(style || "scribble")}">${escapeHtml(text)}</p>`;
  }

  function createImage(photo) {
    const frame = document.createElement("span");
    frame.className = "image-frame";

    const image = document.createElement("img");
    image.src = photo.src || "";
    image.alt = photo.alt || "Фотография из воспоминаний";
    image.loading = "lazy";
    image.decoding = "async";

    const placeholder = document.createElement("span");
    placeholder.className = "image-placeholder";
    placeholder.innerHTML = `<span>замени на своё фото</span><small>${escapeHtml(photo.src || "media/photos/photo.jpg")}</small>`;

    image.addEventListener("error", () => frame.classList.add("is-missing"));
    image.addEventListener("load", () => frame.classList.remove("is-missing"));

    frame.append(image, placeholder);
    return frame;
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
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox) closeGallery();
    });

    document.addEventListener("keydown", (event) => {
      if (lightbox.hidden) return;
      if (event.key === "Escape") closeGallery();
      if (event.key === "ArrowLeft") moveGallery(-1);
      if (event.key === "ArrowRight") moveGallery(1);
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

  function openGallery(photos, index) {
    if (!photos.length) return;
    activeGallery = photos;
    activeIndex = Math.max(0, Math.min(index, photos.length - 1));
    previousFocus = document.activeElement;
    updateLightbox();
    lightbox.hidden = false;
    document.body.classList.add("lightbox-open");
    lightboxClose.focus();
  }

  function closeGallery() {
    lightbox.hidden = true;
    document.body.classList.remove("lightbox-open");
    lightboxImage.removeAttribute("src");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
  }

  function moveGallery(direction) {
    if (!activeGallery.length) return;
    activeIndex = (activeIndex + direction + activeGallery.length) % activeGallery.length;
    updateLightbox();
  }

  function updateLightbox() {
    const photo = activeGallery[activeIndex];
    lightboxImage.src = photo.src || "";
    lightboxImage.alt = photo.alt || "Фотография";
    lightboxCaption.textContent = photo.caption || photo.alt || "";
    lightboxCounter.textContent = `${activeIndex + 1} / ${activeGallery.length}`;
    const multi = activeGallery.length > 1;
    lightboxPrev.hidden = !multi;
    lightboxNext.hidden = !multi;
  }

  function normalizePhoto(photo) {
    return {
      src: photo.src || "",
      alt: photo.alt || "Фотография из воспоминаний",
      caption: photo.caption || ""
    };
  }

  function stackRotation(index) {
    return [-7, 5, -2, 8, -4][index % 5];
  }

  function pad(value) { return String(value).padStart(2, "0"); }
  function numberOr(value, fallback) { return Number.isFinite(Number(value)) ? Number(value) : fallback; }
  function safeClass(value) { return String(value).toLowerCase().replace(/[^a-z0-9_-]/g, "-"); }
  function reducedMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttr(value) { return escapeHtml(value).replace(/`/g, "&#096;"); }
})();
