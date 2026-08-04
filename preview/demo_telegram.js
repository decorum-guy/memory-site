window.TELEGRAM_MEDIA_MODES = {
  "media/telegram/chat-cutout-01.png": "cutout",
  "media/telegram/chat-02.jpg": "paper"
};
window.TELEGRAM_CHAPTER = {
  id: "telegram",
  number: "TG",
  kicker: "Слова, которые остались",
  title: "То, что осталось в переписке",
  subtitle: "Записки и несколько сообщений, которые сами стали частью истории.",
  layout: "wide",
  theme: "blue",
  blocks: [
    {
      type: "note",
      telegramKind: "note",
      text: "Это место не обязано быть архивом всего чата. Здесь можно оставить несколько слов, которые хочется сказать спокойно и без спешки.",
      style: "torn",
      shape: 1,
      rotate: 0.75
    },
    {
      type: "quote",
      telegramKind: "message",
      text: "Ты опять сохранил эту фотографию?",
      author: "Соня",
      speaker: "sonya",
      screenshot: "media/telegram/chat-cutout-01.png",
      screenshotAlt: "Демонстрационный скриншот сообщения Сони",
      screenshotMode: "cutout",
      shape: 2,
      rotate: -0.45
    },
    {
      type: "quote",
      telegramKind: "message",
      text: "Конечно. Я же знал, что однажды соберу из этого целую книгу.",
      author: "Артём",
      speaker: "me",
      screenshot: "",
      screenshotAlt: "",
      screenshotMode: "paper",
      shape: 3,
      rotate: 1.05
    },
    {
      type: "quote",
      telegramKind: "message",
      text: "Тогда пусть здесь останется и эта фраза.",
      author: "Соня",
      speaker: "sonya",
      screenshot: "media/telegram/chat-02.jpg",
      screenshotAlt: "Демонстрационный скриншот сообщения Сони",
      screenshotMode: "paper",
      shape: 4,
      rotate: -0.8
    },
    {
      type: "note",
      telegramKind: "note",
      text: "А в конце главы можно оставить ещё одно напутствие — уже не как сообщение из прошлого, а как слова от тебя сейчас.",
      style: "torn",
      shape: 4,
      rotate: -0.8
    }
  ]
};
