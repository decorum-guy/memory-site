// Опциональная глава. Обычно этот файл генерирует tools/memory_server.py.
// Включается одной строкой в content/settings.js: telegramEnabled: true
window.TELEGRAM_MEDIA_MODES = {};
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "FY",
  kicker: "Несколько слов для тебя",
  title: "For You",
  subtitle: "Пожелания, которые я хочу оставить тебе рядом.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      telegramKind: "note",
      text: "Открой For You Studio, добавь пожелания и нажми «Сохранить главу».",
      style: "torn",
      shape: 0,
      rotate: -1.2,
      layout: "auto"
    }
  ]
};
