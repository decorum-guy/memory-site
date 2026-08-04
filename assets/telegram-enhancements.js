(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const chapter = window.TELEGRAM_CHAPTER;
    const root = document.getElementById("telegram");
    if (!root || !chapter || !Array.isArray(chapter.blocks)) return;

    const rendered = [...root.querySelectorAll(".chapter-content > .memory-block")];
    chapter.blocks.forEach((block, index) => {
      const element = rendered[index];
      if (!element) return;

      if (block.telegramKind === "note") {
        element.classList.add("telegram-note", `telegram-note--shape-${Number(block.shape || 0) % 5}`);
        return;
      }

      if (block.telegramKind !== "message") return;
      const speaker = block.speaker === "sonya" ? "sonya" : "me";
      element.classList.add("telegram-message", `telegram-message--${speaker}`);

      const quote = element.querySelector(".memory-quote");
      if (!quote) return;
      quote.classList.add("telegram-message__quote", `telegram-message__quote--${speaker}`);

      const screenshot = String(block.screenshot || "").trim();
      if (!screenshot) return;

      const layout = document.createElement("div");
      layout.className = "telegram-message__layout";
      quote.before(layout);
      layout.appendChild(quote);

      const button = document.createElement("button");
      button.type = "button";
      button.className = `telegram-message__shot telegram-message__shot--${block.screenshotMode === "cutout" ? "cutout" : "paper"}`;
      button.setAttribute("aria-label", `Открыть скриншот сообщения: ${block.author || ""}`.trim());

      const image = document.createElement("img");
      image.src = screenshot;
      image.alt = block.screenshotAlt || "Скриншот сообщения из Telegram";
      image.loading = "lazy";
      image.decoding = "async";
      button.appendChild(image);
      button.addEventListener("click", () => openScreenshot(screenshot, image.alt));
      layout.appendChild(button);
    });

    function openScreenshot(src, alt) {
      const modal = ensureModal();
      const image = modal.querySelector("img");
      image.src = src;
      image.alt = alt;
      modal.hidden = false;
      document.body.classList.add("telegram-shot-open");
      modal.querySelector("button").focus();
    }

    function ensureModal() {
      let modal = document.getElementById("telegram-shot-modal");
      if (modal) return modal;
      modal = document.createElement("div");
      modal.id = "telegram-shot-modal";
      modal.className = "telegram-shot-modal";
      modal.hidden = true;
      modal.innerHTML = `
        <button type="button" aria-label="Закрыть скриншот">×</button>
        <img alt="" />
      `;
      const close = () => {
        modal.hidden = true;
        modal.querySelector("img").removeAttribute("src");
        document.body.classList.remove("telegram-shot-open");
      };
      modal.querySelector("button").addEventListener("click", close);
      modal.addEventListener("click", (event) => {
        if (event.target === modal) close();
      });
      document.addEventListener("keydown", (event) => {
        if (!modal.hidden && event.key === "Escape") close();
      });
      document.body.appendChild(modal);
      return modal;
    }
  });
})();
