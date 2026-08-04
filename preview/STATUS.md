# Design Preview Status

- Commit: `8856f245dd4178886fef96aa3810b760811f926c`
- Run: https://github.com/decorum-guy/memory-site/actions/runs/30869233784
- Generated: 2026-08-04 01:40:02 UTC
- Result: **failure**

## Последние строки ошибки
```text
node:internal/modules/run_main:123
    triggerUncaughtException(
    ^

page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
    - disabled all CSS animations
  - waiting for fonts to load...

    at shot (/home/runner/work/memory-site/memory-site/preview/capture.mjs:30:14)
    at /home/runner/work/memory-site/memory-site/preview/capture.mjs:125:7 {
  name: 'TimeoutError'
}

Node.js v20.20.2
```
