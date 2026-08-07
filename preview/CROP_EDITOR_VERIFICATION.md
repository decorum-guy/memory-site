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

A dedicated cursor-state test verifies the custom pencil end to end:

- its stylesheet is loaded by `index.html`;
- a desktop fine-pointer environment receives the basic pencil cursor on the book;
- interactive controls switch to the aligned hover pencil;
- pressing an interactive control switches to the aligned active pencil;
- all three states use the same `12 48` graphite-tip hotspot on a 64×64 canvas;
- all three SVG assets return HTTP 200 and contain data;
- the exact uploaded PNG versions remain embedded as fallbacks in CSS;
- text fields retain the native text cursor;
- Memory Studio intentionally keeps the system cursor for precise crop and timeline work.

The CI fixture uses VP9/WebM because open-source Chromium on GitHub Actions does not bundle the proprietary H.264 decoder. Production MP4 files remain unchanged and are supported by Chrome, Yandex Browser and Safari.
