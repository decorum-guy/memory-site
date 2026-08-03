window.MEMORY_BOOK = {
  meta: {
    eyebrow: "Личная книга воспоминаний",
    title: "Наши три года",
    subtitle: "Не идеальные. Настоящие.",
    note: "Демонстрационная версия дизайна: временные изображения нужны только для проверки композиции.",
    footer: "Спасибо за всё, что было между первой и последней страницей.",
    accent: "#9c3f43"
  },
  chapters: [
    {
      id: "beginning",
      number: "01",
      kicker: "С чего всё началось",
      title: "До того, как мы поняли, что это серьёзно",
      subtitle: "Первые встречи, немного неловкости и дни, которые позже стали началом общей истории.",
      layout: "story",
      theme: "rose",
      blocks: [
        {
          type: "note",
          text: "Я не помню точный момент, когда обычные сообщения стали чем-то большим. Но помню ощущение: рядом появился человек, которому хотелось рассказывать вообще всё.",
          style: "lined",
          rotate: -1.4
        },
        {
          type: "photo",
          src: "preview/demo-media/photo-01.jpg",
          thumb: "preview/demo-media/photo-01.jpg",
          alt: "Демонстрационная фотография первой прогулки",
          caption: "Тот вечер, после которого дорога домой ощущалась короче обычного.",
          date: "июль 2023",
          captionStyle: "scribble",
          rotate: 2.1,
          tape: "cream"
        },
        {
          type: "quote",
          text: "Ты дома? Напиши, когда доедешь.",
          author: "одно из первых сообщений",
          rotate: -1
        }
      ]
    },
    {
      id: "ordinary-days",
      number: "02",
      kicker: "Наша обычная жизнь",
      title: "События, которые не казались событиями",
      subtitle: "Именно такие дни обычно исчезают первыми — еда, дорога, смешные кадры и совершенно обычные вечера.",
      layout: "wide",
      theme: "ochre",
      blocks: [

        {
          type: "event",
          id: "demo-single",
          title: "Один тихий кадр",
          caption: "Проверка компактной высоты события с одним файлом.",
          layout: "collage",
          items: [
            { id: "single-01", kind: "photo", src: "preview/demo-media/photo-01.jpg", thumb: "preview/demo-media/photo-01.jpg", caption: "Один кадр тоже может быть целой страницей.", takenAt: "2023-10-02T20:14:00" }
          ]
        },
        {
          type: "event",
          id: "demo-day-one",
          title: "18 ноября 2023",
          caption: "Мы вышли ненадолго, а вернулись с десятком фотографий и историей про самый странный десерт в Москве.",
          layout: "collage",
          items: [
            { id: "d01", kind: "photo", src: "preview/demo-media/photo-02.jpg", thumb: "preview/demo-media/photo-02.jpg", caption: "Сначала просто кофе.", takenAt: "2023-11-18T16:21:00" },
            { id: "d02", kind: "photo", src: "preview/demo-media/photo-03.jpg", thumb: "preview/demo-media/photo-03.jpg", caption: "Потом мы решили идти пешком.", takenAt: "2023-11-18T16:44:00" },
            { id: "d03", kind: "photo", src: "preview/demo-media/photo-04.jpg", thumb: "preview/demo-media/photo-04.jpg", caption: "Кадр, который получился случайно.", takenAt: "2023-11-18T17:10:00" },
            { id: "d04", kind: "photo", src: "preview/demo-media/photo-05.jpg", thumb: "preview/demo-media/photo-05.jpg", caption: "Тот самый десерт.", takenAt: "2023-11-18T17:48:00", censored: true },
            { id: "d05", kind: "video", src: "preview/demo-media/demo-video.mp4", poster: "preview/demo-media/video-poster.jpg", caption: "Четыре секунды абсолютного хаоса.", duration: 4, takenAt: "2023-11-18T18:02:00" },
            { id: "d06", kind: "photo", src: "preview/demo-media/photo-06.jpg", thumb: "preview/demo-media/photo-06.jpg", caption: "И спокойный финал дня.", takenAt: "2023-11-18T19:17:00" }
          ]
        },
        {
          type: "caption",
          text: "Самые важные дни редко предупреждают, что станут важными.",
          style: "marker",
          rotate: -1
        }
      ]
    },
    {
      id: "journeys",
      number: "03",
      kicker: "Немного дальше от дома",
      title: "Поездки, в которых время шло иначе",
      subtitle: "Одно событие может хранить десятки кадров. На странице остаётся аккуратная стопка, а внутри — полноценная последовательность.",
      layout: "scrap",
      theme: "blue",
      blocks: [
        {
          type: "event",
          id: "demo-trip",
          title: "Май 2025 · три дня у воды",
          caption: "Слишком много ветра, слишком мало сна и ощущение, что возвращаться ещё рано.",
          layout: "collage",
          items: [
            { id: "t01", kind: "photo", src: "preview/demo-media/photo-07.jpg", thumb: "preview/demo-media/photo-07.jpg", caption: "Первый вечер.", takenAt: "2025-05-09T19:20:00" },
            { id: "t02", kind: "photo", src: "preview/demo-media/photo-08.jpg", thumb: "preview/demo-media/photo-08.jpg", caption: "Утро, когда мы всё-таки проснулись рано.", takenAt: "2025-05-10T08:14:00" },
            { id: "t03", kind: "photo", src: "preview/demo-media/photo-09.jpg", thumb: "preview/demo-media/photo-09.jpg", caption: "Город в середине дня.", takenAt: "2025-05-10T13:08:00" },
            { id: "t04", kind: "photo", src: "preview/demo-media/photo-10.jpg", thumb: "preview/demo-media/photo-10.jpg", caption: "Пять минут до дождя.", takenAt: "2025-05-10T16:31:00" },
            { id: "t05", kind: "live", src: "preview/demo-media/photo-11.jpg", thumb: "preview/demo-media/photo-11.jpg", liveVideo: "preview/demo-media/demo-live.mp4", caption: "Фото, которое можно оживить.", takenAt: "2025-05-10T18:20:00" },
            { id: "t06", kind: "photo", src: "preview/demo-media/photo-12.jpg", thumb: "preview/demo-media/photo-12.jpg", caption: "Последний вечер.", takenAt: "2025-05-11T20:02:00" },
            { id: "t07", kind: "photo", src: "preview/demo-media/photo-13.jpg", thumb: "preview/demo-media/photo-13.jpg", caption: "Перед дорогой домой.", takenAt: "2025-05-12T09:11:00" },
            { id: "t08", kind: "photo", src: "preview/demo-media/photo-14.jpg", thumb: "preview/demo-media/photo-14.jpg", caption: "Кадр из окна.", takenAt: "2025-05-12T10:03:00" }
          ]
        },
        {
          type: "sticker",
          text: "8 кадров внутри",
          icon: "↗",
          rotate: 5
        }
      ]
    },
    {
      id: "ending",
      number: "04",
      kicker: "Последняя страница",
      title: "Эта история закончилась не потому, что была неудачной",
      subtitle: "Финальная страница остаётся спокойной: без обещаний, просьб и попыток переписать принятое решение.",
      layout: "letter",
      theme: "ink",
      blocks: [
        {
          type: "letter",
          title: "Спасибо тебе",
          text: [
            "За три года, которые были настоящими.",
            "За всё, чему мы друг друга научили, и за обычные дни, которые рядом с тобой переставали быть обычными.",
            "Я не хочу превращать эту книгу в просьбу остаться. Я хочу, чтобы она напоминала: всё это действительно было — и было важным.",
            "Пусть дальше у тебя будет много нового, красивого и твоего."
          ],
          signature: "Артём"
        },
        {
          type: "photo",
          src: "preview/demo-media/photo-15.jpg",
          thumb: "preview/demo-media/photo-15.jpg",
          alt: "Демонстрационная финальная фотография",
          caption: "Не самая идеальная. Просто самая правильная.",
          captionStyle: "underlined",
          rotate: 1.5,
          tape: "rose"
        }
      ]
    }
  ]
};
