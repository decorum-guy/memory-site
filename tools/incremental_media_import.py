#!/usr/bin/env python3
"""Incrementally import photos, videos and Live Photos into an edited book.

Unlike the full archive importer, this module never rebuilds the book. It stages
selected browser files, reuses the production conversion/grouping engine, merges
only the newly processed items into the supplied Studio draft, validates every
path, creates a backup and writes content/memories.js atomically.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, BinaryIO, Iterable

import import_memories as engine
from live_photo_pairing import pair_live_photos_strict

ROOT = Path(__file__).resolve().parents[1]
MEMORIES_FILE = ROOT / "content" / "memories.js"
IMPORT_HOME = ROOT / ".memory-imports"
SOURCE_HOME = ROOT / ".memory-import-source"
SUPPORTED_EXTS = engine.SUPPORTED_EXTS
IMAGE_EXTS = engine.IMAGE_EXTS
VIDEO_EXTS = engine.VIDEO_EXTS
MAX_FILE_BYTES = 20 * 1024 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
IMPORT_LOCK = threading.Lock()
MANIFEST_LOCK = threading.Lock()
BATCH_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def validate_batch_id(value: Any) -> str:
    batch_id = str(value or "").strip()
    if not BATCH_PATTERN.fullmatch(batch_id):
        raise ValueError("Некорректный идентификатор импорта")
    return batch_id


def safe_filename(value: str) -> str:
    raw = Path(str(value or "media")).name
    suffix = Path(raw).suffix.lower()
    stem = Path(raw).stem
    stem = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._ -]+", "-", stem).strip(" .-_") or "media"
    return f"{stem[:120]}{suffix}"


def batch_dir(batch_id: str) -> Path:
    return IMPORT_HOME / validate_batch_id(batch_id)


def manifest_path(batch_id: str) -> Path:
    return batch_dir(batch_id) / "manifest.json"


def load_manifest(batch_id: str) -> dict[str, Any]:
    path = manifest_path(batch_id)
    if not path.exists():
        return {"batchId": batch_id, "files": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Повреждён manifest импорта: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
        raise ValueError("Повреждён manifest импорта")
    return value


def save_manifest(batch_id: str, value: dict[str, Any]) -> None:
    path = manifest_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def stage_upload(
    batch_id: str,
    name: str,
    stream: BinaryIO,
    length: int,
    modified_ms: int = 0,
) -> dict[str, Any]:
    batch_id = validate_batch_id(batch_id)
    cleaned = safe_filename(name)
    suffix = Path(cleaned).suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        allowed = ", ".join(sorted(SUPPORTED_EXTS))
        raise ValueError(f"Неподдерживаемый формат {suffix or '[без расширения]'}. Допустимы: {allowed}")
    if length <= 0 or length > MAX_FILE_BYTES:
        raise ValueError("Файл пустой или превышает 20 ГБ")

    uploads = batch_dir(batch_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    temporary = uploads / f".upload-{uuid.uuid4().hex}.tmp"
    digest = hashlib.sha256()
    remaining = length
    written = 0
    try:
        with temporary.open("wb") as target:
            while remaining:
                chunk = stream.read(min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise ValueError("Загрузка оборвалась до конца файла")
                target.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                remaining -= len(chunk)
        if written != length:
            raise ValueError("Размер загруженного файла не совпал с Content-Length")

        token = digest.hexdigest()[:32]
        with MANIFEST_LOCK:
            manifest = load_manifest(batch_id)
            existing = manifest["files"].get(token)
            if existing:
                existing_path = batch_dir(batch_id) / str(existing.get("path") or "")
                if existing_path.is_file():
                    temporary.unlink(missing_ok=True)
                    return existing

            target = uploads / cleaned
            if target.exists():
                target = uploads / f"{Path(cleaned).stem}__{token[:8]}{suffix}"
            os.replace(temporary, target)
            if modified_ms > 0:
                timestamp = modified_ms / 1000
                os.utime(target, (timestamp, timestamp))
            entry = {
                "token": token,
                "name": cleaned,
                "path": target.relative_to(batch_dir(batch_id)).as_posix(),
                "size": written,
                "sha256": digest.hexdigest(),
                "modifiedMs": int(modified_ms or 0),
                "kind": "image" if suffix in IMAGE_EXTS else "video",
            }
            manifest["files"][token] = entry
            save_manifest(batch_id, manifest)
            return entry
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _persistent_sources(batch_id: str, manifest: dict[str, Any]) -> tuple[dict[Path, Path], list[Path]]:
    mapping: dict[Path, Path] = {}
    created: list[Path] = []
    SOURCE_HOME.mkdir(parents=True, exist_ok=True)
    for entry in manifest["files"].values():
        source = batch_dir(batch_id) / str(entry["path"])
        if not source.is_file():
            raise ValueError(f"Загруженный файл пропал: {entry.get('name')}")
        digest = str(entry["sha256"])
        suffix = Path(str(entry["name"])).suffix.lower()
        target = SOURCE_HOME / digest[:2] / f"{digest}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
            created.append(target)
        mapping[source.resolve()] = target.resolve()
    return mapping, created


def _explicit_live_pairs(
    media: list[Any],
    manifest: dict[str, Any],
    batch_id: str,
    pairs: list[dict[str, Any]],
) -> tuple[set[Path], set[Path]]:
    by_source = {item.source.resolve(): item for item in media}
    by_token: dict[str, Path] = {}
    for token, entry in manifest["files"].items():
        by_token[token] = (batch_dir(batch_id) / str(entry["path"])).resolve()

    paired_images: set[Path] = set()
    used_videos: set[Path] = set()
    for index, pair in enumerate(pairs, 1):
        photo_path = by_token.get(str(pair.get("photoToken") or ""))
        video_path = by_token.get(str(pair.get("videoToken") or ""))
        if photo_path is None or video_path is None:
            raise ValueError(f"Live Photo пара {index}: файл не найден в текущей загрузке")
        photo = by_source.get(photo_path)
        video = by_source.get(video_path)
        if photo is None or not photo.is_image:
            raise ValueError(f"Live Photo пара {index}: первым должно быть фото")
        if video is None or video.is_image:
            raise ValueError(f"Live Photo пара {index}: вторым должен быть видеофайл")
        if photo_path in paired_images:
            raise ValueError(f"Live Photo пара {index}: это фото уже используется в другой паре")
        if video_path in used_videos:
            raise ValueError(f"Live Photo пара {index}: это видео уже используется в другой паре")
        photo.live_source = video.source
        paired_images.add(photo_path)
        used_videos.add(video_path)
    return paired_images, used_videos


def _prepare_media(batch_id: str, manifest: dict[str, Any], pairs: list[dict[str, Any]]) -> tuple[list[Any], set[Path], int, list[Path]]:
    paths = [
        (batch_dir(batch_id) / str(entry["path"])).resolve()
        for entry in manifest["files"].values()
    ]
    if not paths:
        raise ValueError("Сначала выбери хотя бы один файл")

    metadata = engine.exiftool_metadata(paths)
    media = engine.build_media(paths, metadata)
    explicit_images, explicit_videos = _explicit_live_pairs(media, manifest, batch_id, pairs)

    remaining = [
        item for item in media
        if item.source.resolve() not in explicit_images and item.source.resolve() not in explicit_videos
    ]
    _, auto_used = pair_live_photos_strict(remaining)
    used_videos = set(explicit_videos) | {path.resolve() for path in auto_used}

    source_mapping, created_sources = _persistent_sources(batch_id, manifest)
    for item in media:
        old_source = item.source.resolve()
        item.source = source_mapping[old_source]
        if item.live_source:
            item.live_source = source_mapping[item.live_source.resolve()]
    persistent_used = {source_mapping[path.resolve()] for path in used_videos}
    return media, persistent_used, len(auto_used), created_sources


def _iter_items(book: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for chapter in book.get("chapters") or []:
        for block in chapter.get("blocks") or []:
            for item in block.get("items") or []:
                if isinstance(item, dict):
                    yield item


def _item_dict(media: Any) -> dict[str, Any]:
    value = engine.media_to_dict(media)
    if media.latitude is not None and media.longitude is not None:
        value["gps"] = {"lat": round(float(media.latitude), 7), "lon": round(float(media.longitude), 7)}
    return value


def _event_id(year: int, items: list[dict[str, Any]], existing: set[str]) -> str:
    fingerprint = "|".join(sorted(str(item.get("id") or item.get("src") or "") for item in items))
    base = f"event-studio-{year}-{hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()[:12]}"
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{counter}"
        counter += 1
    existing.add(candidate)
    return candidate


def _chapter_year(chapter: dict[str, Any]) -> int | None:
    for value in (chapter.get("number"), chapter.get("title"), chapter.get("id")):
        match = re.search(r"\b((?:19|20)\d{2})\b", str(value or ""))
        if match:
            return int(match.group(1))
    return None


def _event_time(block: dict[str, Any]) -> dt.datetime | None:
    candidates = [block.get("date")]
    candidates.extend(item.get("takenAt") for item in block.get("items") or [] if isinstance(item, dict))
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        try:
            return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _new_chapter(year: int, index: int) -> dict[str, Any]:
    return {
        "id": f"year-{year}",
        "number": str(year),
        "kicker": "Глава по времени",
        "title": str(year),
        "subtitle": "Новые события, добавленные через Memory Studio.",
        "layout": engine.LAYOUTS[index % len(engine.LAYOUTS)],
        "theme": engine.THEMES[index % len(engine.THEMES)],
        "blocks": [],
    }


def _chapter_for_year(book: dict[str, Any], year: int) -> dict[str, Any]:
    chapters = book.setdefault("chapters", [])
    for chapter in chapters:
        if _chapter_year(chapter) == year:
            chapter.setdefault("blocks", [])
            return chapter
    chapter = _new_chapter(year, len(chapters))
    insert_at = len(chapters)
    for index, existing in enumerate(chapters):
        existing_year = _chapter_year(existing)
        if existing_year is not None and existing_year > year:
            insert_at = index
            break
    chapters.insert(insert_at, chapter)
    return chapter


def _insert_event(chapter: dict[str, Any], block: dict[str, Any]) -> None:
    blocks = chapter.setdefault("blocks", [])
    new_time = _event_time(block)
    last_event_index = -1
    for index, existing in enumerate(blocks):
        if existing.get("type") != "event":
            continue
        last_event_index = index
        existing_time = _event_time(existing)
        if new_time is not None and existing_time is not None and existing_time > new_time:
            blocks.insert(index, block)
            return
    blocks.insert(last_event_index + 1 if last_event_index >= 0 else len(blocks), block)


def _find_target(book: dict[str, Any], target: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    chapter_index = int(target.get("chapterIndex", -1))
    block_index = int(target.get("blockIndex", -1))
    chapters = book.get("chapters") or []
    if chapter_index < 0 or chapter_index >= len(chapters):
        raise ValueError("Выбранная глава больше не существует")
    blocks = chapters[chapter_index].get("blocks") or []
    if block_index < 0 or block_index >= len(blocks) or blocks[block_index].get("type") != "event":
        raise ValueError("Выбранное событие больше не существует")
    return chapters[chapter_index], blocks[block_index]


def _merge_book(
    base_book: dict[str, Any],
    processed: list[Any],
    target: dict[str, Any] | None,
) -> tuple[dict[str, Any], int, int, str]:
    book = copy.deepcopy(base_book)
    if not isinstance(book, dict) or not isinstance(book.get("chapters"), list):
        raise ValueError("Studio передала некорректную структуру книги")

    existing_ids = {str(item.get("id")) for item in _iter_items(book) if item.get("id")}
    existing_src = {str(item.get("src")) for item in _iter_items(book) if item.get("src")}
    fresh = [item for item in processed if item.item_id not in existing_ids and item.output_src not in existing_src]
    duplicates = len(processed) - len(fresh)
    if not fresh:
        return book, 0, duplicates, ""

    created_events = 0
    focus_chapter = ""
    if target:
        chapter, block = _find_target(book, target)
        additions = [_item_dict(item) for item in fresh]
        block.setdefault("items", []).extend(additions)
        block["items"].sort(key=lambda item: str(item.get("takenAt") or ""))
        block["layout"] = "stack" if len(block["items"]) > 8 else "collage"
        focus_chapter = str(chapter.get("id") or "")
    else:
        events = engine.group_events(fresh, 75, 180, 0.72)
        existing_block_ids = {
            str(block.get("id"))
            for chapter in book.get("chapters") or []
            for block in chapter.get("blocks") or []
            if block.get("id")
        }
        for event in events:
            items = [_item_dict(item) for item in event.items]
            year = event.start.year
            chapter = _chapter_for_year(book, year)
            block = {
                "type": "event",
                "id": _event_id(year, items, existing_block_ids),
                "title": engine.format_event_title(event),
                "caption": "Добавь сюда одну короткую деталь об этом дне.",
                "date": event.start.isoformat(timespec="minutes"),
                "layout": "stack" if len(items) > 8 else "collage",
                "items": items,
            }
            _insert_event(chapter, block)
            created_events += 1
            if not focus_chapter:
                focus_chapter = str(chapter.get("id") or "")
    return book, len(fresh), duplicates, focus_chapter


def _copy_generated(stage_root: Path) -> list[Path]:
    created: list[Path] = []
    source_root = stage_root / "media" / "generated"
    if not source_root.exists():
        return created
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(stage_root)
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        shutil.copy2(source, target)
        created.append(target)
    return created


def _validate_paths(book: dict[str, Any]) -> None:
    errors: list[str] = []
    checked: set[str] = set()
    for item in _iter_items(book):
        for key in ("src", "thumb", "poster", "liveVideo"):
            raw = str(item.get(key) or "")
            if not raw or raw in checked:
                continue
            checked.add(raw)
            relative = Path(raw)
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"Небезопасный путь: {raw}")
            elif not (ROOT / relative).is_file():
                errors.append(f"Не найден медиафайл: {raw}")
    if errors:
        detail = "; ".join(errors[:12])
        if len(errors) > 12:
            detail += f"; и ещё {len(errors) - 12}"
        raise ValueError(detail)


def _write_book(book: dict[str, Any]) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = MEMORIES_FILE.with_name(f"memories.before-media-import-{timestamp}.js")
    temporary = MEMORIES_FILE.with_name(f".memories.media-{uuid.uuid4().hex}.tmp")
    shutil.copy2(MEMORIES_FILE, backup)
    text = (
        "// Обновлено инкрементальным импортом Memory Studio.\n"
        "window.MEMORY_BOOK = " + json.dumps(book, ensure_ascii=False, indent=2) + ";\n"
    )
    try:
        temporary.write_text(text, encoding="utf-8")
        json.loads(re.search(r"window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$", text).group(1))
        os.replace(temporary, MEMORIES_FILE)
    except Exception:
        temporary.unlink(missing_ok=True)
        shutil.copy2(backup, MEMORIES_FILE)
        raise
    return backup


def process_batch(
    batch_id: str,
    base_book: dict[str, Any],
    pairs: list[dict[str, Any]] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    batch_id = validate_batch_id(batch_id)
    pairs = pairs or []
    with IMPORT_LOCK:
        manifest = load_manifest(batch_id)
        media, used_live_videos, auto_live_pairs, created_sources = _prepare_media(batch_id, manifest, pairs)
        stage_root = batch_dir(batch_id) / "stage"
        shutil.rmtree(stage_root, ignore_errors=True)
        stage_root.mkdir(parents=True, exist_ok=True)
        settings = engine.VideoSettings(max_width=1920, crf=23, preset="veryfast", live_max_width=1080)
        copied_files: list[Path] = []
        try:
            processed, errors = engine.process_media(media, used_live_videos, stage_root, max(2, min(6, os.cpu_count() or 4)), settings)
            if errors:
                detail = "; ".join(f"{Path(item['file']).name}: {item['error']}" for item in errors[:8])
                raise ValueError(f"Не удалось обработать часть файлов: {detail}")

            book, imported, duplicates, focus_chapter = _merge_book(base_book, processed, target)
            if imported == 0:
                shutil.rmtree(batch_dir(batch_id), ignore_errors=True)
                for source in created_sources:
                    source.unlink(missing_ok=True)
                return {
                    "ok": True,
                    "book": book,
                    "importedItems": 0,
                    "duplicates": duplicates,
                    "createdEvents": 0,
                    "explicitLivePairs": len(pairs),
                    "autoLivePairs": auto_live_pairs,
                    "backup": "",
                    "bookUrl": "/index.html?opened=1",
                }

            copied_files = _copy_generated(stage_root)
            _validate_paths(book)
            backup = _write_book(book)
            safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", focus_chapter or "memory-book")
            created_events = 0 if target else len(engine.group_events(
                [item for item in processed if item.item_id not in {
                    str(existing.get("id")) for existing in _iter_items(base_book) if existing.get("id")
                }], 75, 180, 0.72
            ))
            shutil.rmtree(batch_dir(batch_id), ignore_errors=True)
            for source in created_sources:
                source.unlink(missing_ok=True)
            return {
                "ok": True,
                "book": book,
                "importedItems": imported,
                "duplicates": duplicates,
                "createdEvents": created_events,
                "explicitLivePairs": len(pairs),
                "autoLivePairs": auto_live_pairs,
                "backup": backup.relative_to(ROOT).as_posix(),
                "bookUrl": f"/index.html?opened=1#{safe_id}",
            }
        except Exception:
            for target_path in copied_files:
                target_path.unlink(missing_ok=True)
            raise
