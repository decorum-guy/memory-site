# Design Preview Status

- Commit: `c1ef2cbfece7a4bab40866a7dc57f7cfdb782b8f`
- Run: https://github.com/decorum-guy/memory-site/actions/runs/30885972616
- Generated: 2026-08-04 07:01:58 UTC
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
