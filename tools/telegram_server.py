#!/usr/bin/env python3
"""Local drag-and-drop studio for importing Telegram screenshots.

Run from the repository root:
    python3 tools/telegram_server.py

The server listens only on 127.0.0.1, copies dropped images into media/telegram,
and writes content/telegram.js. Nothing is uploaded to the internet.
"""
from __future__ import annotations

import base64
import json
import re
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "media" / "telegram"
DATA_FILE = ROOT / "content" / "telegram-data.json"
JS_FILE = ROOT / "content" / "telegram.js"
HOST = "127.0.0.1"
PORT = 8765
ALLOWED = {".png", ".jpg", ".jpeg", ".webp"}
MAX_BYTES = 35 * 1024 * 1024

DEFAULT_STATE: dict[str, Any] = {
    "title": "То, что осталось в переписке",
    "subtitle": "Не полный архив чата — только фрагменты, которые сами стали воспоминаниями.",
    "intro": "Здесь собраны отдельные кусочки нашей переписки. Не по важности — просто те, которые захотелось оставить.",
    "quote": "",
    "items": [],
}


def safe_name(value: str) -> str:
    stem = Path(value).stem.lower()
    stem = re.sub(r"[^a-z0-9а-яё_-]+", "-", stem, flags=re.IGNORECASE).strip("-_") or "telegram"
    suffix = Path(value).suffix.lower()
    if suffix == ".jpeg":
        suffix = ".jpg"
    return stem[:80] + suffix


def unique_path(name: str) -> Path:
    candidate = MEDIA_DIR / safe_name(name)
    index = 2
    while candidate.exists():
        candidate = MEDIA_DIR / f"{Path(safe_name(name)).stem}-{index}{candidate.suffix}"
        index += 1
    return candidate


def image_has_transparency(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            if image.mode in {"RGBA", "LA"}:
                alpha = image.getchannel("A")
                return alpha.getextrema()[0] < 255
            if image.mode == "P" and "transparency" in image.info:
                return True
    except Exception:
        return False
    return False


def load_state() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))
    try:
        value = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        merged = {**DEFAULT_STATE, **value}
        merged["items"] = value.get("items", [])
        return merged
    except Exception:
        return json.loads(json.dumps(DEFAULT_STATE, ensure_ascii=False))


def build_chapter(state: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    items = state.get("items", [])
    modes = {item["src"]: item.get("mode", "paper") for item in items}
    blocks: list[dict[str, Any]] = []
    intro = str(state.get("intro", "")).strip()
    if intro:
        blocks.append({"type": "note", "text": intro, "style": "torn", "rotate": -1.2})

    for index in range(0, len(items), 7):
        chunk = items[index:index + 7]
        blocks.append({
            "type": "collage",
            "title": "Фрагменты переписки" if index == 0 else f"Ещё несколько фрагментов · {index // 7 + 1}",
            "caption": "Нажми на любой фрагмент, чтобы рассмотреть его ближе.",
            "photos": [
                {
                    "src": item["src"],
                    "alt": item.get("alt") or "Фрагмент переписки из Telegram",
                    "caption": item.get("caption", ""),
                }
                for item in chunk
            ],
        })

    quote = str(state.get("quote", "")).strip()
    if quote:
        blocks.append({"type": "quote", "text": quote, "author": "из Telegram", "rotate": 1.1})

    chapter = {
        "id": "telegram",
        "number": "TG",
        "kicker": "Несколько сообщений",
        "title": state.get("title") or DEFAULT_STATE["title"],
        "subtitle": state.get("subtitle") or DEFAULT_STATE["subtitle"],
        "layout": "wide",
        "theme": "blue",
        "blocks": blocks,
    }
    return modes, chapter


def write_state(state: dict[str, Any]) -> None:
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[Telegram Studio] {format % args}")

    def send_json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BYTES * 2:
            raise ValueError("Слишком большой запрос")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/api/telegram/state":
            self.send_json(load_state())
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            if self.path == "/api/telegram/upload":
                self.handle_upload()
                return
            if self.path == "/api/telegram/save":
                state = self.read_json()
                write_state(state)
                self.send_json({"ok": True, "items": len(state.get("items", []))})
                return
            self.send_json({"error": "Неизвестный endpoint"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def handle_upload(self) -> None:
        value = self.read_json()
        name = str(value.get("name", "telegram.png"))
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED:
            raise ValueError("Поддерживаются PNG, JPG, JPEG и WEBP")
        raw = str(value.get("data", ""))
        if "," in raw:
            raw = raw.split(",", 1)[1]
        content = base64.b64decode(raw, validate=True)
        if len(content) > MAX_BYTES:
            raise ValueError("Один файл не должен превышать 35 МБ")

        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        target = unique_path(name)
        target.write_bytes(content)
        mode = "cutout" if image_has_transparency(target) else "paper"
        relative = target.relative_to(ROOT).as_posix()
        self.send_json({
            "src": relative,
            "caption": "",
            "alt": "Фрагмент переписки из Telegram",
            "mode": mode,
            "name": target.name,
        })


def main() -> int:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        write_state(load_state())
    url = f"http://{HOST}:{PORT}/tools/telegram_studio.html"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Telegram Studio: {url}")
    print("Работает только локально. Для остановки нажми Ctrl+C.")
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
