#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected fragment not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


patch(
    "tools/studio.html",
    'const history=[],expandedItems=new Set(),workspace=document.getElementById("workspace"),status=document.getElementById("status"),dialog=document.getElementById("new-event-dialog");',
    'const history=[],expandedItems=new Set(),openChapters=new Set([book.chapters?.[0]?.id].filter(Boolean)),workspace=document.getElementById("workspace"),status=document.getElementById("status"),dialog=document.getElementById("new-event-dialog");',
)

patch(
    "tools/studio.html",
    'details.className="chapter";details.open=chapterIndex===0;const events=chapter.blocks.filter(b=>b.type==="event");',
    'details.className="chapter";details.open=openChapters.has(chapter.id)||(chapterIndex===0&&openChapters.size===0);const events=chapter.blocks.filter(b=>b.type==="event");',
)

patch(
    "tools/studio.html",
    'details.innerHTML=`<summary>${escapeHtml(chapter.title||`Глава ${chapterIndex+1}`)}<small>${events.length} событий</small></summary><div class="chapter-tools"><button data-add>＋ Добавить событие</button></div><div class="events"></div>`;details.querySelector("[data-add]").onclick=',
    'details.innerHTML=`<summary>${escapeHtml(chapter.title||`Глава ${chapterIndex+1}`)}<small>${events.length} событий</small></summary><div class="chapter-tools"><button data-add>＋ Добавить событие</button></div><div class="events"></div>`;details.addEventListener("toggle",()=>{details.open?openChapters.add(chapter.id):openChapters.delete(chapter.id)});details.querySelector("[data-add]").onclick=',
)

patch(
    "tools/studio.html",
    'card.querySelector("[data-expand]").onclick=()=>{expandedItems.has(item.id)?expandedItems.delete(item.id):expandedItems.add(item.id);render()};',
    'const expandButton=card.querySelector("[data-expand]");expandButton.onclick=()=>{const expanded=!expandedItems.has(item.id);expanded?expandedItems.add(item.id):expandedItems.delete(item.id);card.classList.toggle("is-expanded",expanded);expandButton.textContent=expanded?"Свернуть":"Развернуть подпись"};',
)

patch(
    "tools/studio_workflow.py",
    '''def open_book(root: Path) -> None:
    url = (root / "index.html").resolve().as_uri() + "?opened=1#memory-book"
''',
    '''def open_book(root: Path, chapter_id: str = "memory-book") -> None:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", chapter_id or "memory-book")
    url = (root / "index.html").resolve().as_uri() + f"?opened=1#{safe_id}"
''',
)

patch(
    "tools/studio_workflow.py",
    '''    if args.open:
        open_book(root)
''',
    '''    if args.open:
        chapters = book.get("chapters") or []
        first_chapter_id = str((chapters[0] if chapters else {}).get("id") or "memory-book")
        open_book(root, first_chapter_id)
''',
)

patch(
    "preview/capture.mjs",
    'await chromeCheck.goto(`${base}/${previewQuery}&opened=1#memory-book`, { waitUntil: "networkidle" });',
    'await chromeCheck.goto(`${base}/${previewQuery}&opened=1#ordinary-days`, { waitUntil: "networkidle" });',
)

patch(
    "preview/capture.mjs",
    '''await chromeCheck.reload({ waitUntil: "networkidle" });
await chromeCheck.waitForTimeout(220);
''',
    '''await chromeCheck.reload({ waitUntil: "networkidle" });
await settle(chromeCheck);
await chromeCheck.locator("#ordinary-days").scrollIntoViewIfNeeded();
await chromeCheck.waitForTimeout(320);
''',
)

patch(
    "preview/capture.mjs",
    '''const expandButton = studio.locator("[data-expand]").first();
await expandButton.click();
await studio.waitForTimeout(100);
await shot(studio, "19-memory-studio-expanded-caption.png", { fullPage: false });
''',
    '''const expandButton = populatedChapter.locator("[data-expand]").first();
await expandButton.click();
const expandedCard = populatedChapter.locator(".item.is-expanded").first();
await expandedCard.scrollIntoViewIfNeeded();
await studio.waitForTimeout(140);
await shot(studio, "19-memory-studio-expanded-caption.png", { fullPage: false });
''',
)

patch(
    "preview/capture.mjs",
    '''await eightEvent.screenshot({ path: path.join(output, "21-eight-item-event.png"), animations: "disabled" });
''',
    '''await eightEvent.screenshot({ path: path.join(output, "21-eight-item-event.png"), animations: "disabled" });
const rightmostItem = eightEvent.locator(".event-preview__item--8");
await rightmostItem.hover();
await desktop.waitForTimeout(120);
await eightEvent.screenshot({ path: path.join(output, "22-eight-item-hover-layer.png"), animations: "disabled" });
''',
)
