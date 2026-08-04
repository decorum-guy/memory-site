# Design Preview Status

- Commit: `3e5082737688135a11dab63fb78c857ef4a73bed`
- Run: https://github.com/decorum-guy/memory-site/actions/runs/30864167210
- Generated: 2026-08-04 00:03:36 UTC
- Result: **failure**

## Последние строки ошибки
```text
node:internal/modules/run_main:123
    triggerUncaughtException(
    ^

locator.scrollIntoViewIfNeeded: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('.image-frame.is-censored').first()

    at /home/runner/work/memory-site/memory-site/preview/capture.mjs:70:21 {
  name: 'TimeoutError'
}

Node.js v20.20.2
```
