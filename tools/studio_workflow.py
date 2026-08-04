#!/usr/bin/env python3
"""Открытие Memory Studio и безопасное применение экспортированного memories.js.

Экспорт сохраняет дополнительные метаданные Studio, включая crop и posterTime.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TEST_SITE = ROOT / ".memory-test" / "site"


def site_root(scope: str) -> Path:
    return TEST_SITE if scope == "test" else ROOT


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        webbrowser.open(path.resolve().as_uri())


def open_book(root: Path, chapter_id: str = "memory-book") -> None:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", chapter_id or "memory-book")
    url = (root / "index.html").resolve().as_uri() + f"?opened=1#{safe_id}"
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        webbrowser.open(url)


def extract_book(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$", text)
    if not match:
        raise ValueError("не найден объект window.MEMORY_BOOK")
    book = json.loads(match.group(1))
    if not isinstance(book, dict) or not isinstance(book.get("chapters", []), list):
        raise ValueError("неверная структура книги")
    return book


def iter_media(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_media(item)
    elif isinstance(value, dict):
        if any(key in value for key in ("src", "thumb", "poster", "liveVideo")):
            yield value
        for child in value.values():
            yield from iter_media(child)


def validate_paths(book: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    checked: set[str] = set()
    for item in iter_media(book):
        for key in ("src", "thumb", "poster", "liveVideo"):
            raw = item.get(key)
            if not raw or str(raw) in checked:
                continue
            checked.add(str(raw))
            relative = Path(str(raw))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"Небезопасный путь: {raw}")
            elif not (root / relative).is_file():
                errors.append(f"Не найден медиафайл: {raw}")
    return errors


def confirm(message: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in {"y", "yes", "д", "да"}


def prepare_test_studio(studio: Path) -> None:
    """Разделяет test и production localStorage и имя скачиваемого файла."""
    text = studio.read_text(encoding="utf-8")
    text = text.replace('"memory-studio-draft"', '"memory-studio-draft-test"')
    text = text.replace('link.download="memories.js";', 'link.download="memories.test-edited.js";')
    studio.write_text(text, encoding="utf-8")


def command_open(args: argparse.Namespace) -> int:
    root = site_root(args.scope)
    studio = root / "tools" / "studio.html"
    memories = root / "content" / "memories.js"
    if not studio.is_file() or not memories.is_file():
        if args.scope == "test":
            print("Тестовая копия не готова. Сначала запусти успешный режим test.", file=sys.stderr)
        else:
            print(f"Не найдены Studio или memories.js в {root}", file=sys.stderr)
        return 2
    if args.scope == "test":
        prepare_test_studio(studio)
    export_name = "memories.test-edited.js" if args.scope == "test" else "memories.js"
    print(f"Открываю Memory Studio ({args.scope}): {studio}")
    print("После редактирования нажми «Экспортировать memories.js».")
    print("Затем примени скачанный файл командой:")
    print(f"python3 tools/studio_workflow.py apply {args.scope} \"$HOME/Downloads/{export_name}\" --open")
    open_path(studio)
    return 0


def command_apply(args: argparse.Namespace) -> int:
    root = site_root(args.scope)
    source = args.file.expanduser().resolve()
    target = root / "content" / "memories.js"
    if not root.is_dir() or not target.is_file():
        print(f"Не готова область {args.scope}: {root}", file=sys.stderr)
        return 2
    if not source.is_file():
        print(f"Экспортированный файл не найден: {source}", file=sys.stderr)
        return 2
    try:
        book = extract_book(source)
    except Exception as exc:
        print(f"Экспорт Studio не читается: {exc}", file=sys.stderr)
        return 2
    errors = validate_paths(book, root)
    if errors:
        print("Файл не применён:", file=sys.stderr)
        for error in errors[:40]:
            print(f"- {error}", file=sys.stderr)
        return 1
    if args.scope == "production" and not confirm("Заменить memories.js основной книги?", args.yes):
        print("Отменено.")
        return 0
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"memories.before-studio-{timestamp}.js")
    shutil.copy2(target, backup)
    shutil.copy2(source, target)
    try:
        extract_book(target)
    except Exception as exc:
        shutil.copy2(backup, target)
        print(f"Проверка после записи не прошла, прежний файл восстановлен: {exc}", file=sys.stderr)
        return 1
    print(f"Правки применены к {args.scope}: {target}")
    print(f"Резервная копия: {backup}")
    if args.open:
        chapters = book.get("chapters") or []
        first_chapter_id = str((chapters[0] if chapters else {}).get("id") or "memory-book")
        open_book(root, first_chapter_id)
    else:
        print(f"Открыть книгу: open \"{root / 'index.html'}\"")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Безопасная работа с Memory Studio")
    sub = parser.add_subparsers(dest="command", required=True)

    open_parser = sub.add_parser("open", help="Открыть Studio")
    open_parser.add_argument("scope", choices=["test", "production"], nargs="?", default="test")
    open_parser.set_defaults(handler=command_open)

    apply_parser = sub.add_parser("apply", help="Применить экспортированный memories.js")
    apply_parser.add_argument("scope", choices=["test", "production"])
    apply_parser.add_argument("file", type=Path)
    apply_parser.add_argument("--open", action="store_true")
    apply_parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение для production")
    apply_parser.set_defaults(handler=command_apply)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
