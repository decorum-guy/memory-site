(function () {
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
