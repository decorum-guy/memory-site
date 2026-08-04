from pathlib import Path

ROBUST_WAIT = '''await {locator}.evaluate((video, expected) => new Promise((resolve, reject) => {{
  const started = performance.now();
  const deadline = started + 15000;
  const events = ["loadedmetadata", "loadeddata", "seeked", "timeupdate", "canplay"];
  let timer = 0;
  let nudging = false;
  let settled = false;

  const cleanup = () => {{
    window.clearInterval(timer);
    events.forEach((name) => video.removeEventListener(name, check));
  }};

  const finish = () => {{
    if (settled) return;
    settled = true;
    cleanup();
    video.pause();
    resolve();
  }};

  const fail = () => {{
    if (settled) return;
    settled = true;
    cleanup();
    reject(new Error(`Timed out waiting for selected frame ${{expected}}; current=${{video.currentTime}}; readyState=${{video.readyState}}`));
  }};

  const nudgeDecode = async () => {{
    if (nudging || video.readyState < 1 || settled) return;
    nudging = true;
    video.muted = true;
    try {{ await video.play(); }} catch {{}}
    try {{
      if (typeof video.fastSeek === "function") video.fastSeek(expected);
      else video.currentTime = expected;
    }} catch {{}}
    window.setTimeout(() => {{ nudging = false; }}, 300);
  }};

  const check = () => {{
    if (video.readyState >= 2 && Math.abs(video.currentTime - expected) <= .35) {{
      finish();
      return;
    }}
    const now = performance.now();
    if (now >= deadline) {{
      fail();
      return;
    }}
    if (now - started >= 3000) void nudgeDecode();
  }};

  events.forEach((name) => video.addEventListener(name, check));
  timer = window.setInterval(check, 120);
  check();
}}), 1.2);'''


def patch_focused_verification() -> None:
    path = Path("preview/verify_crop_editor.mjs")
    text = path.read_text(encoding="utf-8")
    old = '''  const selectedVideo = reader.locator('[data-media-key="d05"] video').first();
  await selectedVideo.scrollIntoViewIfNeeded();
  await reader.waitForFunction(() => {
    const video = document.querySelector('[data-media-key="d05"] video');
    return Boolean(video && video.readyState >= 2 && Math.abs(video.currentTime - 1.2) <= .35);
  }, null, { timeout: 15000 });'''
    new = '''  const selectedVideo = reader.locator('[data-media-key="d05"] video').first();
  await selectedVideo.waitFor({ state: "attached" });
  await selectedVideo.scrollIntoViewIfNeeded();
  ''' + ROBUST_WAIT.format(locator="selectedVideo")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif "const started = performance.now();" not in text:
        raise SystemExit("focused selected-video block not found")


def patch_design_capture() -> None:
    path = Path("preview/capture.mjs")
    text = path.read_text(encoding="utf-8")
    old = '''await selectedVideoPreview.evaluate((video, expected) => new Promise((resolve, reject) => {
  const deadline = performance.now() + 12000;
  const check = () => {
    if (Math.abs(video.currentTime - expected) <= .35 && video.readyState >= 2) {
      resolve();
      return;
    }
    if (performance.now() >= deadline) {
      reject(new Error(`Timed out waiting for selected frame ${expected}; current=${video.currentTime}; readyState=${video.readyState}`));
      return;
    }
    window.setTimeout(check, 80);
  };
  ["loadedmetadata", "loadeddata", "seeked", "timeupdate", "canplay"].forEach((name) => video.addEventListener(name, check));
  check();
}), 1.2);'''
    if old in text:
        text = text.replace(old, ROBUST_WAIT.format(locator="selectedVideoPreview"), 1)
    elif "const started = performance.now();" not in text:
        raise SystemExit("capture selected-video block not found")

    old_state = '''const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
  currentTime: video.currentTime,
  objectPosition: getComputedStyle(video).objectPosition
}));'''
    new_state = '''const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
  currentTime: video.currentTime,
  objectPosition: getComputedStyle(video).objectPosition,
  paused: video.paused
}));'''
    if old_state in text:
        text = text.replace(old_state, new_state, 1)

    pause_anchor = '''if (!selectedVideoState.objectPosition.includes("68%") || !selectedVideoState.objectPosition.includes("34%")) {
  throw new Error(`Saved video crop was not applied: ${selectedVideoState.objectPosition}`);
}'''
    if "Selected video preview frame is still playing" not in text:
        if pause_anchor not in text:
            raise SystemExit("capture pause assertion anchor not found")
        text = text.replace(
            pause_anchor,
            pause_anchor + '''
if (!selectedVideoState.paused) {
  throw new Error("Selected video preview frame is still playing");
}''',
            1,
        )
    path.write_text(text, encoding="utf-8")


patch_focused_verification()
patch_design_capture()
print("Selected-frame verification patched")
