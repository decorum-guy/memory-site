(function () {
  "use strict";

  const ready = (callback) => document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", callback, { once: true })
    : callback();

  ready(function installMediaImporter() {
    if (document.getElementById("memory-media-import")) return;
    const top = document.querySelector(".top");
    const exportButton = document.getElementById("export");
    if (!top || !exportButton) return;

    const trigger = document.createElement("button");
    trigger.id = "memory-media-import";
    trigger.type = "button";
    trigger.className = "memory-media-import-trigger";
    trigger.textContent = "Добавить фото и видео";
    exportButton.insertAdjacentElement("afterend", trigger);

    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = "studio-media-import.css";
    document.head.appendChild(style);

    const dialog = document.createElement("dialog");
    dialog.id = "memory-media-import-dialog";
    dialog.className = "memory-media-import-dialog";
    dialog.innerHTML = `
      <form method="dialog" class="media-import-shell">
        <header class="media-import-header">
          <div>
            <span class="media-import-eyebrow">Инкрементальный импорт</span>
            <h2>Добавить новые воспоминания</h2>
            <p>Текущая книга не пересобирается. Новые оригиналы обрабатываются локально и добавляются к уже отредактированному memories.js.</p>
          </div>
          <button type="button" class="media-import-close" data-import-close aria-label="Закрыть">×</button>
        </header>

        <section class="media-import-section">
          <div class="media-import-section__heading">
            <div><strong>Пакет фото и видео</strong><small>Можно выбрать много файлов или целую папку. Даты, типы, GPS и обычные события определятся автоматически.</small></div>
            <div class="media-import-picker-row">
              <label class="media-import-picker">Выбрать файлы<input data-import-files type="file" multiple accept="image/*,video/*,.heic,.heif,.jpg,.jpeg,.png,.webp,.tif,.tiff,.mov,.mp4,.m4v" /></label>
              <label class="media-import-picker media-import-picker--secondary">Выбрать папку<input data-import-folder type="file" multiple webkitdirectory /></label>
            </div>
          </div>
          <div class="media-import-drop" data-import-drop>
            Перетащи сюда фотографии и видео
            <small>Live Photo с совпадающим Apple ContentIdentifier или именем тоже распознаются автоматически.</small>
          </div>
        </section>

        <section class="media-import-section media-import-live">
          <div class="media-import-section__heading">
            <div><strong>Явная пара Live Photo</strong><small>Выбери неподвижное фото и именно соответствующий ему MOV/MP4. Можно добавить несколько пар.</small></div>
          </div>
          <div class="media-import-live__controls">
            <label><span>Фото</span><input data-live-photo type="file" accept="image/*,.heic,.heif,.jpg,.jpeg,.png,.webp,.tif,.tiff" /></label>
            <label><span>Видео Live Photo</span><input data-live-video type="file" accept="video/*,.mov,.mp4,.m4v" /></label>
            <button type="button" data-add-live-pair>Добавить пару</button>
          </div>
          <div class="media-import-pairs" data-live-pairs></div>
        </section>

        <section class="media-import-section">
          <label class="media-import-destination">
            <span>Куда добавить</span>
            <select data-import-target></select>
            <small>Автоматический режим группирует только новые файлы по времени, месту и визуальной близости. Уже существующие события не объединяются и не перестраиваются.</small>
          </label>
        </section>

        <section class="media-import-section media-import-queue-section">
          <div class="media-import-section__heading">
            <div><strong>Очередь</strong><small data-import-summary>Файлы ещё не выбраны.</small></div>
            <button type="button" class="media-import-clear" data-import-clear>Очистить</button>
          </div>
          <div class="media-import-queue" data-import-queue></div>
        </section>

        <section class="media-import-progress" data-import-progress hidden>
          <div><strong data-import-progress-title>Подготовка…</strong><span data-import-progress-count></span></div>
          <progress value="0" max="1"></progress>
          <small>Не закрывай Studio: видео и Live Photo могут обрабатываться несколько минут.</small>
        </section>

        <footer class="media-import-footer">
          <p>Перед изменением production автоматически создаётся резервная копия. Исходники никуда не отправляются.</p>
          <div>
            <button type="button" data-import-cancel>Отмена</button>
            <button type="button" class="primary" data-import-start disabled>Импортировать</button>
          </div>
        </footer>
      </form>`;
    document.body.appendChild(dialog);

    const state = {
      files: new Map(),
      pairs: [],
      busy: false,
    };
    const queue = dialog.querySelector("[data-import-queue]");
    const pairList = dialog.querySelector("[data-live-pairs]");
    const summary = dialog.querySelector("[data-import-summary]");
    const startButton = dialog.querySelector("[data-import-start]");
    const targetSelect = dialog.querySelector("[data-import-target]");
    const photoInput = dialog.querySelector("[data-live-photo]");
    const videoInput = dialog.querySelector("[data-live-video]");
    const progressBox = dialog.querySelector("[data-import-progress]");
    const progress = progressBox.querySelector("progress");
    const progressTitle = progressBox.querySelector("[data-import-progress-title]");
    const progressCount = progressBox.querySelector("[data-import-progress-count]");

    trigger.addEventListener("click", () => {
      populateTargets();
      renderState();
      dialog.showModal();
    });
    dialog.querySelector("[data-import-close]").addEventListener("click", closeDialog);
    dialog.querySelector("[data-import-cancel]").addEventListener("click", closeDialog);
    dialog.addEventListener("cancel", (event) => {
      if (state.busy) event.preventDefault();
    });
    dialog.querySelector("[data-import-files]").addEventListener("change", (event) => addFiles(event.target.files));
    dialog.querySelector("[data-import-folder]").addEventListener("change", (event) => addFiles(event.target.files));
    dialog.querySelector("[data-add-live-pair]").addEventListener("click", addLivePair);
    dialog.querySelector("[data-import-clear]").addEventListener("click", clearState);
    startButton.addEventListener("click", startImport);

    const drop = dialog.querySelector("[data-import-drop]");
    ["dragenter", "dragover"].forEach((name) => drop.addEventListener(name, (event) => {
      event.preventDefault();
      drop.classList.add("is-dragover");
    }));
    ["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (event) => {
      event.preventDefault();
      drop.classList.remove("is-dragover");
    }));
    drop.addEventListener("drop", (event) => addFiles(event.dataTransfer?.files));

    queue.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove-file]");
      if (!remove || state.busy) return;
      const key = remove.dataset.removeFile;
      state.files.delete(key);
      state.pairs = state.pairs.filter((pair) => pair.photoKey !== key && pair.videoKey !== key);
      renderState();
    });
    pairList.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove-pair]");
      if (!remove || state.busy) return;
      state.pairs.splice(Number(remove.dataset.removePair), 1);
      renderState();
    });

    function fileKey(file) {
      return `${file.name}::${file.size}::${file.lastModified}::${file.type}`;
    }

    function addFiles(fileList) {
      [...(fileList || [])].forEach((file) => {
        if (!isSupported(file)) return;
        state.files.set(fileKey(file), file);
      });
      renderState();
    }

    function isSupported(file) {
      return /\.(heic|heif|jpe?g|png|webp|tiff?|mov|mp4|m4v)$/i.test(file.name)
        || /^(image|video)\//.test(file.type || "");
    }

    function isPhoto(file) {
      return /\.(heic|heif|jpe?g|png|webp|tiff?)$/i.test(file.name) || /^image\//.test(file.type || "");
    }

    function isVideo(file) {
      return /\.(mov|mp4|m4v)$/i.test(file.name) || /^video\//.test(file.type || "");
    }

    function addLivePair() {
      const photo = photoInput.files?.[0];
      const video = videoInput.files?.[0];
      if (!photo || !video) {
        alert("Для Live Photo выбери и фото, и соответствующий видеофайл.");
        return;
      }
      if (!isPhoto(photo) || !isVideo(video)) {
        alert("В первой ячейке должно быть фото, во второй — MOV/MP4 Live Photo.");
        return;
      }
      const photoKey = fileKey(photo);
      const videoKey = fileKey(video);
      if (state.pairs.some((pair) => pair.photoKey === photoKey || pair.videoKey === videoKey)) {
        alert("Это фото или видео уже используется в явной Live Photo паре.");
        return;
      }
      state.files.set(photoKey, photo);
      state.files.set(videoKey, video);
      state.pairs.push({ photoKey, videoKey });
      photoInput.value = "";
      videoInput.value = "";
      renderState();
    }

    function clearState() {
      if (state.busy) return;
      state.files.clear();
      state.pairs = [];
      photoInput.value = "";
      videoInput.value = "";
      renderState();
    }

    function closeDialog() {
      if (!state.busy) dialog.close();
    }

    function populateTargets() {
      const previous = targetSelect.value;
      const options = ['<option value="auto">Автоматически создать события по датам</option>'];
      (book.chapters || []).forEach((chapter, chapterIndex) => {
        (chapter.blocks || []).forEach((block, blockIndex) => {
          if (block.type !== "event") return;
          const count = (block.items || []).length;
          const chapterName = chapter.title || chapter.number || `Глава ${chapterIndex + 1}`;
          options.push(`<option value="${chapterIndex}:${blockIndex}">${escapeHtmlLocal(chapterName)} · ${escapeHtmlLocal(block.title || block.date || "Событие")} (${count})</option>`);
        });
      });
      targetSelect.innerHTML = options.join("");
      if ([...targetSelect.options].some((option) => option.value === previous)) targetSelect.value = previous;
    }

    function renderState() {
      const files = [...state.files.entries()];
      const pairKeys = new Set(state.pairs.flatMap((pair) => [pair.photoKey, pair.videoKey]));
      queue.innerHTML = files.length ? files.map(([key, file]) => `
        <article class="media-import-file">
          <span class="media-import-file__icon">${isVideo(file) ? "▶" : "▧"}</span>
          <div><strong>${escapeHtmlLocal(file.name)}</strong><small>${formatBytes(file.size)} · ${pairKeys.has(key) ? "явная Live Photo пара" : isVideo(file) ? "видео" : "фото"}</small></div>
          <button type="button" data-remove-file="${escapeAttrLocal(key)}" aria-label="Убрать файл">×</button>
        </article>`).join("") : '<div class="media-import-empty">Выбранные файлы появятся здесь.</div>';
      pairList.innerHTML = state.pairs.map((pair, index) => {
        const photo = state.files.get(pair.photoKey);
        const video = state.files.get(pair.videoKey);
        return `<article><span>LIVE ${index + 1}</span><div><strong>${escapeHtmlLocal(photo?.name || "Фото")}</strong><small>+</small><strong>${escapeHtmlLocal(video?.name || "Видео")}</strong></div><button type="button" data-remove-pair="${index}">Удалить пару</button></article>`;
      }).join("");
      const totalBytes = files.reduce((sum, [, file]) => sum + file.size, 0);
      summary.textContent = files.length
        ? `${files.length} ${plural(files.length, "файл", "файла", "файлов")} · ${formatBytes(totalBytes)} · явных Live Photo: ${state.pairs.length}`
        : "Файлы ещё не выбраны.";
      startButton.disabled = !files.length || state.busy;
      startButton.textContent = files.length ? `Импортировать ${files.length}` : "Импортировать";
    }

    async function startImport() {
      if (state.busy || !state.files.size) return;
      if (location.protocol === "file:") {
        alert("Импорт работает через локальный сервер. Запусти: python3 tools/memory_server.py");
        return;
      }
      state.busy = true;
      renderState();
      setControlsDisabled(true);
      progressBox.hidden = false;
      progress.value = 0;
      progress.max = state.files.size + 1;
      const batchId = `memory-${crypto.randomUUID().replace(/-/g, "")}`;
      const tokenByKey = new Map();
      let previewWindow = window.open("about:blank", "memory-import-preview");
      if (previewWindow) {
        previewWindow.document.title = "Импорт воспоминаний…";
        previewWindow.document.body.textContent = "Загружаю и обрабатываю новые файлы…";
      }

      try {
        const entries = [...state.files.entries()];
        for (let index = 0; index < entries.length; index += 1) {
          const [key, file] = entries[index];
          progressTitle.textContent = `Загружаю: ${file.name}`;
          progressCount.textContent = `${index + 1} / ${entries.length}`;
          const response = await fetch("/api/memory/import/upload", {
            method: "POST",
            headers: {
              "Content-Type": "application/octet-stream",
              "X-Memory-Batch": batchId,
              "X-Memory-Name": encodeURIComponent(file.name),
              "X-Memory-Modified": String(file.lastModified || 0),
            },
            body: file,
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok || !result.ok) throw new Error(result.error || `Не удалось загрузить ${file.name}`);
          tokenByKey.set(key, result.token);
          progress.value = index + 1;
        }

        progressTitle.textContent = "Определяю даты, пары Live Photo и создаю превью…";
        progressCount.textContent = "Обработка";
        const target = parseTarget(targetSelect.value);
        const pairs = state.pairs.map((pair) => ({
          photoToken: tokenByKey.get(pair.photoKey),
          videoToken: tokenByKey.get(pair.videoKey),
        }));
        const response = await fetch("/api/memory/import/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ batchId, book, pairs, target }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
        progress.value = progress.max;

        snapshot();
        book = result.book;
        normalizeBook();
        render();
        const liveCount = Number(result.explicitLivePairs || 0) + Number(result.autoLivePairs || 0);
        status.textContent = result.importedItems
          ? `Добавлено ${result.importedItems} ${plural(result.importedItems, "медиафайл", "медиафайла", "медиафайлов")}${liveCount ? `, Live Photo: ${liveCount}` : ""}. Backup: ${result.backup}.`
          : `Новых файлов не найдено: ${result.duplicates || 0} уже были в книге.`;

        const targetUrl = new URL(result.bookUrl || "../index.html?opened=1", location.href);
        targetUrl.searchParams.set("v", String(Date.now()));
        if (previewWindow && !previewWindow.closed) previewWindow.location.replace(targetUrl.href);
        else window.open(targetUrl.href, "_blank");
        clearStateAfterSuccess();
        dialog.close();
      } catch (error) {
        if (previewWindow && !previewWindow.closed) previewWindow.close();
        const serverHint = /404|endpoint|Failed to fetch|Load failed/i.test(String(error.message || ""))
          ? " Перезапусти сервер командой: python3 tools/memory_server.py"
          : "";
        status.textContent = `Импорт не выполнен: ${error.message}.${serverHint}`;
        alert(`Не удалось импортировать медиа: ${error.message}.${serverHint}`);
      } finally {
        state.busy = false;
        setControlsDisabled(false);
        progressBox.hidden = true;
        renderState();
      }
    }

    function parseTarget(value) {
      if (!value || value === "auto") return null;
      const [chapterIndex, blockIndex] = value.split(":").map(Number);
      return { chapterIndex, blockIndex };
    }

    function setControlsDisabled(disabled) {
      dialog.querySelectorAll("button, input, select").forEach((control) => {
        if (control === startButton) return;
        control.disabled = disabled;
      });
    }

    function clearStateAfterSuccess() {
      state.files.clear();
      state.pairs = [];
      photoInput.value = "";
      videoInput.value = "";
      renderState();
    }

    function formatBytes(value) {
      const units = ["Б", "КБ", "МБ", "ГБ", "ТБ"];
      let number = Number(value) || 0;
      let index = 0;
      while (number >= 1024 && index < units.length - 1) {
        number /= 1024;
        index += 1;
      }
      return `${number >= 10 || index === 0 ? number.toFixed(0) : number.toFixed(1)} ${units[index]}`;
    }

    function plural(number, one, few, many) {
      const mod10 = number % 10;
      const mod100 = number % 100;
      if (mod10 === 1 && mod100 !== 11) return one;
      if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) return few;
      return many;
    }

    function escapeHtmlLocal(value) {
      return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function escapeAttrLocal(value) {
      return escapeHtmlLocal(value).replace(/`/g, "&#096;");
    }

    const guide = document.querySelector(".button-guide dl");
    if (guide) {
      const row = document.createElement("div");
      row.innerHTML = "<dt>Добавить фото и видео</dt><dd>Пакетно импортирует новые оригиналы, явные Live Photo пары или добавляет всё в выбранное событие без пересборки книги.</dd>";
      guide.appendChild(row);
    }
  });
})();
