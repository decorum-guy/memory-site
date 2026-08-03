#!/usr/bin/env python3
"""Локальный импорт большого архива iPhone в scrapbook-сайт.

Что делает импортёр:
- читает даты, GPS, длительность и идентификаторы Live Photo через ExifTool;
- превращает HEIC/HEIF в совместимые JPEG и создаёт лёгкие превью;
- перекодирует обычные и длинные видео в H.264/AAC MP4 без ограничения длительности;
- связывает пары Apple Live Photo;
- группирует материалы по времени, месту и лёгкой визуальной близости;
- записывает content/memories.js и отчёт content/import-report.json.

Обработка полностью локальная: файлы никуда не отправляются.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageOps, ImageStat

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

IMAGE_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
RUS_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
THEMES = ["rose", "blue", "ochre", "green", "ink"]
LAYOUTS = ["scrap", "wide", "story", "split"]


@dataclasses.dataclass
class Media:
    source: Path
    kind: str
    taken_at: dt.datetime
    latitude: float | None = None
    longitude: float | None = None
    content_id: str | None = None
    duration: float | None = None
    avg_rgb: tuple[int, int, int] | None = None
    dhash: int | None = None
    output_src: str | None = None
    thumb_src: str | None = None
    poster_src: str | None = None
    live_source: Path | None = None
    live_output_src: str | None = None
    caption: str = ""
    item_id: str = ""

    @property
    def is_image(self) -> bool:
        return self.kind == "image"


@dataclasses.dataclass
class Event:
    items: list[Media]

    @property
    def start(self) -> dt.datetime:
        return min(item.taken_at for item in self.items)

    @property
    def end(self) -> dt.datetime:
        return max(item.taken_at for item in self.items)


@dataclasses.dataclass(frozen=True)
class VideoSettings:
    max_width: int
    crf: int
    preset: str
    live_max_width: int


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_json(cmd: list[str]) -> Any:
    completed = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return json.loads(completed.stdout)


def scan_files(source: Path) -> list[Path]:
    files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    return sorted(files, key=lambda p: (p.parent.as_posix().lower(), p.name.lower()))


def exiftool_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    if not command_exists("exiftool") or not paths:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(paths), 180):
        chunk = paths[start:start + 180]
        cmd = [
            "exiftool", "-json", "-n", "-api", "QuickTimeUTC=1",
            "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate", "-TrackCreateDate",
            "-GPSLatitude", "-GPSLongitude", "-ContentIdentifier", "-Duration",
            *[str(p) for p in chunk],
        ]
        try:
            rows = run_json(cmd)
        except Exception as exc:
            print(f"Предупреждение: ExifTool не прочитал часть файлов: {exc}", file=sys.stderr)
            continue
        for row in rows:
            source_file = row.get("SourceFile")
            if source_file:
                result[str(Path(source_file).resolve())] = row
    return result


def first_value(mapping: dict[str, Any], names: Iterable[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    for key, value in lowered.items():
        if any(name.lower() in key for name in names) and value not in (None, ""):
            return value
    return None


def parse_datetime(value: Any, fallback: dt.datetime) -> dt.datetime:
    if value is None:
        return fallback
    text = str(value).strip()
    text = re.sub(r"([+-]\d\d):?(\d\d)$", r"\1:\2", text)
    for fmt in (
        "%Y:%m:%d %H:%M:%S%z", "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
    ):
        try:
            parsed = dt.datetime.strptime(text, fmt)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return fallback


def pil_datetime(path: Path) -> dt.datetime | None:
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            for tag in (36867, 36868, 306):
                if exif.get(tag):
                    return parse_datetime(exif.get(tag), dt.datetime.fromtimestamp(path.stat().st_mtime))
    except Exception:
        return None
    return None


def build_media(paths: list[Path], metadata: dict[str, dict[str, Any]]) -> list[Media]:
    result: list[Media] = []
    for path in paths:
        row = metadata.get(str(path.resolve()), {})
        fallback = dt.datetime.fromtimestamp(path.stat().st_mtime)
        taken = parse_datetime(first_value(row, ["DateTimeOriginal", "MediaCreateDate", "CreateDate", "TrackCreateDate"]), pil_datetime(path) or fallback)
        latitude = first_value(row, ["GPSLatitude"])
        longitude = first_value(row, ["GPSLongitude"])
        duration = first_value(row, ["Duration"])
        result.append(Media(
            source=path,
            kind="image" if path.suffix.lower() in IMAGE_EXTS else "video",
            taken_at=taken,
            latitude=float(latitude) if latitude is not None else None,
            longitude=float(longitude) if longitude is not None else None,
            content_id=str(first_value(row, ["ContentIdentifier"]) or "").strip() or None,
            duration=float(duration) if duration is not None else None,
        ))
    return result


def pair_live_photos(media: list[Media]) -> tuple[list[Media], set[Path]]:
    images = [m for m in media if m.is_image]
    videos = [m for m in media if not m.is_image]
    used_videos: set[Path] = set()
    videos_by_id: dict[str, list[Media]] = defaultdict(list)
    videos_by_stem: dict[str, list[Media]] = defaultdict(list)
    for video in videos:
        if video.content_id:
            videos_by_id[video.content_id].append(video)
        videos_by_stem[video.source.stem.lower()].append(video)
    for image in images:
        candidates = list(videos_by_id.get(image.content_id or "", [])) if image.content_id else []
        if not candidates:
            candidates = list(videos_by_stem.get(image.source.stem.lower(), []))
        candidates = [candidate for candidate in candidates if candidate.source not in used_videos]
        if not candidates:
            continue
        candidates.sort(key=lambda candidate: abs((candidate.taken_at - image.taken_at).total_seconds()))
        best = candidates[0]
        if image.content_id or abs((best.taken_at - image.taken_at).total_seconds()) <= 600:
            image.live_source = best.source
            used_videos.add(best.source)
    return media, used_videos


def stable_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:14]


def dhash(image: Image.Image, hash_size: int = 8) -> int:
    gray = ImageOps.grayscale(image).resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            value = (value << 1) | int(left > right)
    return value


def analyze_and_convert_image(media: Media, root: Path) -> Media:
    output_dir = root / "media" / "generated" / "photos"
    thumb_dir = root / "media" / "generated" / "thumbs"
    output_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    media.item_id = stable_id(media.source)
    full_path = output_dir / f"{media.item_id}.jpg"
    thumb_path = thumb_dir / f"{media.item_id}.jpg"
    if media.source.suffix.lower() in {".heic", ".heif"} and not HEIF_AVAILABLE:
        raise RuntimeError("Для HEIC нужен pillow-heif. Запусти tools/setup_mac.sh")
    with Image.open(media.source) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        analysis = image.copy()
        analysis.thumbnail((96, 96), Image.Resampling.LANCZOS)
        stat = ImageStat.Stat(analysis)
        media.avg_rgb = tuple(int(value) for value in stat.mean[:3])
        media.dhash = dhash(analysis)
        if not full_path.exists():
            full = image.copy()
            full.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            full.save(full_path, "JPEG", quality=88, optimize=True, progressive=True)
        if not thumb_path.exists():
            thumb = image.copy()
            thumb.thumbnail((640, 640), Image.Resampling.LANCZOS)
            thumb.save(thumb_path, "JPEG", quality=78, optimize=True, progressive=True)
    media.output_src = full_path.relative_to(root).as_posix()
    media.thumb_src = thumb_path.relative_to(root).as_posix()
    media.caption = format_item_caption(media.taken_at)
    return media


def ffprobe_duration(path: Path) -> float | None:
    if not command_exists("ffprobe") or not path.exists():
        return None
    try:
        result = run_json(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
        duration = float(result.get("format", {}).get("duration"))
        return duration if duration > 0 else None
    except Exception:
        return None


def ffmpeg_transcode(source: Path, destination: Path, settings: VideoSettings, live: bool = False) -> tuple[bool, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    max_width = settings.live_max_width if live else settings.max_width
    scale = f"scale='trunc(min({max_width},iw)/2)*2':-2:flags=lanczos"
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-vf", scale,
        "-c:v", "libx264", "-preset", settings.preset, "-crf", str(settings.crf + (2 if live else 0)),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-tag:v", "avc1",
        "-movflags", "+faststart", "-fps_mode", "vfr", "-map_metadata", "0",
    ]
    if live:
        cmd += ["-an", "-t", "6"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    cmd.append(str(destination))
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if completed.returncode != 0:
        return False, completed.stderr.strip()[-1200:]
    if not destination.exists() or destination.stat().st_size < 1024 or ffprobe_duration(destination) is None:
        return False, "FFmpeg создал пустой или нечитаемый файл"
    return True, ""


def ffmpeg_poster(source: Path, destination: Path, duration: float | None) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    seek = min(3.0, max(0.15, (duration or 2.0) * 0.08))
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.2f}", "-i", str(source),
        "-frames:v", "1", "-vf", "scale='trunc(min(960,iw)/2)*2':-2:flags=lanczos", "-q:v", "3", str(destination),
    ]
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.returncode == 0 and destination.exists() and destination.stat().st_size > 512


def convert_video(media: Media, root: Path, settings: VideoSettings, is_live: bool = False) -> tuple[str, str | None, float | None]:
    item_id = stable_id(media.source)
    output_dir = root / "media" / "generated" / ("live" if is_live else "videos")
    poster_dir = root / "media" / "generated" / "posters"
    destination = output_dir / f"{item_id}.mp4"
    poster = poster_dir / f"{item_id}.jpg"
    valid_existing = destination.exists() and destination.stat().st_size > 1024 and ffprobe_duration(destination)
    if not valid_existing:
        destination.unlink(missing_ok=True)
        ok, error = ffmpeg_transcode(media.source, destination, settings, live=is_live)
        if not ok:
            destination.unlink(missing_ok=True)
            raise RuntimeError(error or "неизвестная ошибка FFmpeg")
    duration = ffprobe_duration(destination) or media.duration
    if not is_live and not poster.exists():
        ffmpeg_poster(destination, poster, duration)
    return destination.relative_to(root).as_posix(), poster.relative_to(root).as_posix() if poster.exists() else None, duration


def process_media(media: list[Media], used_live_videos: set[Path], root: Path, workers: int, settings: VideoSettings) -> tuple[list[Media], list[dict[str, str]]]:
    images = [item for item in media if item.is_image]
    standalone_videos = [item for item in media if not item.is_image and item.source not in used_live_videos]
    errors: list[dict[str, str]] = []
    print(f"Фото: {len(images)}, обычные видео: {len(standalone_videos)}, Live Photo: {sum(bool(item.live_source) for item in images)}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        processed_images = list(pool.map(lambda item: analyze_and_convert_image(item, root), images))
    for index, image in enumerate(processed_images, 1):
        if image.live_source:
            try:
                live_media = Media(source=image.live_source, kind="video", taken_at=image.taken_at)
                image.live_output_src, _, _ = convert_video(live_media, root, settings, is_live=True)
            except RuntimeError as exc:
                errors.append({"file": str(image.live_source), "type": "live-photo-video", "error": str(exc)})
                image.live_output_src = None
        if index % 100 == 0:
            print(f"Обработано фото: {index}/{len(processed_images)}")
    processed_videos: list[Media] = []
    for index, video in enumerate(standalone_videos, 1):
        try:
            video.item_id = stable_id(video.source)
            video.output_src, video.poster_src, video.duration = convert_video(video, root, settings, is_live=False)
            video.caption = format_item_caption(video.taken_at)
            processed_videos.append(video)
        except RuntimeError as exc:
            errors.append({"file": str(video.source), "type": "video", "error": str(exc)})
            print(f"Не обработано видео: {video.source.name}: {exc}", file=sys.stderr)
        if index % 10 == 0:
            print(f"Обработано видео: {index}/{len(standalone_videos)}")
    return sorted(processed_images + processed_videos, key=lambda item: item.taken_at), errors


def haversine_km(a: Media, b: Media) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a.latitude, a.longitude, b.latitude, b.longitude])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def visual_similarity(a: Media, b: Media) -> float | None:
    if not a.is_image or not b.is_image or a.avg_rgb is None or b.avg_rgb is None or a.dhash is None or b.dhash is None:
        return None
    color_distance = math.sqrt(sum((x - y) ** 2 for x, y in zip(a.avg_rgb, b.avg_rgb))) / 441.67295593
    color_score = 1.0 - min(1.0, color_distance)
    hamming = (a.dhash ^ b.dhash).bit_count() / 64.0
    hash_score = 1.0 - hamming
    return 0.58 * color_score + 0.42 * hash_score


def should_join(previous: Media, current: Media, gap_minutes: int, merge_gap_minutes: int, threshold: float) -> bool:
    seconds = (current.taken_at - previous.taken_at).total_seconds()
    if seconds < 0:
        return False
    minutes = seconds / 60
    same_day = current.taken_at.date() == previous.taken_at.date()
    if minutes <= 18:
        return True
    if not same_day:
        return False
    distance = haversine_km(previous, current)
    similarity = visual_similarity(previous, current)
    if minutes <= gap_minutes:
        if distance is not None and distance <= 2.0:
            return True
        if similarity is not None and similarity >= threshold:
            return True
        return previous.kind == "video" or current.kind == "video"
    if minutes <= merge_gap_minutes:
        close_place = distance is not None and distance <= 0.45
        visually_close = similarity is not None and similarity >= min(0.97, threshold + 0.08)
        return close_place and visually_close
    return False


def group_events(items: list[Media], gap_minutes: int, merge_gap_minutes: int, threshold: float) -> list[Event]:
    if not items:
        return []
    groups: list[Event] = [Event(items=[items[0]])]
    for item in items[1:]:
        previous = groups[-1].items[-1]
        if should_join(previous, item, gap_minutes, merge_gap_minutes, threshold):
            groups[-1].items.append(item)
        else:
            groups.append(Event(items=[item]))
    return groups


def format_item_caption(value: dt.datetime) -> str:
    return f"{value.day} {RUS_MONTHS[value.month - 1]} {value.year}, {value:%H:%M}"


def format_event_title(event: Event) -> str:
    start = event.start
    if event.start.date() == event.end.date():
        return f"{start.day} {RUS_MONTHS[start.month - 1]} {start.year}"
    return f"{start.day} {RUS_MONTHS[start.month - 1]} — {event.end.day} {RUS_MONTHS[event.end.month - 1]} {event.end.year}"


def media_to_dict(media: Media) -> dict[str, Any]:
    common: dict[str, Any] = {
        "id": media.item_id,
        "src": media.output_src,
        "caption": media.caption,
        "takenAt": media.taken_at.isoformat(timespec="seconds"),
        "censored": False,
    }
    if media.is_image:
        common.update({"kind": "live" if media.live_output_src else "photo", "thumb": media.thumb_src, "liveVideo": media.live_output_src, "alt": "Фотография из воспоминаний"})
    else:
        common.update({"kind": "video", "poster": media.poster_src, "duration": round(media.duration, 3) if media.duration else None})
    return common


def build_book(events: list[Event]) -> dict[str, Any]:
    by_year: dict[int, list[Event]] = defaultdict(list)
    for event in events:
        by_year[event.start.year].append(event)
    chapters = []
    for chapter_index, year in enumerate(sorted(by_year)):
        blocks = []
        for event_index, event in enumerate(by_year[year]):
            blocks.append({
                "type": "event", "id": f"event-{year}-{event_index + 1:03d}", "title": format_event_title(event),
                "caption": "Добавь сюда одну короткую деталь об этом дне.", "date": event.start.isoformat(timespec="minutes"),
                "layout": "stack" if len(event.items) > 7 else "collage", "items": [media_to_dict(item) for item in event.items],
            })
        chapters.append({
            "id": f"year-{year}", "number": f"{chapter_index + 1:02d}", "kicker": "Глава по времени", "title": str(year),
            "subtitle": f"{len(by_year[year])} событий, собранных автоматически по датам, месту и визуальной близости.",
            "layout": LAYOUTS[chapter_index % len(LAYOUTS)], "theme": THEMES[chapter_index % len(THEMES)], "blocks": blocks,
        })
    return {
        "meta": {"eyebrow": "Личная книга воспоминаний", "title": "Наши три года", "subtitle": "Не идеальные. Настоящие.", "note": "Сначала собраны автоматически. Потом — поправлены вручную.", "footer": "Спасибо за всё, что было между первой и последней страницей.", "accent": "#9c3f43"},
        "chapters": chapters,
    }


def write_outputs(root: Path, book: dict[str, Any], report: dict[str, Any]) -> tuple[Path, Path]:
    content_dir = root / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    target = content_dir / "memories.js"
    if target.exists():
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(target, content_dir / f"memories.backup-{timestamp}.js")
    target.write_text("// Сгенерировано tools/import_memories.py. Редактируй через tools/studio.html.\nwindow.MEMORY_BOOK = " + json.dumps(book, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    report_path = content_dir / "import-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Импорт фотографий iPhone в локальную книгу воспоминаний")
    parser.add_argument("source", type=Path, help="Папка с экспортированными оригиналами из Фото")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Корень memory-site")
    parser.add_argument("--gap-minutes", type=int, default=75)
    parser.add_argument("--merge-gap-minutes", type=int, default=180)
    parser.add_argument("--visual-threshold", type=float, default=0.72)
    parser.add_argument("--workers", type=int, default=max(2, min(8, (os.cpu_count() or 4))))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--video-max-width", type=int, default=1920)
    parser.add_argument("--live-max-width", type=int, default=1080)
    parser.add_argument("--video-crf", type=int, default=23)
    parser.add_argument("--video-preset", default="veryfast", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    root = args.root.expanduser().resolve()
    if not source.is_dir():
        print(f"Папка не найдена: {source}", file=sys.stderr)
        return 2
    paths = scan_files(source)
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        print("Поддерживаемые фото и видео не найдены.", file=sys.stderr)
        return 2
    has_videos = any(path.suffix.lower() in VIDEO_EXTS for path in paths)
    if has_videos and (not command_exists("ffmpeg") or not command_exists("ffprobe")):
        print("Для видео обязательны ffmpeg и ffprobe. Запусти: zsh tools/setup_mac.sh", file=sys.stderr)
        return 2
    print(f"Найдено файлов: {len(paths)}")
    if not command_exists("exiftool"):
        print("Предупреждение: ExifTool не найден; группировка и Live Photo будут менее точными.")
    metadata = exiftool_metadata(paths)
    media = build_media(paths, metadata)
    media, used_live_videos = pair_live_photos(media)
    settings = VideoSettings(max_width=max(320, args.video_max_width), crf=min(35, max(16, args.video_crf)), preset=args.video_preset, live_max_width=max(320, args.live_max_width))
    processed, errors = process_media(media, used_live_videos, root, args.workers, settings)
    events = group_events(processed, args.gap_minutes, args.merge_gap_minutes, args.visual_threshold)
    report = {"createdAt": dt.datetime.now().isoformat(timespec="seconds"), "source": str(source), "foundFiles": len(paths), "importedItems": len(processed), "events": len(events), "errors": errors, "videoSettings": dataclasses.asdict(settings)}
    target, report_path = write_outputs(root, build_book(events), report)
    sizes = [len(event.items) for event in events]
    print(f"Событий: {len(events)}; медиана элементов: {sorted(sizes)[len(sizes)//2] if sizes else 0}; максимум: {max(sizes) if sizes else 0}")
    print(f"Готово: {target}")
    print(f"Отчёт: {report_path}")
    if errors:
        print(f"Внимание: не обработано файлов/Live-компонентов: {len(errors)}. Проверь import-report.json", file=sys.stderr)
    print("Открой tools/studio.html, поправь группы, поставь цензуру и экспортируй memories.js.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
