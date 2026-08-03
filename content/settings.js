// Главные переключатели проекта. Этот файл можно менять вручную без правки memories.js.
window.MEMORY_SETTINGS = {
  // Готовая глава со скриншотами Telegram. По умолчанию выключена.
  telegramEnabled: false,

  // Shared Album открывается только при наличии интернета. QR хранится локально на флешке.
  sharedAlbumEnabled: false,
  sharedAlbumUrl: "",
  sharedAlbumQr: "media/shared-album-qr.png",
  sharedAlbumTitle: "Все фотографии и видео — ещё и в Shared Album",
  sharedAlbumText: "На случай, если удобнее листать всё в обычной галерее или сохранить себе оригиналы.",

  // При каждом новом открытии браузера цензура снова включена.
  censorshipEnabledByDefault: true,

  // Показывать компактную панель читателя после открытия книги.
  readerControlsEnabled: true
};
