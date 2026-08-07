#!/usr/bin/env python3
"""Local constructors and safe production apply server for Memory Site.

Run from repository root:
    python3 tools/telegram_server.py

The server listens only on 127.0.0.1. Optional Telegram screenshots are copied
to media/telegram. Memory Studio may validate and apply a downloaded
memories.js to production with an automatic local backup. Nothing is uploaded
to the internet.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import shutil
import threading
import uuid
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "media" / "telegram"
DATA_FILE = ROOT / "content" / "telegram-data.json"
JS_FILE = ROOT / "content" / "telegram.js"
MEMORIES_FILE = ROOT / "content" / "memories.js"
HOST = "127.0.0.1"
PORT = 8765
ALLOWED = {".png", ".jpg", ".jpeg", ".webp"}
RANGE_MEDIA = {".mp4", ".mov", ".m4v", ".webm", ".mp3", ".m4a", ".wav", ".ogg"}
MAX_BYTES = 35 * 1024 * 1024
MAX_REQUEST_BYTES = 75 * 1024 * 1024

DEFAULT_STATE: dict[str, Any] = {
    "kicker": "Слова, которые остались",
    "title": "То, что осталось в переписке",
    "subtitle": "Несколько наших фраз — и слова, которые я хочу оставить тебе рядом.",
    "blocks": [],
}


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def safe_name(value: str) -> str:
    stem = Path(value).stem.lower()
    stem = re.sub(r"[^a-z0-9а-яё_-]+", "-", stem, flags=re.IGNORECASE).strip("-_") or "telegram"
    suffix = Path(value).suffix.lower()
    if suffix == ".jpeg":
        suffix = ".jpg"
    return stem[:80] + suffix


def unique_path(name: str) -> Path:
    cleaned = safe_name(name)
    candidate = MEDIA_DIR / cleaned
    index = 2
    while candidate.exists():
        candidate = MEDIA_DIR / f"{Path(cleaned).stem}-{index}{Path(cleaned).suffix}"
        index += 1
    return candidate


def image_has_transparency(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            if image.mode in {"RGBA", "LA"}:
                alpha = image.getchannel("A")
                return alpha.getextrema()[0] < 255
            return image.mode == "P" and "transparency" in image.info
    except Exception:
        return False


def clamp_shape(value: Any, fallback: int = 0) -> int:
    try:
        return int(value) % 5
    except (TypeError, ValueError):
        return fallback % 5


def normalize_block(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kind = str(value.get("type") or "").strip().lower()
    if kind == "note":
        return {
            "id": str(value.get("id") or new_id("note")),
            "type": "note",
            "text": str(value.get("text") or "").strip(),
            "shape": clamp_shape(value.get("shape"), index),
            "layout": str(value.get("layout") or "auto") if str(value.get("layout") or "auto") in {"auto", "left", "right"} else "auto",
        }
    if kind == "quote":
        speaker = "sonya" if str(value.get("speaker") or "").lower() == "sonya" else "me"
        screenshot = str(value.get("screenshot") or "").strip()
        if screenshot and (Path(screenshot).is_absolute() or ".." in Path(screenshot).parts):
            screenshot = ""
        return {
            "id": str(value.get("id") or new_id("quote")),
            "type": "quote",
            "text": str(value.get("text") or "").strip(),
            "speaker": speaker,
            "screenshot": screenshot,
            "screenshotName": str(value.get("screenshotName") or (Path(screenshot).name if screenshot else "")),
            "screenshotMode": "cutout" if value.get("screenshotMode") == "cutout" else "paper",
            "shape": clamp_shape(value.get("shape"), index),
        }
    return None


def migrate_legacy_state(value: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    intro = str(value.get("intro") or "").strip()
    if intro:
        blocks.append({"id": new_id("note"), "type": "note", "text": intro, "shape": 0})
    for index, item in enumerate(value.get("items") or []):
        if not isinstance(item, dict):
            continue
        blocks.append({
            "id": new_id("quote"),
            "type": "quote",
            "text": str(item.get("caption") or "Фрагмент нашей переписки").strip(),
            "speaker": "sonya",
            "screenshot": str(item.get("src") or ""),
            "screenshotName": str(item.get("name") or Path(str(item.get("src") or "")).name),
            "screenshotMode": "cutout" if item.get("mode") == "cutout" else "paper",
            "shape": index % 5,
        })
    ending = str(value.get("quote") or "").strip()
    if ending:
        blocks.append({"id": new_id("note"), "type": "note", "text": ending, "shape": 3})
    return blocks


def normalize_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    raw_blocks = value.get("blocks")
    if isinstance(raw_blocks, list):
        blocks = [block for index, raw in enumerate(raw_blocks) if (block := normalize_block(raw, index)) is not None]
    else:
        blocks = migrate_legacy_state(value)
    return {
        "kicker": str(value.get("kicker") or DEFAULT_STATE["kicker"]).strip(),
        "title": str(value.get("title") or DEFAULT_STATE["title"]).strip(),
        "subtitle": str(value.get("subtitle") or DEFAULT_STATE["subtitle"]).strip(),
        "blocks": blocks,
    }


def load_state() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))
    try:
        return normalize_state(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    except Exception:
        return json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))


def build_chapter(state: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    modes: dict[str, str] = {}
    for index, item in enumerate(state.get("blocks", [])):
        shape = clamp_shape(item.get("shape"), index)
        rotate = (-1.2, .75, -0.45, 1.05, -0.8)[shape]
        if item.get("type") == "note":
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            blocks.append({
                "type": "note",
                "telegramKind": "note",
                "text": text,
                "style": "torn",
                "shape": shape,
                "rotate": rotate,
                "layout": item.get("layout") if item.get("layout") in {"left", "right"} else "auto",
            })
            continue
        text = str(item.get("text") or "").strip()
        screenshot = str(item.get("screenshot") or "").strip()
        if not text and not screenshot:
            continue
        speaker = "sonya" if item.get("speaker") == "sonya" else "me"
        if screenshot:
            modes[screenshot] = "cutout" if item.get("screenshotMode") == "cutout" else "paper"
        blocks.append({
            "type": "quote",
            "telegramKind": "message",
            "text": text or "Сообщение без подписи",
            "author": "Соня" if speaker == "sonya" else "Артём",
            "speaker": speaker,
            "screenshot": screenshot,
            "screenshotAlt": f"Скриншот сообщения — {'Соня' if speaker == 'sonya' else 'Артём'}",
            "screenshotMode": modes.get(screenshot, "paper"),
            "shape": shape,
            "rotate": rotate,
        })
    chapter = {
        "id": "telegram",
        "number": "TG",
        "kicker": state.get("kicker") or DEFAULT_STATE["kicker"],
        "title": state.get("title") or DEFAULT_STATE["title"],
        "subtitle": state.get("subtitle") or DEFAULT_STATE["subtitle"],
        "layout": "wide",
        "theme": "blue",
        "blocks": blocks,
    }
    return modes, chapter


def write_state(value: Any) -> dict[str, Any]:
    state = normalize_state(value)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    modes, chapter = build_chapter(state)
    content = (
        "// Сгенерировано через tools/telegram_server.py.\n"
        "// Глава включается параметром telegramEnabled в content/settings.js.\n"
        f"window.TELEGRAM_MEDIA_MODES = {json.dumps(modes, ensure_ascii=False, indent=2)};\n"
        f"window.TELEGRAM_CHAPTER = {json.dumps(chapter, ensure_ascii=False, indent=2)};\n"
    )
    JS_FILE.write_text(content, encoding="utf-8")
    return state


def extract_memory_book_text(text: str) -> dict[str, Any]:
    match = re.search(r"window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$", text)
    payload = match.group(1) if match else text
    book = json.loads(payload)
    if not isinstance(book, dict) or not isinstance(book.get("chapters"), list):
        raise ValueError("неверная структура книги")
    return book


def iter_memory_media(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_memory_media(item)
    elif isinstance(value, dict):
        if any(key in value for key in ("src", "thumb", "poster", "liveVideo")):
            yield value
        for child in value.values():
            yield from iter_memory_media(child)


def validate_memory_paths(book: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checked: set[str] = set()
    for item in iter_memory_media(book):
        for key in ("src", "thumb", "poster", "liveVideo"):
            raw = item.get(key)
            if not raw or str(raw) in checked:
                continue
            checked.add(str(raw))
            relative = Path(str(raw))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"Небезопасный путь: {raw}")
            elif not (ROOT / relative).is_file():
                errors.append(f"Не найден медиафайл: {raw}")
    return errors


def apply_memory_book(text: str) -> dict[str, str]:
    if not MEMORIES_FILE.is_file():
        raise ValueError("production content/memories.js не найден")
    book = extract_memory_book_text(text)
    errors = validate_memory_paths(book)
    if errors:
        detail = "; ".join(errors[:12])
        if len(errors) > 12:
            detail += f"; и ещё {len(errors) - 12}"
        raise ValueError(detail)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = MEMORIES_FILE.with_name(f"memories.before-studio-{timestamp}.js")
    temporary = MEMORIES_FILE.with_name(f".memories.apply-{uuid.uuid4().hex}.tmp")
    shutil.copy2(MEMORIES_FILE, backup)
    try:
        temporary.write_text(text, encoding="utf-8")
        extract_memory_book_text(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, MEMORIES_FILE)
    except Exception:
        temporary.unlink(missing_ok=True)
        shutil.copy2(backup, MEMORIES_FILE)
        raise
    chapters = book.get("chapters") or []
    first_id = str((chapters[0] if chapters else {}).get("id") or "memory-book")
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", first_id)
    return {"backup": backup.relative_to(ROOT).as_posix(), "bookUrl": f"/index.html?opened=1#{safe_id}"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._range_remaining: int | None = None
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[Memory Site] {format % args}")

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0]
        if Path(path).suffix.lower() in RANGE_MEDIA:
            self.send_header("Accept-Ranges", "bytes")
        no_cache = (
            path.startswith("/api/telegram/")
            or path.startswith("/api/memory/")
            or path in {
                "/index.html", "/tools/studio.html", "/tools/telegram_studio.html",
                "/content/memories.js", "/content/telegram.js", "/content/telegram-data.json",
            }
        )
        if no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def send_head(self):
        range_header = self.headers.get("Range")
        if not range_header:
            self._range_remaining = None
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            self._range_remaining = None
            return super().send_head()
        try:
            source = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            size = os.fstat(source.fileno()).st_size
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match or size <= 0:
                raise ValueError
            start_raw, end_raw = match.groups()
            if not start_raw and not end_raw:
                raise ValueError
            if not start_raw:
                suffix = int(end_raw)
                if suffix <= 0:
                    raise ValueError
                start = max(0, size - suffix)
                end = size - 1
            else:
                start = int(start_raw)
                end = int(end_raw) if end_raw else size - 1
            if start < 0 or start >= size or end < start:
                raise ValueError
            end = min(end, size - 1)
            length = end - start + 1
            source.seek(start)
            self._range_remaining = length
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(os.fstat(source.fileno()).st_mtime))
            self.end_headers()
            return source
        except ValueError:
            source.close()
            self._range_remaining = None
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{os.path.getsize(path)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        except Exception:
            source.close()
            raise

    def copyfile(self, source, outputfile) -> None:
        remaining = self._range_remaining
        if remaining is None:
            super().copyfile(source, outputfile)
            return
        try:
            while remaining > 0:
                chunk = source.read(min(128 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        finally:
            self._range_remaining = None

    def send_json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Некорректный или слишком большой запрос")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/telegram/state":
            self.send_json(load_state())
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            if path == "/api/telegram/upload":
                self.handle_upload()
                return
            if path == "/api/telegram/save":
                state = write_state(self.read_json())
                notes = sum(1 for block in state["blocks"] if block["type"] == "note")
                quotes = sum(1 for block in state["blocks"] if block["type"] == "quote")
                self.send_json({"ok": True, "blocks": len(state["blocks"]), "notes": notes, "quotes": quotes})
                return
            if path == "/api/memory/apply":
                value = self.read_json()
                name = str(value.get("name") or "memories.js")
                if Path(name).suffix.lower() not in {".js", ".json"}:
                    raise ValueError("Выбери memories.js или JSON-экспорт Studio")
                text = str(value.get("text") or "")
                if not text.strip():
                    raise ValueError("Файл пустой")
                result = apply_memory_book(text)
                self.send_json({"ok": True, **result})
                return
            self.send_json({"error": "Неизвестный endpoint"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def handle_upload(self) -> None:
        value = self.read_json()
        name = str(value.get("name") or "telegram.png")
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED:
            raise ValueError("Поддерживаются PNG, JPG, JPEG и WEBP")
        raw = str(value.get("data") or "")
        if "," in raw:
            raw = raw.split(",", 1)[1]
        content = base64.b64decode(raw, validate=True)
        if not content or len(content) > MAX_BYTES:
            raise ValueError("Файл пустой или превышает 35 МБ")
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        target = unique_path(name)
        target.write_bytes(content)
        try:
            with Image.open(target) as image:
                image.verify()
        except Exception:
            target.unlink(missing_ok=True)
            raise ValueError("Файл не является читаемым изображением")
        relative = target.relative_to(ROOT).as_posix()
        self.send_json({
            "src": relative,
            "name": target.name,
            "mode": "cutout" if image_has_transparency(target) else "paper",
        })


def main() -> int:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        write_state(DEFAULT_STATE)
    telegram_url = f"http://{HOST}:{PORT}/tools/telegram_studio.html"
    memory_url = f"http://{HOST}:{PORT}/tools/studio.html"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Telegram Studio: {telegram_url}")
    print(f"Memory Studio:  {memory_url}")
    print("Работает только локально. Для остановки нажми Ctrl+C.")
    threading.Timer(0.7, lambda: webbrowser.open(telegram_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
