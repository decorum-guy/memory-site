#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected fragment not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "assets/app.js",
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
    '''  function seekPreviewVideo(video, time) {
    const requested = Math.max(0, Number(time) || 0);
    let settled = false;
    let attempts = 0;
    let retryTimer = 0;

    const safeTime = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : Infinity;
      return duration === Infinity ? requested : Math.min(requested, Math.max(0, duration - .01));
    };

    const schedule = (delay = 120) => {
      if (settled || attempts >= 18) return;
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(renderSelectedFrame, delay);
    };

    const finishWhenDecoded = () => {
      if (settled) return;
      const safe = safeTime();
      if (video.readyState < 2 || Math.abs(video.currentTime - safe) > .08) {
        schedule(100);
        return;
      }
      const finish = () => {
        if (settled || Math.abs(video.currentTime - safe) > .12) {
          schedule(80);
          return;
        }
        settled = true;
        window.clearTimeout(retryTimer);
        video.pause();
        video.removeAttribute("poster");
        video.dataset.frameReady = "1";
      };
      if (typeof video.requestVideoFrameCallback === "function") {
        video.requestVideoFrameCallback(finish);
      } else {
        requestAnimationFrame(finish);
      }
    };

    function renderSelectedFrame() {
      if (settled) return;
      attempts += 1;
      if (!video.isConnected || video.readyState < 1) {
        if (video.readyState === 0) video.load();
        schedule(Math.min(500, 60 * attempts));
        return;
      }
      const safe = safeTime();
      try {
        if (typeof video.fastSeek === "function") video.fastSeek(safe);
        else video.currentTime = safe;
      } catch (_) {
        schedule(Math.min(500, 70 * attempts));
        return;
      }
      const playback = video.play();
      if (playback && typeof playback.then === "function") {
        playback.then(() => {
          if (Math.abs(video.currentTime - safe) > .08) {
            try { video.currentTime = safe; }
            catch (_) { /* next scheduled attempt will retry */ }
          }
          finishWhenDecoded();
        }).catch(() => finishWhenDecoded());
      } else {
        finishWhenDecoded();
      }
      schedule(Math.min(600, 100 + attempts * 45));
    }

    ["loadedmetadata", "loadeddata", "canplay", "durationchange", "progress", "seeked"].forEach((name) => {
      video.addEventListener(name, () => {
        if (name === "seeked") finishWhenDecoded();
        else renderSelectedFrame();
      });
    });
    requestAnimationFrame(renderSelectedFrame);
  }
''',
)
