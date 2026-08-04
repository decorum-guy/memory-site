#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected fragment not found in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "assets/app.js",
    '''    if (useSelectedVideoFrame) {
      media.muted = true;
      media.playsInline = true;
      media.preload = "metadata";
      media.poster = item.poster || "";
      media.src = item.src || "";
      seekPreviewVideo(media, item.posterTime);
    } else {
''',
    '''    if (useSelectedVideoFrame) {
      media.muted = true;
      media.playsInline = true;
      media.preload = "auto";
      media.poster = item.poster || "";
      media.src = item.src || "";
      media.dataset.posterTime = String(item.posterTime);
    } else {
''',
)

replace_once(
    "assets/app.js",
    '''    frame.append(media, placeholder);

    if (item.kind === "live") {
''',
    '''    frame.append(media, placeholder);
    if (useSelectedVideoFrame) seekPreviewVideo(media, item.posterTime);

    if (item.kind === "live") {
''',
)

replace_once(
    "assets/app.js",
    '''  function seekPreviewVideo(video, time) {
    const seek = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : Infinity;
      const requested = Math.max(0, Number(time) || 0);
      const safe = duration === Infinity ? requested : Math.min(requested, Math.max(0, duration - .01));
      try { video.currentTime = safe; }
      catch (_) { /* metadata may arrive on the next tick */ }
    };
    if (video.readyState >= 1) seek();
    else video.addEventListener("loadedmetadata", seek, { once: true });
  }
''',
    '''  function seekPreviewVideo(video, time) {
    const requested = Math.max(0, Number(time) || 0);
    let attempts = 0;
    const seek = () => {
      if (!video.isConnected && attempts < 8) {
        attempts += 1;
        window.setTimeout(seek, 40 * attempts);
        return;
      }
      const duration = Number.isFinite(video.duration) ? video.duration : Infinity;
      const safe = duration === Infinity ? requested : Math.min(requested, Math.max(0, duration - .01));
      try {
        if (Math.abs(video.currentTime - safe) > .03) video.currentTime = safe;
        video.pause();
      } catch (_) {
        if (attempts < 8) {
          attempts += 1;
          window.setTimeout(seek, 60 * attempts);
        }
      }
    };
    ["loadedmetadata", "loadeddata", "canplay"].forEach((name) => video.addEventListener(name, seek));
    video.addEventListener("seeked", () => {
      video.pause();
      video.dataset.frameReady = "1";
    });
    requestAnimationFrame(seek);
  }
''',
)

replace_once(
    "preview/capture.mjs",
    '''await selectedVideoPreview.evaluate((video) => new Promise((resolve) => {
  if (video.readyState >= 2) resolve();
  else {
    video.addEventListener("loadeddata", resolve, { once: true });
    window.setTimeout(resolve, 3000);
  }
}));
const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
''',
    '''await selectedVideoPreview.evaluate((video, expected) => new Promise((resolve, reject) => {
  const deadline = performance.now() + 6000;
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
}), 1.2);
const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
''',
)
