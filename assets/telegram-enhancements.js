(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const modes = window.TELEGRAM_MEDIA_MODES || {};
    document.querySelectorAll("#telegram .scrap-collage__item img").forEach((image) => {
      const source = image.getAttribute("src") || "";
      const mode = modes[source] || (source.toLowerCase().endsWith(".png") ? "cutout" : "paper");
      const card = image.closest(".scrap-collage__item");
      if (!card) return;
      card.classList.toggle("telegram-cutout", mode === "cutout");
      card.classList.toggle("telegram-paper", mode !== "cutout");
    });
  });
})();
