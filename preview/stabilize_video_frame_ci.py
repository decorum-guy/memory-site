from pathlib import Path
import re

DETERMINISTIC_WAIT = '''await {locator}.evaluate(async (video, expected) => {{
  const sourceUrl = video.currentSrc || video.getAttribute("src") || video.src;
  const configuredTime = Number(video.dataset.posterTime);
  if (!sourceUrl) throw new Error("Selected-frame video has no source URL");
  if (!Number.isFinite(configuredTime) || Math.abs(configuredTime - expected) > 0.001) {{
    throw new Error(`Runtime did not preserve posterTime: ${{video.dataset.posterTime}}`);
  }}

  const waitUntil = async (predicate, timeout, message) => {{
    const deadline = performance.now() + timeout;
    while (!predicate()) {{
      if (performance.now() >= deadline) throw new Error(message());
      await new Promise((resolve) => window.setTimeout(resolve, 80));
    }}
  }};

  let usedBlobFallback = false;
  let responseStatus = null;
  let sourceBytes = null;

  try {{
    await waitUntil(
      () => video.readyState >= 2 && Math.abs(video.currentTime - expected) <= 0.35,
      3000,
      () => "runtime preview frame was not decoded within the grace period"
    );
  }} catch {{
    const response = await fetch(sourceUrl, {{ cache: "no-store" }});
    responseStatus = response.status;
    if (!response.ok) {{
      throw new Error(`Selected-frame source request failed: ${{response.status}} ${{sourceUrl}}`);
    }}
    const blob = await response.blob();
    sourceBytes = blob.size;
    if (!blob.size) throw new Error(`Selected-frame source is empty: ${{sourceUrl}}`);

    const objectUrl = URL.createObjectURL(blob);
    usedBlobFallback = true;
    video.muted = true;
    video.preload = "auto";
    video.src = objectUrl;

    await new Promise((resolve, reject) => {{
      const timer = window.setTimeout(
        () => reject(new Error(`Timed out loading fetched video metadata: ${{sourceUrl}}`)),
        10000
      );
      const done = () => {{
        window.clearTimeout(timer);
        resolve();
      }};
      const fail = () => {{
        window.clearTimeout(timer);
        reject(new Error(`Fetched video could not be decoded: ${{sourceUrl}}`));
      }};
      video.addEventListener("loadedmetadata", done, {{ once: true }});
      video.addEventListener("error", fail, {{ once: true }});
      try {{ video.load(); }} catch (error) {{ fail(error); }}
    }});

    try {{ await video.play(); }} catch {{}}
    try {{ video.currentTime = expected; }} catch (error) {{
      throw new Error(`Could not seek fetched video: ${{error?.message || error}}`);
    }}
    await waitUntil(
      () => video.readyState >= 2 && Math.abs(video.currentTime - expected) <= 0.35,
      10000,
      () => `Timed out decoding fetched selected frame ${{expected}}; current=${{video.currentTime}}; readyState=${{video.readyState}}`
    );
  }}

  video.pause();
  if (video.readyState < 2 || Math.abs(video.currentTime - expected) > 0.35) {{
    throw new Error(`Selected frame mismatch after verification: current=${{video.currentTime}}; readyState=${{video.readyState}}`);
  }}
  video.dataset.verificationSourceUrl = sourceUrl;
  video.dataset.verificationBlobFallback = String(usedBlobFallback);
  if (responseStatus !== null) video.dataset.verificationResponseStatus = String(responseStatus);
  if (sourceBytes !== null) video.dataset.verificationSourceBytes = String(sourceBytes);
}}, 1.2);'''


def replace_wait(path: Path, locator: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"await {re.escape(locator)}\.evaluate\((?:async )?\(video, expected\) => .*?\n\s*\}}, 1\.2\);|"
        rf"await {re.escape(locator)}\.evaluate\(\(video, expected\) => new Promise\(\(resolve, reject\) => \{{.*?\n\s*\}}\), 1\.2\);",
        re.DOTALL,
    )
    replacement = DETERMINISTIC_WAIT.format(locator=locator)
    updated, count = pattern.subn(replacement, text, count=1)
    if count == 0:
        if "verificationBlobFallback" in text:
            return
        raise SystemExit(f"selected-frame block not found in {path}")
    path.write_text(updated, encoding="utf-8")


def add_diagnostics(path: Path, locator: str) -> None:
    text = path.read_text(encoding="utf-8")
    if locator == "selectedVideo":
        old = '''  const readerVideoState = await selectedVideo.evaluate((video) => ({
    currentTime: video.currentTime,
    objectPosition: getComputedStyle(video).objectPosition,
    paused: video.paused,
  }));'''
        new = '''  const readerVideoState = await selectedVideo.evaluate((video) => ({
    currentTime: video.currentTime,
    objectPosition: getComputedStyle(video).objectPosition,
    paused: video.paused,
    sourceUrl: video.dataset.verificationSourceUrl || video.currentSrc || video.src,
    usedBlobFallback: video.dataset.verificationBlobFallback === "true",
    responseStatus: Number(video.dataset.verificationResponseStatus || 0) || null,
    sourceBytes: Number(video.dataset.verificationSourceBytes || 0) || null,
  }));'''
    else:
        old = '''const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
  currentTime: video.currentTime,
  objectPosition: getComputedStyle(video).objectPosition,
  paused: video.paused
}));'''
        new = '''const selectedVideoState = await selectedVideoPreview.evaluate((video) => ({
  currentTime: video.currentTime,
  objectPosition: getComputedStyle(video).objectPosition,
  paused: video.paused,
  sourceUrl: video.dataset.verificationSourceUrl || video.currentSrc || video.src,
  usedBlobFallback: video.dataset.verificationBlobFallback === "true",
  responseStatus: Number(video.dataset.verificationResponseStatus || 0) || null,
  sourceBytes: Number(video.dataset.verificationSourceBytes || 0) || null
}));'''
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")


verify = Path("preview/verify_crop_editor.mjs")
capture = Path("preview/capture.mjs")
replace_wait(verify, "selectedVideo")
replace_wait(capture, "selectedVideoPreview")
add_diagnostics(verify, "selectedVideo")
add_diagnostics(capture, "selectedVideoPreview")
print("Selected-frame verification now validates HTTP source and uses a Blob decode fallback")
