#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected fragment not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


patch(
    "assets/app.js",
    '''  function restoreReaderChrome() {
    const update = () => {
      const cover = byId("cover");
      const threshold = cover ? Math.min(160, cover.offsetHeight * .12) : 80;
      if (window.scrollY > threshold || window.location.hash) document.body.classList.add("book-opened");
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("pageshow", () => requestAnimationFrame(update));
  }
''',
    '''  function restoreReaderChrome() {
    const params = new URLSearchParams(window.location.search);
    const forcedOpen = params.get("opened") === "1" || window.location.hash === "#memory-book";
    const update = () => {
      const cover = byId("cover");
      const threshold = cover ? Math.min(160, cover.offsetHeight * .12) : 80;
      if (forcedOpen || window.scrollY > threshold || window.location.hash) {
        document.body.classList.add("book-opened");
      }
    };
    update();
    [80, 250, 700, 1500].forEach((delay) => window.setTimeout(update, delay));
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("pageshow", () => requestAnimationFrame(update));
    window.addEventListener("hashchange", update);
  }
''',
)

patch(
    "tools/studio_workflow.py",
    '''def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        webbrowser.open(path.resolve().as_uri())
''',
    '''def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        webbrowser.open(path.resolve().as_uri())


def open_book(root: Path) -> None:
    url = (root / "index.html").resolve().as_uri() + "?opened=1#memory-book"
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        webbrowser.open(url)
''',
)

patch(
    "tools/studio_workflow.py",
    '''    if args.open:
        open_path(root / "index.html")
    else:
        print(f"Открыть книгу: open \\"{root / 'index.html'}\\"")
''',
    '''    if args.open:
        open_book(root)
    else:
        print(f"Открыть книгу: open \\"{root / 'index.html'}\\"")
''',
)

patch(
    "preview/capture.mjs",
    '''await chromeCheck.goto(`${base}/${previewQuery}`, { waitUntil: "networkidle" });
await chromeCheck.locator("#open-book").click();
await chromeCheck.locator("#ordinary-days").scrollIntoViewIfNeeded();
''',
    '''await chromeCheck.goto(`${base}/${previewQuery}&opened=1#memory-book`, { waitUntil: "networkidle" });
await chromeCheck.locator("#ordinary-days").scrollIntoViewIfNeeded();
''',
)
