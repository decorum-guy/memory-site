#!/usr/bin/env python3
"""Безопасный интерфейс для импорта архива в Memory Site.

Режимы:
- dry-run: проверяет зависимости и каждый исходный файл без записи в проект;
- test: импортирует в изолированную .memory-test/site и проверяет результат;
- import: запускает полный production-импорт после preflight;
- reset: очищает тестовую область либо архивирует и сбрасывает production-результат.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "tools" / "import_memories.py"
TEST_HOME = ROOT / ".memory-test"
TEST_SITE = TEST_HOME / "site"
BACKUP_HOME = ROOT / ".memory-backups"

IMAGE_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
DATE_KEYS = ("DateTimeOriginal", "MediaCreateDate", "CreateDate", "TrackCreateDate")
CONTENT_ID_KEYS = ("ContentIdentifier", "QuickTime:ContentIdentifier", "MakerApple:ContentIdentifier")


@dataclass
class Problem:
    level: str
    file: str
    message: str


@dataclass
class PreflightResult:
    source: str
    total_files: int
    images: int
    videos: int
    live_pairs: int
    dated_files: int
    gps_files: int
    source_bytes: int
    estimated_required_bytes: int
    free_bytes: int
    extension_counts: dict[str, int]
    video_seconds: float
    problems: list[Problem]

    @property
    def errors(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.level == "error"]

    @property
    def warnings(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.level == "warning"]

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["errors"] = len(self.errors)
        data["warnings"] = len(self.warnings)
        return data


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def human_bytes(value: int) -> str:
    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    number = float(max(0, value))
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}" if unit != "Б" else f"{int(number)} {unit}"
        number /= 1024
    return f"{value} Б"


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def scan_files(source: Path, limit: int = 0) -> tuple[list[Path], list[Path]]:
    supported: list[Path] = []
    ignored: list[Path] = []
    for path in source.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in SUPPORTED_EXTS:
            supported.append(path)
        else:
            ignored.append(path)
    supported.sort(key=lambda path: (path.parent.as_posix().lower(), path.name.lower()))
    ignored.sort(key=lambda path: path.as_posix().lower())
    if limit > 0:
        supported = supported[:limit]
    return supported, ignored


def run_json(command: list[str]) -> Any:
    completed = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return json.loads(completed.stdout)


def load_metadata(paths: list[Path], problems: list[Problem]) -> dict[str, dict[str, Any]]:
    if not paths or not command_exists("exiftool"):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(paths), 180):
        chunk = paths[start:start + 180]
        command = [
            "exiftool", "-json", "-n", "-api", "QuickTimeUTC=1",
            "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate", "-TrackCreateDate",
            "-GPSLatitude", "-GPSLongitude", "-ContentIdentifier", "-Duration",
            *[str(path) for path in chunk],
        ]
        try:
            rows = run_json(command)
        except Exception as exc:
            problems.append(Problem("error", "ExifTool", f"Не удалось прочитать metadata группы файлов: {exc}"))
            continue
        for row in rows:
            source_file = row.get("SourceFile")
            if source_file:
                result[str(Path(source_file).resolve())] = row
    return result


def first_metadata_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    for row_key, value in lowered.items():
        if any(key.lower() in row_key for key in keys) and value not in (None, ""):
            return value
    return None


def verify_images(paths: list[Path], problems: list[Problem]) -> None:
    try:
        from PIL import Image
    except ImportError:
        problems.append(Problem("error", "Python", "Не установлен Pillow. Запусти: zsh tools/setup_mac.sh"))
        return

    has_heif = any(path.suffix.lower() in {".heic", ".heif"} for path in paths)
    if has_heif:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            problems.append(Problem("error", "HEIC", "Не установлен pillow-heif. Запусти: zsh tools/setup_mac.sh"))
            return

    for path in paths:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                if image.width < 1 or image.height < 1:
                    raise ValueError("нулевой размер изображения")
        except Exception as exc:
            problems.append(Problem("error", str(path), f"Изображение не читается: {exc}"))


def probe_videos(paths: list[Path], problems: list[Problem]) -> tuple[dict[str, float], float]:
    durations: dict[str, float] = {}
    total_seconds = 0.0
    if not paths:
        return durations, total_seconds
    if not command_exists("ffprobe"):
        problems.append(Problem("error", "ffprobe", "Для видео нужен ffprobe. Запусти: zsh tools/setup_mac.sh"))
        return durations, total_seconds

    for path in paths:
        try:
            data = run_json([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=index,codec_type,codec_name,width,height:format=duration,size",
                "-of", "json", str(path),
            ])
            video_streams = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"]
            if not video_streams:
                raise ValueError("не найден видеопоток")
            duration = float(data.get("format", {}).get("duration") or 0)
            if duration <= 0:
                raise ValueError("не удалось определить длительность")
            durations[str(path.resolve())] = duration
            total_seconds += duration
        except Exception as exc:
            problems.append(Problem("error", str(path), f"Видео не читается через ffprobe: {exc}"))
    return durations, total_seconds


def estimate_live_pairs(paths: list[Path], metadata: dict[str, dict[str, Any]]) -> int:
    images = [path for path in paths if path.suffix.lower() in IMAGE_EXTS]
    videos = [path for path in paths if path.suffix.lower() in VIDEO_EXTS]
    videos_by_id: dict[str, list[Path]] = defaultdict(list)
    videos_by_stem: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for video in videos:
        row = metadata.get(str(video.resolve()), {})
        content_id = str(first_metadata_value(row, CONTENT_ID_KEYS) or "").strip()
        if content_id:
            videos_by_id[content_id].append(video)
        videos_by_stem[(video.parent.as_posix().lower(), video.stem.lower())].append(video)
    used: set[Path] = set()
    pairs = 0
    for image in images:
        row = metadata.get(str(image.resolve()), {})
        content_id = str(first_metadata_value(row, CONTENT_ID_KEYS) or "").strip()
        candidates = videos_by_id.get(content_id, []) if content_id else []
        if not candidates:
            candidates = videos_by_stem.get((image.parent.as_posix().lower(), image.stem.lower()), [])
        candidate = next((path for path in candidates if path not in used), None)
        if candidate:
            used.add(candidate)
            pairs += 1
    return pairs


def run_preflight(source: Path, limit: int = 0) -> PreflightResult:
    problems: list[Problem] = []
    paths, ignored = scan_files(source, limit)
    images = [path for path in paths if path.suffix.lower() in IMAGE_EXTS]
    videos = [path for path in paths if path.suffix.lower() in VIDEO_EXTS]

    if not paths:
        problems.append(Problem("error", str(source), "Поддерживаемые фото и видео не найдены"))

    if not command_exists("exiftool"):
        problems.append(Problem("error", "ExifTool", "Не найден ExifTool. Запусти: zsh tools/setup_mac.sh"))
    if videos and not command_exists("ffmpeg"):
        problems.append(Problem("error", "FFmpeg", "Не найден FFmpeg. Запусти: zsh tools/setup_mac.sh"))

    verify_images(images, problems)
    _video_durations, total_video_seconds = probe_videos(videos, problems)
    metadata = load_metadata(paths, problems)

    dated_files = 0
    gps_files = 0
    for path in paths:
        row = metadata.get(str(path.resolve()), {})
        if first_metadata_value(row, DATE_KEYS):
            dated_files += 1
        if first_metadata_value(row, ("GPSLatitude",)) is not None and first_metadata_value(row, ("GPSLongitude",)) is not None:
            gps_files += 1

    if paths and dated_files == 0:
        problems.append(Problem("warning", "metadata", "ExifTool не нашёл даты ни в одном файле; импортёр возьмёт время изменения файлов"))
    elif paths and dated_files < int(len(paths) * 0.8):
        problems.append(Problem("warning", "metadata", f"Точная дата найдена только у {dated_files} из {len(paths)} файлов"))

    if ignored:
        examples = ", ".join(path.name for path in ignored[:5])
        problems.append(Problem("warning", str(source), f"Игнорируются неподдерживаемые файлы: {len(ignored)} шт. Например: {examples}"))

    source_bytes = sum(path.stat().st_size for path in paths if path.exists())
    estimated = max(2 * 1024**3, int(source_bytes * (2.2 if videos else 1.35)))
    free_bytes = shutil.disk_usage(ROOT).free
    if free_bytes < estimated:
        problems.append(Problem(
            "error", str(ROOT),
            f"Недостаточно свободного места: доступно {human_bytes(free_bytes)}, желательно минимум {human_bytes(estimated)}",
        ))
    elif free_bytes < estimated * 1.35:
        problems.append(Problem(
            "warning", str(ROOT),
            f"Свободного места мало с учётом запаса: {human_bytes(free_bytes)} при оценке {human_bytes(estimated)}",
        ))

    return PreflightResult(
        source=str(source),
        total_files=len(paths),
        images=len(images),
        videos=len(videos),
        live_pairs=estimate_live_pairs(paths, metadata),
        dated_files=dated_files,
        gps_files=gps_files,
        source_bytes=source_bytes,
        estimated_required_bytes=estimated,
        free_bytes=free_bytes,
        extension_counts=dict(sorted(Counter(path.suffix.lower() for path in paths).items())),
        video_seconds=total_video_seconds,
        problems=problems,
    )


def print_preflight(result: PreflightResult) -> None:
    print("\n=== MEMORY IMPORT · DRY RUN ===")
    print(f"Источник:          {result.source}")
    print(f"Файлов:            {result.total_files} ({result.images} фото, {result.videos} видео)")
    print(f"Live Photo пар:    {result.live_pairs}")
    print(f"С точной датой:    {result.dated_files}/{result.total_files}")
    print(f"С GPS:             {result.gps_files}/{result.total_files}")
    print(f"Видео суммарно:    {format_duration(result.video_seconds)}")
    print(f"Размер исходников: {human_bytes(result.source_bytes)}")
    print(f"Оценка места:      {human_bytes(result.estimated_required_bytes)}")
    print(f"Свободно:          {human_bytes(result.free_bytes)}")
    if result.extension_counts:
        print("Форматы:           " + ", ".join(f"{ext or '[без расширения]'}: {count}" for ext, count in result.extension_counts.items()))

    for level, title in (("error", "ОШИБКИ"), ("warning", "ПРЕДУПРЕЖДЕНИЯ")):
        items = [problem for problem in result.problems if problem.level == level]
        if items:
            print(f"\n{title} ({len(items)}):")
            for item in items:
                print(f"- {item.file}: {item.message}")

    if result.errors:
        print("\nРЕЗУЛЬТАТ: НЕ ГОТОВО. Исправь ошибки выше; импорт не запускался и проект не изменён.")
    else:
        suffix = f" Есть предупреждения: {len(result.warnings)}." if result.warnings else ""
        print(f"\nРЕЗУЛЬТАТ: ГОТОВО К ТЕСТОВОМУ ИМПОРТУ.{suffix}")


def common_engine_args(args: argparse.Namespace) -> list[str]:
    result = [
        "--gap-minutes", str(args.gap_minutes),
        "--merge-gap-minutes", str(args.merge_gap_minutes),
        "--visual-threshold", str(args.visual_threshold),
        "--workers", str(args.workers),
        "--video-max-width", str(args.video_max_width),
        "--live-max-width", str(args.live_max_width),
        "--video-crf", str(args.video_crf),
        "--video-preset", args.video_preset,
    ]
    if args.limit:
        result += ["--limit", str(args.limit)]
    return result


def project_ignore(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    ignored = {".git", ".github", ".memory-test", ".memory-venv", ".memory-backups", "node_modules", "__pycache__", ".DS_Store"}
    if path == ROOT:
        ignored.add("preview")
    if path.name == "media":
        ignored.add("generated")
    if path.name == "content":
        ignored.add("import-report.json")
        ignored.update(name for name in names if name.startswith("memories.backup-"))
    return {name for name in names if name in ignored or name.startswith("._")}


def prepare_test_workspace() -> Path:
    if TEST_SITE.exists():
        shutil.rmtree(TEST_SITE)
    TEST_HOME.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT, TEST_SITE, ignore=project_ignore)
    return TEST_SITE


def invoke_engine(source: Path, root: Path, args: argparse.Namespace) -> int:
    if not ENGINE.exists():
        print(f"Не найден движок импортёра: {ENGINE}", file=sys.stderr)
        return 2
    command = [sys.executable, str(ENGINE), str(source), "--root", str(root), *common_engine_args(args)]
    print("\nЗапуск:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    return subprocess.run(command).returncode


def extract_book(memories_path: Path) -> dict[str, Any]:
    text = memories_path.read_text(encoding="utf-8")
    match = re.search(r"window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$", text)
    if not match:
        raise ValueError("не найден объект window.MEMORY_BOOK")
    return json.loads(match.group(1))


def iter_media_values(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_media_values(item)
    elif isinstance(value, dict):
        if any(key in value for key in ("src", "thumb", "poster", "liveVideo")):
            yield value
        for child in value.values():
            yield from iter_media_values(child)


def validate_generated_site(site_root: Path) -> list[str]:
    errors: list[str] = []
    required = [site_root / "index.html", site_root / "content" / "memories.js", site_root / "content" / "import-report.json"]
    for path in required:
        if not path.exists():
            errors.append(f"Не создан обязательный файл: {path.relative_to(site_root)}")
    memories = site_root / "content" / "memories.js"
    if not memories.exists():
        return errors
    try:
        book = extract_book(memories)
    except Exception as exc:
        errors.append(f"memories.js не читается: {exc}")
        return errors

    seen: set[str] = set()
    for item in iter_media_values(book):
        for key in ("src", "thumb", "poster", "liveVideo"):
            raw = item.get(key)
            if not raw or raw in seen:
                continue
            seen.add(raw)
            path = Path(str(raw))
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"Небезопасный путь в memories.js: {raw}")
                continue
            if not (site_root / path).exists():
                errors.append(f"Сгенерированный файл не найден: {raw}")
    return errors


def open_path(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception as exc:
        print(f"Не удалось открыть браузер автоматически: {exc}")


def confirm(message: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Нужен флаг --yes для неинтерактивного запуска.", file=sys.stderr)
        return False
    answer = input(f"{message} [y/N]: ").strip().lower()
    return answer in {"y", "yes", "д", "да"}


def run_dry_run(args: argparse.Namespace) -> int:
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        print(f"Папка не найдена: {source}", file=sys.stderr)
        return 2
    result = run_preflight(source, args.limit)
    print_preflight(result)
    if args.json_report:
        report_path = args.json_report.expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON-отчёт: {report_path}")
    return 2 if result.errors else 0


def run_test(args: argparse.Namespace) -> int:
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        print(f"Папка не найдена: {source}", file=sys.stderr)
        return 2
    preflight = run_preflight(source, args.limit)
    print_preflight(preflight)
    if preflight.errors:
        print("\nТестовый импорт не запущен: dry-run нашёл ошибки.")
        return 2

    print(f"\nСоздаю изолированную тестовую копию: {TEST_SITE}")
    site = prepare_test_workspace()
    code = invoke_engine(source, site, args)
    validation_errors = validate_generated_site(site)

    report_path = site / "content" / "import-report.json"
    import_errors: list[Any] = []
    if report_path.exists():
        try:
            import_errors = json.loads(report_path.read_text(encoding="utf-8")).get("errors", [])
        except Exception as exc:
            validation_errors.append(f"Не читается import-report.json: {exc}")

    print("\n=== РЕЗУЛЬТАТ ТЕСТОВОГО ИМПОРТА ===")
    print(f"Тестовый сайт: {site / 'index.html'}")
    print(f"Отчёт:        {report_path}")
    print(f"Код движка:   {code}")
    print(f"Ошибок import-report: {len(import_errors)}")
    print(f"Ошибок структуры:     {len(validation_errors)}")
    for error in validation_errors[:30]:
        print(f"- {error}")

    if code == 0 and not import_errors and not validation_errors:
        print("\nРЕЗУЛЬТАТ: ТЕСТ ПРОЙДЕН. Production-файлы не изменены.")
        if args.open:
            open_path(site / "index.html")
        else:
            print(f"Открыть вручную: open \"{site / 'index.html'}\"")
        return 0

    print("\nРЕЗУЛЬТАТ: ТЕСТ НЕ ПРОЙДЕН. Не запускай полный импорт, пока ошибки не исправлены.", file=sys.stderr)
    return 1


def run_import(args: argparse.Namespace) -> int:
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        print(f"Папка не найдена: {source}", file=sys.stderr)
        return 2
    preflight = run_preflight(source, args.limit)
    print_preflight(preflight)
    if preflight.errors:
        print("\nProduction-импорт не запущен: dry-run нашёл ошибки.")
        return 2
    if not confirm("Полный импорт заменит content/memories.js и media/generated (memories.js будет сохранён в backup)", args.yes):
        print("Отменено.")
        return 0
    return invoke_engine(source, ROOT, args)


def minimal_reset_book() -> str:
    book = {
        "meta": {
            "eyebrow": "Личная книга воспоминаний",
            "title": "Наши три года",
            "subtitle": "Материалы ещё не импортированы",
            "note": "Запусти тестовый импорт, а затем полный импорт.",
            "footer": "Здесь появится финальная страница.",
            "accent": "#9c3f43",
        },
        "chapters": [],
    }
    return "// Чистое состояние после tools/import_workflow.py reset production.\nwindow.MEMORY_BOOK = " + json.dumps(book, ensure_ascii=False, indent=2) + ";\n"


def reset_test(assume_yes: bool) -> int:
    if not TEST_HOME.exists():
        print("Тестовая область уже чистая: .memory-test отсутствует.")
        return 0
    if not confirm(f"Удалить только тестовую область {TEST_HOME}?", assume_yes):
        print("Отменено.")
        return 0
    shutil.rmtree(TEST_HOME)
    print("Тестовая область удалена. Production-файлы не затронуты.")
    return 0


def reset_production(assume_yes: bool) -> int:
    if not assume_yes:
        print("Production-reset требует явного флага --yes.", file=sys.stderr)
        return 2
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_HOME / f"reset-{timestamp}"
    backup.mkdir(parents=True, exist_ok=False)

    targets = [ROOT / "content" / "memories.js", ROOT / "content" / "import-report.json"]
    for target in targets:
        if target.exists():
            destination = backup / target.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)

    generated = ROOT / "media" / "generated"
    if generated.exists():
        destination = backup / "media" / "generated"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(generated), str(destination))

    (ROOT / "content").mkdir(parents=True, exist_ok=True)
    (ROOT / "content" / "memories.js").write_text(minimal_reset_book(), encoding="utf-8")
    (ROOT / "content" / "import-report.json").unlink(missing_ok=True)
    print(f"Production-результат сброшен. Полная резервная копия: {backup}")
    return 0


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=0, help="Ограничить число файлов после сортировки; 0 = все")
    parser.add_argument("--gap-minutes", type=int, default=75)
    parser.add_argument("--merge-gap-minutes", type=int, default=180)
    parser.add_argument("--visual-threshold", type=float, default=0.72)
    parser.add_argument("--workers", type=int, default=max(2, min(8, os.cpu_count() or 4)))
    parser.add_argument("--video-max-width", type=int, default=1920)
    parser.add_argument("--live-max-width", type=int, default=1080)
    parser.add_argument("--video-crf", type=int, default=23)
    parser.add_argument("--video-preset", default="veryfast", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Безопасный dry-run, test, import и reset для Memory Site",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Быстрый сценарий:
              python3 tools/import_workflow.py dry-run ~/Desktop/test-photos
              python3 tools/import_workflow.py test ~/Desktop/test-photos --open
              python3 tools/import_workflow.py reset test --yes
              python3 tools/import_workflow.py import ~/Desktop/all-photos --yes
        """),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser("dry-run", aliases=["dryrun"], help="Проверка без записи файлов")
    dry.add_argument("source", type=Path)
    dry.add_argument("--json-report", type=Path, help="Необязательно сохранить JSON-отчёт в указанный путь")
    add_common_options(dry)
    dry.set_defaults(handler=run_dry_run)

    test = subparsers.add_parser("test", help="Изолированный импорт в .memory-test/site")
    test.add_argument("source", type=Path)
    test.add_argument("--open", action="store_true", help="Открыть тестовый index.html после успешного импорта")
    add_common_options(test)
    test.set_defaults(handler=run_test)

    production = subparsers.add_parser("import", help="Полный production-импорт")
    production.add_argument("source", type=Path)
    production.add_argument("--yes", action="store_true", help="Не задавать вопрос перед перезаписью")
    add_common_options(production)
    production.set_defaults(handler=run_import)

    reset = subparsers.add_parser("reset", help="Сброс тестовой области или production-результата")
    reset.add_argument("scope", choices=["test", "production"], nargs="?", default="test")
    reset.add_argument("--yes", action="store_true")
    reset.set_defaults(handler=lambda args: reset_test(args.yes) if args.scope == "test" else reset_production(args.yes))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
