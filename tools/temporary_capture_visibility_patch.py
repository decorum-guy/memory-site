#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "preview/capture.mjs"
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'const browser = await chromium.launch({ headless: true });',
        'const browser = await chromium.launch({ headless: true, args: ["--autoplay-policy=no-user-gesture-required"] });',
    ),
    (
        '''const selectedVideoPreview = desktop.locator('[data-media-key="d05"] video').first();
await selectedVideoPreview.waitFor({ state: "attached" });
await selectedVideoPreview.evaluate((video, expected) => new Promise((resolve, reject) => {
  const deadline = performance.now() + 6000;
''',
        '''const selectedVideoPreview = desktop.locator('[data-media-key="d05"] video').first();
await selectedVideoPreview.waitFor({ state: "attached" });
await selectedVideoPreview.scrollIntoViewIfNeeded();
await desktop.waitForTimeout(250);
await selectedVideoPreview.evaluate((video, expected) => new Promise((resolve, reject) => {
  const deadline = performance.now() + 12000;
''',
    ),
]

for old, new in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"Expected capture fragment not found: {old[:100]!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
