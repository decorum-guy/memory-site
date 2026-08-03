window.TELEGRAM_MEDIA_MODES = {
  "media/telegram/chat-cutout-01.png": "cutout",
  "media/telegram/chat-cutout-02.png": "cutout"
};
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "TG",
  kicker: "Несколько сообщений",
  title: "То, что осталось в переписке",
  subtitle: "Демонстрация большой Telegram-главы: обычные скриншоты, прозрачные вырезки и несколько scrapbook-разворотов.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      text: "Это временный набор для проверки дизайна. В финальной книге здесь будут только выбранные Артёмом фрагменты.",
      style: "torn",
      rotate: -1.2
    },
    {
      type: "collage",
      title: "Фрагменты переписки",
      caption: "Обычные прямоугольные скриншоты и прозрачные PNG могут жить на одном развороте.",
      photos: [
        { src: "media/telegram/chat-01.jpg", alt: "Демо Telegram", caption: "Первый фрагмент." },
        { src: "media/telegram/chat-cutout-01.png", alt: "Демо PNG-вырезка", caption: "Прозрачная вырезка без белого фона." },
        { src: "media/telegram/chat-02.jpg", alt: "Демо Telegram", caption: "Второй фрагмент." },
        { src: "media/telegram/chat-03.jpg", alt: "Демо Telegram", caption: "Третий фрагмент." },
        { src: "media/telegram/chat-cutout-02.png", alt: "Демо PNG-вырезка", caption: "Ещё одна нестандартная форма." },
        { src: "media/telegram/chat-04.jpg", alt: "Демо Telegram", caption: "Четвёртый фрагмент." },
        { src: "media/telegram/chat-05.jpg", alt: "Демо Telegram", caption: "Пятый фрагмент." }
      ]
    },
    {
      type: "collage",
      title: "Ещё несколько фрагментов · 2",
      caption: "Большой импорт автоматически разбивается на дополнительные развороты.",
      photos: [
        { src: "media/telegram/chat-06.jpg", alt: "Демо Telegram", caption: "Шестой фрагмент." },
        { src: "media/telegram/chat-07.jpg", alt: "Демо Telegram", caption: "Седьмой фрагмент." },
        { src: "media/telegram/chat-08.jpg", alt: "Демо Telegram", caption: "Восьмой фрагмент." },
        { src: "media/telegram/chat-09.jpg", alt: "Демо Telegram", caption: "Девятый фрагмент." },
        { src: "media/telegram/chat-10.jpg", alt: "Демо Telegram", caption: "Десятый фрагмент." }
      ]
    },
    {
      type: "quote",
      text: "Здесь может остаться одна фраза, которую не нужно объяснять никому кроме вас.",
      author: "из Telegram",
      rotate: 1.1
    }
  ]
};
