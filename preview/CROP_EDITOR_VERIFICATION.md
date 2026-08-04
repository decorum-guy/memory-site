# Crop editor and cursor verification

Focused Chromium verification exercises the Studio crop and video-frame editor end to end:

- existing photo crop is rendered in the book;
- existing selected video frame and crop are rendered in the book;
- photo position changes after dragging and saving;
- cancelling the crop editor leaves the previous values untouched;
- video timeline cancel restores the committed frame time;
- video timeline save returns to crop positioning with the new frame;
- save and exit commits both poster time and crop;
- exported `memories.js` contains `crop` and `posterTime`;
- Live Photo opens the same crop editor without the regular-video timeline.

The same test verifies the custom pencil cursor:

- its stylesheet is loaded by `index.html`;
- a desktop fine-pointer environment receives the cursor on the book and interactive controls;
- the cursor URL resolves to `scrapbook-pencil-final-v19.svg` with PNG fallback;
- Memory Studio intentionally keeps the system cursor.

The CI fixture uses VP9/WebM because open-source Chromium on GitHub Actions does not bundle the proprietary H.264 decoder. Production MP4 files remain unchanged and are supported by Chrome, Yandex Browser and Safari.
