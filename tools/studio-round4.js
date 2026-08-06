(function () {
  installStudioTabs();
  installProductionApply();

  const baseNormalizeBook = normalizeBook;
  normalizeBook = function round4NormalizeBook() {
    baseNormalizeBook();
    book.meta ||= {};
    if (book.meta.typography && typeof book.meta.typography !== "object") delete book.meta.typography;
    book.chapters.forEach((chapter) => {
      const year = String(chapter.title || "").match(/\b(?:19|20)\d{2}\b/)?.[0];
      if (year && (!chapter.number || /^\d{1,2}$/.test(String(chapter.number)))) chapter.number = year;
      chapter.kicker ||= "Глава по времени";
      chapter.subtitle ||= "";
      (chapter.blocks || []).forEach((block) => {
        (block.items || []).forEach((item) => {
          const location = String(item.location || "").trim();
          if (location) item.location = location;
          else delete item.location;
          const lat = Number(item.gps?.lat);
          const lon = Number(item.gps?.lon);
          if (Number.isFinite(lat) && Number.isFinite(lon)) item.gps = { lat, lon };
          else delete item.gps;
        });
      });
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

  const baseRenderItem = renderItem;
  renderItem = function round4RenderItem(item, chapterIndex, blockIndex, itemIndex) {
    const card = baseRenderItem(item, chapterIndex, blockIndex, itemIndex);
    const fields = card.querySelector(".item-fields");
    const expand = fields?.querySelector("[data-expand]");
    if (!fields || !expand) return card;

    const label = document.createElement("label");
    label.className = "item-location-field";
    label.innerHTML = `
      <span>Местоположение в открытой карточке</span>
      <input data-location type="text" value="${escapeAttr(item.location || "")}" placeholder="Например: Москва, Россия или Наш двор" />
      <small>${gpsHint(item)}</small>`;
    fields.insertBefore(label, expand);
    label.querySelector("[data-location]").addEventListener("change", (inputEvent) => {
      snapshot();
      const value = String(inputEvent.target.value || "").trim();
      if (value) item.location = value;
      else delete item.location;
      status.textContent = value
        ? "Местоположение изменено. Экспортируй memories.js, чтобы применить его к книге."
        : "Местоположение скрыто. Экспортируй memories.js, чтобы применить изменение.";
    });
    return card;
  };

  const baseRender = render;
  render = function round4Render() {
    baseRender();
    renderBookSettings();
  };

  function installStudioTabs() {
    const top = document.querySelector(".top");
    if (!top || top.querySelector(".studio-tabs")) return;
    const tabs = document.createElement("nav");
    tabs.className = "studio-tabs";
    tabs.setAttribute("aria-label", "Разделы конструктора");
    tabs.innerHTML = `
      <a class="is-active" href="studio.html" aria-current="page">Memory Studio</a>
      <a href="telegram_studio.html">Telegram Studio</a>`;
    top.prepend(tabs);
  }

  function installProductionApply() {
    const top = document.querySelector(".top");
    const exportButton = document.getElementById("export");
    if (!top || !exportButton || document.getElementById("apply-production-file") || testMode) return;

    const label = document.createElement("label");
    label.className = "studio-apply-production";
    label.innerHTML = `Применить в production<input id="apply-production-file" type="file" accept=".js,.json" />`;
    exportButton.insertAdjacentElement("afterend", label);

    const guide = document.querySelector(".button-guide dl");
    if (guide) {
      const row = document.createElement("div");
      row.innerHTML = `<dt>Применить в production</dt><dd>Выбирает скачанный memories.js, делает резервную копию, проверяет медиа и сразу открывает обновлённую книгу.</dd>`;
      guide.appendChild(row);
    }

    label.querySelector("input").addEventListener("change", applyProductionFile);
  }

  async function applyProductionFile(fileEvent) {
    const input = fileEvent.target;
    const file = input.files?.[0];
    if (!file) return;
    if (!confirm(`Применить «${file.name}» к основной книге? Перед заменой будет создана резервная копия.`)) {
      input.value = "";
      return;
    }

    let parsed;
    let previewWindow = null;
    try {
      const text = await file.text();
      parsed = parseMemoryText(text);
      previewWindow = window.open("about:blank", "memory-production-preview");
      if (previewWindow) {
        previewWindow.document.title = "Применение memories.js…";
        previewWindow.document.body.textContent = "Проверяю файл и обновляю книгу…";
      }
      status.textContent = "Проверяю memories.js и применяю его к production…";
      const response = await fetch("/api/memory/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: file.name, text })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);

      snapshot();
      book = parsed;
      normalizeBook();
      render();
      status.textContent = `Production обновлён. Резервная копия: ${result.backup || "создана"}`;

      const target = new URL(result.bookUrl || "../index.html?opened=1", location.href);
      target.searchParams.set("v", String(Date.now()));
      if (previewWindow && !previewWindow.closed) previewWindow.location.replace(target.href);
      else window.open(target.href, "_blank");
    } catch (error) {
      if (previewWindow && !previewWindow.closed) previewWindow.close();
      const localHint = location.protocol === "file:"
        ? " Открой Studio через python3 tools/telegram_server.py, а не как file://."
        : "";
      status.textContent = `Не удалось применить файл: ${error.message}.${localHint}`;
      alert(`Не удалось применить memories.js: ${error.message}.${localHint}`);
    } finally {
      input.value = "";
    }
  }

  function parseMemoryText(text) {
    const match = String(text || "").match(/window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$/);
    const parsed = JSON.parse(match ? match[1] : text);
    if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.chapters)) {
      throw new Error("неверная структура книги");
    }
    return parsed;
  }

  function gpsHint(item) {
    const lat = Number(item.gps?.lat);
    const lon = Number(item.gps?.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return "GPS в исходном файле отсутствует — поле можно заполнить вручную или оставить пустым.";
    return `GPS сохранён: ${lat.toFixed(5)}, ${lon.toFixed(5)}. Координаты в книге не показываются.`;
  }

  function renderBookSettings() {
    let panel = document.getElementById("book-settings");
    if (!panel) {
      panel = document.createElement("section");
      panel.id = "book-settings";
      panel.className = "book-settings";
      workspace.before(panel);
    }
    const meta = book.meta ||= {};
    const typography = meta.typography || {};
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
      </div>
      <section class="typography-settings">
        <header>
          <div><h3>Общий кегль книги</h3><p>Настройки сохраняются в memories.js. Главная — подпись под датой конкретного дня.</p></div>
          <button type="button" data-reset-typography>Сбросить на авто</button>
        </header>
        <div class="typography-settings__grid">
          ${rangeField("eventCaptionPx", "Подпись к конкретному дню", typography.eventCaptionPx ?? 16, 10, 32, "px")}
          ${rangeField("eventDatePx", "Дата дня", typography.eventDatePx ?? 36, 20, 64, "px")}
          ${rangeField("polaroidCaptionScale", "Подписи на полароидах", typography.polaroidCaptionScale ?? 100, 60, 180, "%")}
        </div>
        <div class="typography-preview" aria-label="Предпросмотр кегля">
          <strong data-type-preview="eventDate">17 ноября 2025</strong>
          <span data-type-preview="eventCaption">Добавь сюда одну короткую деталь об этом дне.</span>
          <em data-type-preview="polaroid">Наша маленькая подпись</em>
        </div>
      </section>`;
    panel.querySelectorAll("[data-meta-field]").forEach((input) => {
      input.addEventListener("change", () => {
        snapshot();
        meta[input.dataset.metaField] = input.value;
        status.textContent = "Подписи книги изменены. Экспортируй memories.js, чтобы применить их.";
      });
    });
    bindTypographyControls(panel, meta);
  }

  function bindTypographyControls(panel, meta) {
    const controls = [...panel.querySelectorAll("[data-typography-field]")];
    const updatePreview = () => {
      const values = Object.fromEntries(controls.map((input) => [input.dataset.typographyField, Number(input.value)]));
      controls.forEach((input) => {
        const output = panel.querySelector(`[data-typography-output="${input.dataset.typographyField}"]`);
        if (output) output.textContent = `${input.value}${input.dataset.unit}`;
      });
      panel.querySelector('[data-type-preview="eventDate"]').style.fontSize = `${values.eventDatePx}px`;
      panel.querySelector('[data-type-preview="eventCaption"]').style.fontSize = `${values.eventCaptionPx}px`;
      panel.querySelector('[data-type-preview="polaroid"]').style.fontSize = `${14 * values.polaroidCaptionScale / 100}px`;
    };
    controls.forEach((input) => {
      input.addEventListener("input", updatePreview);
      input.addEventListener("change", () => {
        snapshot();
        meta.typography ||= {};
        meta.typography[input.dataset.typographyField] = Number(input.value);
        status.textContent = "Кегль изменён. Экспортируй memories.js или нажми «Применить в production».";
      });
    });
    panel.querySelector("[data-reset-typography]").addEventListener("click", () => {
      snapshot();
      delete meta.typography;
      render();
      status.textContent = "Кегль возвращён к автоматическим размерам.";
    });
    updatePreview();
  }

  function field(key, label, value) {
    return `<label><span>${label}</span><input data-meta-field="${key}" value="${escapeAttr(value || "")}" /></label>`;
  }
  function area(key, label, value, wide = false) {
    return `<label class="${wide ? "wide" : ""}"><span>${label}</span><textarea data-meta-field="${key}">${escapeHtml(value || "")}</textarea></label>`;
  }
  function rangeField(key, label, value, min, max, unit) {
    return `<label class="typography-control"><span>${label}</span><div><input data-typography-field="${key}" data-unit="${unit}" type="range" min="${min}" max="${max}" step="1" value="${value}" /><output data-typography-output="${key}">${value}${unit}</output></div></label>`;
  }

  normalizeBook();
  render();
})();
