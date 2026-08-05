# Design Preview Status

- Commit: `075b982d40756143f9adbc12d12eb235b36cda78`
- Run: https://github.com/decorum-guy/memory-site/actions/runs/31042394364
- Generated: 2026-08-05 20:08:07 UTC
- Result: **failure**

## Последние строки ошибки
```text
node:internal/modules/run_main:123
    triggerUncaughtException(
    ^

locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('details.chapter').nth(1).locator('.item').filter({ hasText: 'PHOTO' }).first().locator('[data-crop]')
    - locator resolved to <button data-crop="" type="button" class="crop-open">Настроить кадр</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not stable
    - retrying click action
    - waiting 20ms
    - waiting for element to be visible, enabled and stable
    - element is not stable
  - retrying click action
    - waiting 100ms
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <a href="telegram_studio.html">Telegram Studio</a> from <header class="top">…</header> subtree intercepts pointer events
  - retrying click action
    - waiting 100ms
    - waiting for element to be visible, enabled and stable
    - element is not stable
  14 × retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div class="item-preview">…</div> intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div class="item-preview">…</div> intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <a href="telegram_studio.html">Telegram Studio</a> from <header class="top">…</header> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <a href="telegram_studio.html">Telegram Studio</a> from <header class="top">…</header> subtree intercepts pointer events
  - retrying click action
    - waiting 500ms
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <div class="item-preview">…</div> intercepts pointer events
  - retrying click action
    - waiting 500ms

    at /home/runner/work/memory-site/memory-site/preview/capture.mjs:261:45 {
  name: 'TimeoutError'
}

Node.js v20.20.2
```
