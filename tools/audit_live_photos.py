#!/usr/bin/env python3
"""Audit an Apple Photos export for renamed, ambiguous and orphan Live Photos.

The command is read-only: it never renames, moves or edits source files. It
uses Apple ContentIdentifier as the strongest signal and produces JSON, CSV and
an offline HTML report with the much smaller set of groups worth reviewing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from live_photo_pairing import (
    FALLBACK_MAX_SECONDS,
    copy_family_key,
    copy_family_stem,
    parse_metadata_datetime,
    stem_key,
)

IMAGE_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS
DATE_KEYS = ("DateTimeOriginal", "MediaCreateDate", "CreateDate", "TrackCreateDate")
CONTENT_ID_KEYS = ("ContentIdentifier", "QuickTime:ContentIdentifier", "MakerApple:ContentIdentifier")


@dataclass(frozen=True)
class Record:
    path: Path
    relative: str
    kind: str
    content_id: str
    taken_at: dt.datetime
    duration: float | None

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def family_stem(self) -> str:
        return copy_family_stem(self.path.stem)

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "relative": self.relative,
            "kind": self.kind,
            "stem": self.stem,
            "familyStem": self.family_stem,
            "contentIdentifier": self.content_id or None,
            "takenAt": self.taken_at.isoformat(timespec="seconds"),
            "duration": round(self.duration, 3) if self.duration is not None else None,
        }


def first_value(mapping: dict[str, Any], names: Iterable[str]) -> Any:
    lowered = {str(key).lower(): value for key, value in mapping.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    for key, value in lowered.items():
        if value not in (None, "") and any(name.lower() in key for name in names):
            return value
    return None


def scan_files(source: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in source.rglob("*")
            if path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in SUPPORTED_EXTS
        ),
        key=lambda path: (path.parent.as_posix().casefold(), path.name.casefold()),
    )


def load_metadata(paths: list[Path]) -> dict[str, dict[str, Any]]:
    if not shutil.which("exiftool"):
        raise RuntimeError("Не найден ExifTool. Запусти: zsh tools/setup_mac.sh")
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(paths), 180):
        chunk = paths[start:start + 180]
        command = [
            "exiftool", "-json", "-n", "-api", "QuickTimeUTC=1",
            "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate", "-TrackCreateDate",
            "-ContentIdentifier", "-Duration",
            *[str(path) for path in chunk],
        ]
        completed = subprocess.run(
            command,
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


def build_records(source: Path, paths: list[Path], metadata: dict[str, dict[str, Any]]) -> list[Record]:
    records: list[Record] = []
    for path in paths:
        resolved = path.resolve()
        row = metadata.get(str(resolved), {})
        fallback = dt.datetime.fromtimestamp(path.stat().st_mtime)
        taken_at = parse_metadata_datetime(first_value(row, DATE_KEYS), fallback)
        content_id = str(first_value(row, CONTENT_ID_KEYS) or "").strip()
        raw_duration = first_value(row, ("Duration",))
        try:
            duration = float(raw_duration) if raw_duration not in (None, "") else None
        except (TypeError, ValueError):
            duration = None
        records.append(Record(
            path=resolved,
            relative=resolved.relative_to(source).as_posix(),
            kind="image" if path.suffix.lower() in IMAGE_EXTS else "video",
            content_id=content_id,
            taken_at=taken_at,
            duration=duration,
        ))
    return records


def pair_dict(image: Record, video: Record, method: str) -> dict[str, Any]:
    seconds = abs((video.taken_at - image.taken_at).total_seconds())
    return {
        "method": method,
        "image": image.to_json(),
        "video": video.to_json(),
        "contentIdentifier": image.content_id or video.content_id or None,
        "stemsDiffer": image.stem.casefold() != video.stem.casefold(),
        "sameCopyFamily": copy_family_key(image.path) == copy_family_key(video.path),
        "timeDifferenceSeconds": round(seconds, 3),
    }


def analyze(records: list[Record]) -> dict[str, Any]:
    images = [record for record in records if record.kind == "image"]
    videos = [record for record in records if record.kind == "video"]

    images_by_id: dict[str, list[Record]] = defaultdict(list)
    videos_by_id: dict[str, list[Record]] = defaultdict(list)
    images_by_stem: dict[tuple[str, str], list[Record]] = defaultdict(list)
    videos_by_stem: dict[tuple[str, str], list[Record]] = defaultdict(list)
    records_by_family: dict[tuple[str, str], list[Record]] = defaultdict(list)

    for record in records:
        records_by_family[copy_family_key(record.path)].append(record)
        if record.kind == "image":
            images_by_stem[stem_key(record.path)].append(record)
            if record.content_id:
                images_by_id[record.content_id].append(record)
        else:
            videos_by_stem[stem_key(record.path)].append(record)
            if record.content_id:
                videos_by_id[record.content_id].append(record)

    exact_pairs: list[dict[str, Any]] = []
    renamed_exact_pairs: list[dict[str, Any]] = []
    ambiguous_ids: list[dict[str, Any]] = []
    paired_images: set[Path] = set()
    paired_videos: set[Path] = set()

    for content_id in sorted(set(images_by_id) & set(videos_by_id)):
        image_group = images_by_id[content_id]
        video_group = videos_by_id[content_id]
        if len(image_group) == 1 and len(video_group) == 1:
            pair = pair_dict(image_group[0], video_group[0], "contentIdentifier")
            exact_pairs.append(pair)
            if pair["stemsDiffer"]:
                renamed_exact_pairs.append(pair)
            paired_images.add(image_group[0].path)
            paired_videos.add(video_group[0].path)
        else:
            ambiguous_ids.append({
                "contentIdentifier": content_id,
                "images": [record.to_json() for record in image_group],
                "videos": [record.to_json() for record in video_group],
                "reason": "Один ContentIdentifier относится не к одной картинке и одному видео",
            })

    collision_families = {
        key
        for key, group in records_by_family.items()
        if len({record.stem.casefold() for record in group}) > 1
    }

    safe_filename_pairs: list[dict[str, Any]] = []
    for key, image_group in images_by_stem.items():
        video_group = videos_by_stem.get(key, [])
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if image.path in paired_images or video.path in paired_videos:
            continue
        if image.content_id or video.content_id:
            continue
        if copy_family_key(image.path) in collision_families:
            continue
        seconds = abs((video.taken_at - image.taken_at).total_seconds())
        if seconds > FALLBACK_MAX_SECONDS:
            continue
        safe_filename_pairs.append(pair_dict(image, video, "safeFilenameFallback"))
        paired_images.add(image.path)
        paired_videos.add(video.path)

    suspicious_families: list[dict[str, Any]] = []
    for key in sorted(collision_families):
        group = sorted(records_by_family[key], key=lambda record: (record.taken_at, record.relative.casefold()))
        group_images = [record for record in group if record.kind == "image"]
        group_videos = [record for record in group if record.kind == "video"]
        if not group_images or not group_videos:
            continue
        unresolved_images = [record for record in group_images if record.path not in paired_images]
        unresolved_videos = [record for record in group_videos if record.path not in paired_videos]
        candidates: list[dict[str, Any]] = []
        for video in unresolved_videos:
            ranked = sorted(
                unresolved_images,
                key=lambda image: abs((video.taken_at - image.taken_at).total_seconds()),
            )
            for image in ranked[:3]:
                seconds = abs((video.taken_at - image.taken_at).total_seconds())
                if seconds <= 600:
                    candidates.append(pair_dict(image, video, "manualCandidate"))
        suspicious_families.append({
            "folder": group[0].path.parent.as_posix(),
            "familyStem": group[0].family_stem,
            "files": [record.to_json() for record in group],
            "unresolved": bool(unresolved_images and unresolved_videos),
            "manualCandidates": candidates,
        })

    orphan_image_ids = [
        {
            "contentIdentifier": content_id,
            "images": [record.to_json() for record in group],
        }
        for content_id, group in sorted(images_by_id.items())
        if content_id not in videos_by_id
    ]
    orphan_video_ids = [
        {
            "contentIdentifier": content_id,
            "videos": [record.to_json() for record in group],
        }
        for content_id, group in sorted(videos_by_id.items())
        if content_id not in images_by_id
    ]

    likely_orphan_live_videos = [
        record.to_json()
        for record in videos
        if record.path not in paired_videos
        and record.duration is not None
        and record.duration <= 6.5
        and (record.content_id or copy_family_key(record.path) in collision_families)
    ]

    unresolved_families = [family for family in suspicious_families if family["unresolved"]]
    return {
        "summary": {
            "files": len(records),
            "images": len(images),
            "videos": len(videos),
            "exactContentIdentifierPairs": len(exact_pairs),
            "renamedExactPairs": len(renamed_exact_pairs),
            "safeFilenameFallbackPairs": len(safe_filename_pairs),
            "ambiguousContentIdentifiers": len(ambiguous_ids),
            "copyNameCollisionFamilies": len(suspicious_families),
            "unresolvedCollisionFamilies": len(unresolved_families),
            "orphanImageIdentifiers": len(orphan_image_ids),
            "orphanVideoIdentifiers": len(orphan_video_ids),
            "likelyOrphanLiveVideos": len(likely_orphan_live_videos),
            "pairedLivePhotos": len(exact_pairs) + len(safe_filename_pairs),
        },
        "renamedExactPairs": renamed_exact_pairs,
        "exactPairs": exact_pairs,
        "safeFilenameFallbackPairs": safe_filename_pairs,
        "ambiguousContentIdentifiers": ambiguous_ids,
        "copyNameCollisionFamilies": suspicious_families,
        "orphanImageIdentifiers": orphan_image_ids,
        "orphanVideoIdentifiers": orphan_video_ids,
        "likelyOrphanLiveVideos": likely_orphan_live_videos,
    }


def csv_rows(report: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add_pair(category: str, pair: dict[str, Any], note: str) -> None:
        rows.append({
            "category": category,
            "confidence": "high" if pair["method"] == "contentIdentifier" else "medium",
            "image": pair["image"]["relative"],
            "video": pair["video"]["relative"],
            "content_identifier": str(pair.get("contentIdentifier") or ""),
            "time_difference_seconds": str(pair.get("timeDifferenceSeconds") or ""),
            "note": note,
        })

    for pair in report["renamedExactPairs"]:
        add_pair("renamed_exact_pair", pair, "Надёжная пара по Apple ID; имена различаются")
    for pair in report["safeFilenameFallbackPairs"]:
        add_pair("safe_filename_pair", pair, "Нет Apple ID, но имя и время совпадают без конфликта копий")
    for family in report["copyNameCollisionFamilies"]:
        rows.append({
            "category": "copy_name_collision",
            "confidence": "review",
            "image": ", ".join(file["relative"] for file in family["files"] if file["kind"] == "image"),
            "video": ", ".join(file["relative"] for file in family["files"] if file["kind"] == "video"),
            "content_identifier": "",
            "time_difference_seconds": "",
            "note": "Нужна проверка" if family["unresolved"] else "Связь уже восстановлена по Apple ID",
        })
    for group in report["ambiguousContentIdentifiers"]:
        rows.append({
            "category": "ambiguous_content_identifier",
            "confidence": "review",
            "image": ", ".join(file["relative"] for file in group["images"]),
            "video": ", ".join(file["relative"] for file in group["videos"]),
            "content_identifier": group["contentIdentifier"],
            "time_difference_seconds": "",
            "note": group["reason"],
        })
    return rows


def render_html(source: Path, report: dict[str, Any]) -> str:
    summary = report["summary"]

    def file_link(file: dict[str, Any]) -> str:
        uri = Path(file["path"]).as_uri()
        label = html.escape(file["relative"])
        cid = html.escape(str(file.get("contentIdentifier") or "нет ID"))
        return f'<li><a href="{html.escape(uri)}">{label}</a><small>{html.escape(file["kind"])} · {cid} · {html.escape(file["takenAt"])}</small></li>'

    renamed_cards = "".join(
        "<article><h3>Связь восстановлена автоматически</h3><ul>"
        + file_link(pair["image"])
        + file_link(pair["video"])
        + "</ul><p>Точный общий Apple ContentIdentifier; переименовывать файлы не требуется.</p></article>"
        for pair in report["renamedExactPairs"]
    ) or "<p class='empty'>Переименованных, но надёжно восстановленных пар не найдено.</p>"

    collision_cards = "".join(
        "<article class='warning'><h3>"
        + html.escape(family["familyStem"])
        + (" — проверить" if family["unresolved"] else " — уже восстановлено")
        + "</h3><ul>"
        + "".join(file_link(file) for file in family["files"])
        + "</ul>"
        + (
            "<p>Автосвязь по имени запрещена. Смотри предложенные пары в JSON/CSV или проверяй только эту группу.</p>"
            if family["unresolved"]
            else "<p>Конфликт имён есть, но точный Apple ID уже определил настоящую пару.</p>"
        )
        + "</article>"
        for family in report["copyNameCollisionFamilies"]
    ) or "<p class='empty'>Конфликтов имён с видео не найдено.</p>"

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Аудит Live Photos</title>
<style>
:root{{--bg:#f3eee5;--card:#fffaf2;--ink:#2d2925;--muted:#756b60;--line:#d8cab7;--good:#295f46;--warn:#8b4a31}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{width:min(1100px,calc(100% - 32px));margin:32px auto 80px}}h1{{font:700 clamp(2rem,5vw,4rem) Georgia,serif;margin:.2rem 0}}.source{{color:var(--muted);word-break:break-all}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}.metric,article{{background:var(--card);border:1px solid var(--line);padding:16px;box-shadow:0 8px 24px rgba(50,38,25,.06)}}.metric b{{display:block;font-size:1.8rem}}.metric span,small{{display:block;color:var(--muted)}}section{{margin-top:36px}}h2{{font:700 1.6rem Georgia,serif}}article{{margin:12px 0}}article.warning{{border-left:5px solid var(--warn)}}article h3{{margin:0 0 8px}}ul{{margin:0;padding-left:20px}}li{{margin:8px 0}}a{{color:#3f6287;word-break:break-all}}p{{margin:.7rem 0 0}}.empty{{color:var(--muted)}}code{{background:#e8dfd2;padding:.15rem .35rem}}
</style></head><body><main>
<p>READ-ONLY REPORT</p><h1>Аудит Live Photos</h1><p class="source">{html.escape(str(source))}</p>
<div class="summary">
<div class="metric"><b>{summary['pairedLivePhotos']}</b><span>надёжных Live Photos</span></div>
<div class="metric"><b>{summary['renamedExactPairs']}</b><span>пар с разными именами</span></div>
<div class="metric"><b>{summary['unresolvedCollisionFamilies']}</b><span>групп на ручную проверку</span></div>
<div class="metric"><b>{summary['likelyOrphanLiveVideos']}</b><span>вероятных одиноких MOV</span></div>
</div>
<section><h2>Переименованные пары, восстановленные по Apple ID</h2>{renamed_cards}</section>
<section><h2>Семейства с конфликтами имён</h2>{collision_cards}</section>
<section><h2>Как читать отчёт</h2><article><p>Зелёный сценарий — HEIC и MOV имеют один уникальный <code>ContentIdentifier</code>: имена могут различаться, импортёр всё равно объединит их. Группы «проверить» не объединяются автоматически и не теряют ни одного файла.</p></article></section>
</main></body></html>"""


def write_reports(source: Path, output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "createdAt": dt.datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        **report,
    }
    json_path = output_dir / "live-photo-audit.json"
    csv_path = output_dir / "live-photo-audit.csv"
    html_path = output_dir / "live-photo-audit.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = csv_rows(report)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "category", "confidence", "image", "video", "content_identifier",
            "time_difference_seconds", "note",
        ])
        writer.writeheader()
        writer.writerows(rows)
    html_path.write_text(render_html(source, report), encoding="utf-8")
    return json_path, csv_path, html_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверка конфликтов и переименованных компонентов Live Photo")
    parser.add_argument("source", type=Path, help="Папка с экспортированными оригиналами")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".memory-audit",
        help="Куда записать HTML/JSON/CSV отчёт",
    )
    parser.add_argument("--open", action="store_true", help="Открыть HTML-отчёт после проверки")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not source.is_dir():
        print(f"Папка не найдена: {source}", file=sys.stderr)
        return 2

    paths = scan_files(source)
    if not paths:
        print("Поддерживаемые фото и видео не найдены.", file=sys.stderr)
        return 2

    print("\n=== LIVE PHOTO AUDIT · READ ONLY ===")
    print(f"Источник: {source}")
    print(f"Файлов:   {len(paths)}")
    try:
        metadata = load_metadata(paths)
    except Exception as exc:
        print(f"Не удалось прочитать metadata: {exc}", file=sys.stderr)
        return 2

    records = build_records(source, paths, metadata)
    report = analyze(records)
    json_path, csv_path, html_path = write_reports(source, output_dir, report)
    summary = report["summary"]

    print(f"Надёжных Live Photo:             {summary['pairedLivePhotos']}")
    print(f"Переименованных точных пар:      {summary['renamedExactPairs']}")
    print(f"Безопасных пар только по имени:  {summary['safeFilenameFallbackPairs']}")
    print(f"Конфликтных семейств имён:       {summary['copyNameCollisionFamilies']}")
    print(f"Из них требуют проверки:         {summary['unresolvedCollisionFamilies']}")
    print(f"Неоднозначных Apple ID:          {summary['ambiguousContentIdentifiers']}")
    print(f"Вероятных одиноких Live MOV:     {summary['likelyOrphanLiveVideos']}")
    print(f"\nHTML: {html_path}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print("Исходники не изменены.")

    if args.open:
        if sys.platform == "darwin":
            subprocess.run(["open", str(html_path)], check=False)
        else:
            import webbrowser
            webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
