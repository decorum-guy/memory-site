# Design Preview Status

- Commit: `c2c76a2790656966283773b04c1457fb22e4d2bd`
- Run: https://github.com/decorum-guy/memory-site/actions/runs/30885950398
- Generated: 2026-08-04 07:05:05 UTC
- Result: **failure**

## Последние строки ошибки
```text
node:internal/modules/run_main:123
    triggerUncaughtException(
    ^

locator.scrollIntoViewIfNeeded: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('#telegram .memory-block--collage').first()

    at /home/runner/work/memory-site/memory-site/preview/capture.mjs:234:22 {
  name: 'TimeoutError'
}

Node.js v20.20.2
```
