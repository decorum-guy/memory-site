// Опциональная глава. Включается одной строкой в content/settings.js:
// telegramEnabled: true
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "TG",
  kicker: "Несколько сообщений",
  title: "То, что осталось в переписке",
  subtitle: "Не полный архив чата — только несколько фраз и скриншотов, которые сами стали воспоминаниями.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      text: "Эта глава специально сделана короткой. Если сил на неё не хватит — оставь telegramEnabled: false, и она вообще не появится в книге.",
      style: "torn",
      rotate: -1.4
    },
    {
      type: "collage",
      title: "Сообщения, которые хочется перечитать",
      caption: "Положи скриншоты в media/telegram и замени подписи ниже.",
      photos: [
        { src: "media/telegram/chat-01.jpg", alt: "Скриншот переписки", caption: "Подпись к первому фрагменту переписки." },
        { src: "media/telegram/chat-02.jpg", alt: "Скриншот переписки", caption: "Подпись ко второму фрагменту переписки." },
        { src: "media/telegram/chat-03.jpg", alt: "Скриншот переписки", caption: "Подпись к третьему фрагменту переписки." },
        { src: "media/telegram/chat-04.jpg", alt: "Скриншот переписки", caption: "Подпись к четвёртому фрагменту переписки." }
      ]
    },
    {
      type: "quote",
      text: "Здесь может быть одна короткая фраза из переписки, которую вы оба узнаете без объяснений.",
      author: "из Telegram",
      rotate: 1.2
    }
  ]
};
