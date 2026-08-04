// Опциональная глава. Обычно этот файл генерирует tools/telegram_server.py.
// Включается одной строкой в content/settings.js: telegramEnabled: true
window.TELEGRAM_MEDIA_MODES = {};
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "TG",
  kicker: "Слова, которые остались",
  title: "То, что осталось в переписке",
  subtitle: "Несколько наших фраз — и слова, которые я хочу оставить тебе рядом.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      telegramKind: "note",
      text: "Запусти python3 tools/telegram_server.py, добавь записки и цитаты сообщений, а затем нажми «Сохранить главу». Если времени не хватит — оставь telegramEnabled: false.",
      style: "torn",
      shape: 0,
      rotate: -1.2
    }
  ]
};
