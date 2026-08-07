#!/usr/bin/env python3
"""Adds offline-ready location labels to an imported Memory Site book.

The source archive is scanned locally with ExifTool. Existing textual location
metadata is preferred. GPS-only items are reverse-geocoded once through the
macOS Core Location service, cached locally, and written into memories.js as
plain text. The final book never performs network requests for locations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

IMAGE_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
CACHE_VERSION = 1
CACHE_PRECISION = 3

TEXT_LOCATION_TAGS = [
    "Sub-location",
    "Location",
    "City",
    "Province-State",
    "Country-PrimaryLocationName",
    "Country",
    "LocationCreatedLocationName",
    "LocationCreatedSublocation",
    "LocationCreatedCity",
    "LocationCreatedProvinceState",
    "LocationCreatedCountryName",
    "LocationShownLocationName",
    "LocationShownSublocation",
    "LocationShownCity",
    "LocationShownProvinceState",
    "LocationShownCountryName",
]


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def stable_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:14]


def scan_files(source: Path) -> list[Path]:
    return sorted(
        (path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS),
        key=lambda path: (path.parent.as_posix().lower(), path.name.lower()),
    )


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def first_value(mapping: dict[str, Any], names: Iterable[str]) -> Any:
    normalized = {normalize_key(str(key)): value for key, value in mapping.items()}
    wanted = [normalize_key(name) for name in names]
    for name in wanted:
        value = normalized.get(name)
        if value not in (None, ""):
            return value
    for key, value in normalized.items():
        if value not in (None, "") and any(name in key or key in name for name in wanted):
            return value
    return None


def read_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    if not command_exists("exiftool"):
        raise RuntimeError("Не найден ExifTool. Запусти: zsh tools/setup_mac.sh")
    result: dict[str, dict[str, Any]] = {}
    requested = ["-GPSLatitude", "-GPSLongitude", *[f"-{tag}" for tag in TEXT_LOCATION_TAGS]]
    for start in range(0, len(paths), 180):
        chunk = paths[start:start + 180]
        completed = subprocess.run(
            ["exiftool", "-json", "-n", "-api", "QuickTimeUTC=1", *requested, *[str(path) for path in chunk]],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for row in json.loads(completed.stdout):
            source_file = row.get("SourceFile")
            if source_file:
                result[str(Path(source_file).resolve())] = row
    return result


def clean_location_part(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,;·")
    if not text:
        return ""
    # Reject coordinate-looking values and technical placeholders.
    if re.fullmatch(r"[-+\d.,°'\" NSEW]+", text, flags=re.IGNORECASE):
        return ""
    if text.lower() in {"unknown", "неизвестно", "none", "null"}:
        return ""
    return text


def unique_parts(*values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        part = clean_location_part(value)
        key = part.casefold()
        if part and key not in seen:
            seen.add(key)
            result.append(part)
    return result


def metadata_location(row: dict[str, Any]) -> str:
    place = first_value(row, [
        "LocationCreatedLocationName", "LocationShownLocationName",
        "LocationCreatedSublocation", "LocationShownSublocation",
        "Sub-location", "Location",
    ])
    city = first_value(row, ["LocationCreatedCity", "LocationShownCity", "City"])
    region = first_value(row, [
        "LocationCreatedProvinceState", "LocationShownProvinceState", "Province-State",
    ])
    country = first_value(row, [
        "LocationCreatedCountryName", "LocationShownCountryName",
        "Country-PrimaryLocationName", "Country",
    ])
    parts = unique_parts(place, city, region, country)
    return ", ".join(parts[:3])


def parse_book(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MEMORY_BOOK\s*=\s*([\s\S]*);\s*$", text)
    if not match:
        raise ValueError("не найден объект window.MEMORY_BOOK")
    value = json.loads(match.group(1))
    if not isinstance(value, dict) or not isinstance(value.get("chapters"), list):
        raise ValueError("неверная структура memories.js")
    return value


def iter_media(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_media(item)
    elif isinstance(value, dict):
        if value.get("id") and any(key in value for key in ("src", "thumb", "poster", "liveVideo")):
            yield value
        for child in value.values():
            yield from iter_media(child)


def cache_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.{CACHE_PRECISION}f},{longitude:.{CACHE_PRECISION}f}"


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": CACHE_VERSION, "precision": CACHE_PRECISION, "locale": "ru_RU", "entries": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") == CACHE_VERSION and isinstance(value.get("entries"), dict):
            return value
    except Exception:
        pass
    return {"version": CACHE_VERSION, "precision": CACHE_PRECISION, "locale": "ru_RU", "entries": {}}


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def format_geocoder_result(value: dict[str, Any]) -> str:
    interests = value.get("areasOfInterest") if isinstance(value.get("areasOfInterest"), list) else []
    point = next((clean_location_part(item) for item in interests if clean_location_part(item)), "")
    water = clean_location_part(value.get("inlandWater") or value.get("ocean"))
    locality = clean_location_part(value.get("locality"))
    sublocality = clean_location_part(value.get("subLocality"))
    area = clean_location_part(value.get("subAdministrativeArea") or value.get("administrativeArea"))
    country = clean_location_part(value.get("country"))

    if point:
        return ", ".join(unique_parts(point, locality or area, country)[:3])
    if water:
        return ", ".join(unique_parts(water, locality or area, country)[:3])
    if sublocality and locality:
        return ", ".join(unique_parts(sublocality, locality, country)[:3])
    if locality:
        return ", ".join(unique_parts(locality, country)[:2])
    if area:
        return ", ".join(unique_parts(area, country)[:2])
    name = clean_location_part(value.get("name"))
    return ", ".join(unique_parts(name, country)[:2])


def ensure_geocoder_binary(root: Path) -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("Автоматический геокодер доступен только на macOS")
    if not command_exists("xcrun"):
        raise RuntimeError("Не найден xcrun. Установи Command Line Tools: xcode-select --install")
    source = root / "tools" / "macos_reverse_geocoder.swift"
    if not source.is_file():
        raise RuntimeError(f"Не найден Swift-геокодер: {source}")
    tools_dir = root / ".memory-tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    binary = tools_dir / "macos-reverse-geocoder"
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    print("Собираю локальный геокодер macOS…")
    completed = subprocess.run(
        ["xcrun", "swiftc", "-O", str(source), "-o", str(binary), "-framework", "CoreLocation"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("Не удалось собрать геокодер:\n" + completed.stderr[-3000:])
    return binary


def run_geocoder_batch(binary: Path, requests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not requests:
        return {}
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests)
    completed = subprocess.run(
        [str(binary)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(90, len(requests) * 12),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"геокодер завершился с кодом {completed.returncode}")
    result: dict[str, dict[str, Any]] = {}
    for line in completed.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = str(value.get("key") or "")
        if key:
            result[key] = value
    return result


def reverse_geocode_missing(root: Path, requests: dict[str, tuple[float, float]], cache_path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    cache = load_cache(cache_path)
    entries: dict[str, Any] = cache["entries"]
    locations: dict[str, str] = {}
    errors: list[dict[str, str]] = []

    for key in requests:
        cached = entries.get(key)
        if isinstance(cached, dict) and clean_location_part(cached.get("location")):
            locations[key] = clean_location_part(cached["location"])

    pending = [
        {"key": key, "latitude": coordinates[0], "longitude": coordinates[1]}
        for key, coordinates in requests.items()
        if key not in locations
    ]
    if not pending:
        return locations, errors

    binary = ensure_geocoder_binary(root)
    total = len(pending)
    for start in range(0, total, 40):
        chunk = pending[start:start + 40]
        try:
            responses = run_geocoder_batch(binary, chunk)
        except Exception as exc:
            errors.append({"key": chunk[0]["key"], "error": str(exc)})
            continue

        retry: list[dict[str, Any]] = []
        for request in chunk:
            key = request["key"]
            response = responses.get(key)
            if not response or response.get("error"):
                retry.append(request)
                continue
            location = format_geocoder_result(response)
            if location:
                locations[key] = location
                entries[key] = {"location": location, "result": response}

        if retry:
            time.sleep(3)
            try:
                retry_responses = run_geocoder_batch(binary, retry)
            except Exception as exc:
                retry_responses = {}
                errors.append({"key": retry[0]["key"], "error": str(exc)})
            for request in retry:
                key = request["key"]
                response = retry_responses.get(key)
                location = format_geocoder_result(response or {}) if response and not response.get("error") else ""
                if location:
                    locations[key] = location
                    entries[key] = {"location": location, "result": response}
                else:
                    errors.append({"key": key, "error": str((response or {}).get("error") or "место не определено")})

        save_cache(cache_path, cache)
        print(f"Геокодирование: {min(start + len(chunk), total)}/{total} уникальных мест")
        if start + len(chunk) < total:
            time.sleep(2)

    return locations, errors


def write_book(path: Path, book: dict[str, Any]) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"memories.before-location-{timestamp}.js")
    shutil.copy2(path, backup)
    content = (
        "// Сгенерировано tools/import_memories.py и дополнено tools/location_enrichment.py.\n"
        "// Редактируй через tools/studio.html.\n"
        "window.MEMORY_BOOK = " + json.dumps(book, ensure_ascii=False, indent=2) + ";\n"
    )
    path.write_text(content, encoding="utf-8")
    return backup


def enrich(args: argparse.Namespace) -> int:
    source = args.source.expanduser().resolve()
    root = args.root.expanduser().resolve()
    memories_path = root / "content" / "memories.js"
    cache_path = root / ".memory-location-cache.json"
    if not source.is_dir():
        print(f"Папка исходников не найдена: {source}", file=sys.stderr)
        return 2
    if not memories_path.is_file():
        print(f"Сначала выполни импорт: не найден {memories_path}", file=sys.stderr)
        return 2

    try:
        book = parse_book(memories_path)
    except Exception as exc:
        print(f"Не удалось прочитать memories.js: {exc}", file=sys.stderr)
        return 2

    items = {str(item.get("id")): item for item in iter_media(book) if item.get("id")}
    paths = scan_files(source)
    matching = [path for path in paths if stable_id(path) in items]
    print(f"Локации: найдено {len(matching)} исходников для {len(items)} элементов книги")

    try:
        metadata = read_metadata(matching)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    records: dict[str, dict[str, Any]] = {}
    geocode_requests: dict[str, tuple[float, float]] = {}
    for path in matching:
        item_id = stable_id(path)
        row = metadata.get(str(path.resolve()), {})
        latitude = first_value(row, ["GPSLatitude"])
        longitude = first_value(row, ["GPSLongitude"])
        lat = float(latitude) if latitude not in (None, "") else None
        lon = float(longitude) if longitude not in (None, "") else None
        location = metadata_location(row)
        key = cache_key(lat, lon) if lat is not None and lon is not None else ""
        records[item_id] = {"lat": lat, "lon": lon, "location": location, "key": key}
        if key and not location:
            geocode_requests.setdefault(key, (lat, lon))

    geocoded: dict[str, str] = {}
    geocode_errors: list[dict[str, str]] = []
    if geocode_requests and not args.no_geocode:
        try:
            geocoded, geocode_errors = reverse_geocode_missing(root, geocode_requests, cache_path)
        except Exception as exc:
            print(f"Предупреждение: автоматическое геокодирование недоступно: {exc}", file=sys.stderr)
            geocode_errors.append({"key": "geocoder", "error": str(exc)})

    with_gps = 0
    with_location = 0
    metadata_locations = 0
    geocoded_locations = 0
    preserved_manual = 0
    for item_id, record in records.items():
        item = items.get(item_id)
        if not item:
            continue
        lat, lon = record["lat"], record["lon"]
        if lat is not None and lon is not None:
            item["gps"] = {"lat": round(lat, 6), "lon": round(lon, 6)}
            with_gps += 1

        existing = clean_location_part(item.get("location"))
        if existing and not args.overwrite:
            preserved_manual += 1
            with_location += 1
            continue
        location = clean_location_part(record["location"])
        if location:
            metadata_locations += 1
        elif record["key"]:
            location = clean_location_part(geocoded.get(record["key"]))
            if location:
                geocoded_locations += 1
        if location:
            item["location"] = location
            with_location += 1
        else:
            item.pop("location", None)

    backup = write_book(memories_path, book)
    report = {
        "createdAt": dt.datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        "root": str(root),
        "bookItems": len(items),
        "matchedSources": len(matching),
        "itemsWithGps": with_gps,
        "itemsWithLocation": with_location,
        "locationsFromMetadata": metadata_locations,
        "locationsFromMacOS": geocoded_locations,
        "preservedManualLocations": preserved_manual,
        "unresolvedGpsItems": max(0, with_gps - with_location),
        "geocoderErrors": geocode_errors,
        "cache": str(cache_path),
    }
    report_path = root / "content" / "location-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"GPS сохранён:       {with_gps}")
    print(f"Названия мест:      {with_location}")
    print(f"Из metadata:        {metadata_locations}")
    print(f"Через macOS:        {geocoded_locations}")
    print(f"Без названия:       {max(0, with_gps - with_location)}")
    print(f"Готово:             {memories_path}")
    print(f"Резервная копия:    {backup}")
    print(f"Отчёт:              {report_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Добавить названия мест в импортированную книгу")
    parser.add_argument("source", type=Path, help="Папка с оригиналами, использованная при импорте")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Корень production или test-сайта")
    parser.add_argument("--no-geocode", action="store_true", help="Не обращаться к геокодеру macOS; использовать только metadata")
    parser.add_argument("--overwrite", action="store_true", help="Перезаписать уже заполненные вручную названия мест")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(enrich(parse_args()))
