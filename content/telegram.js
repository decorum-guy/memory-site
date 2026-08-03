// Опциональная глава. Обычно этот файл генерирует tools/telegram_server.py.
// Включается одной строкой в content/settings.js: telegramEnabled: true
window.TELEGRAM_MEDIA_MODES = {};
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "TG",
  kicker: "Несколько сообщений",
  title: "То, что осталось в переписке",
  subtitle: "Не полный архив чата — только фрагменты, которые сами стали воспоминаниями.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      text: "Запусти python3 tools/telegram_server.py, перетащи подготовленные скриншоты и нажми «Сохранить главу». Если времени не хватит — оставь telegramEnabled: false, и эта страница не появится.",
      style: "torn",
      rotate: -1.4
    }
  ]
};
