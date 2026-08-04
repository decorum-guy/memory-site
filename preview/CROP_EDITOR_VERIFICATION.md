# Crop editor verification

Chromium preview verifies the Studio crop and video-frame editor end to end:

- existing photo crop is rendered in the book;
- existing selected video frame and crop are rendered in the book;
- photo position changes after dragging and saving;
- cancelling the crop editor leaves the previous values untouched;
- video timeline cancel restores the committed frame time;
- video timeline save returns to crop positioning with the new frame;
- save and exit commits both poster time and crop;
- exported `memories.js` contains `crop` and `posterTime`;
- Live Photo opens the same crop editor without the regular-video timeline.

The CI fixture uses VP9/WebM because open-source Chromium on GitHub Actions does not bundle the proprietary H.264 decoder. Production MP4 files remain unchanged and are supported by Chrome, Yandex Browser and Safari.
