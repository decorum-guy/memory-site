#!/usr/bin/env python3
"""Strict Live Photo pairing shared by import and preflight.

A matching filename is only a last-resort signal. Exact Apple
ContentIdentifier matches are preferred only for unambiguous files. Filename
fallback is allowed only for one image + one video in the same folder, with no
identifiers on either side and a close timestamp. Any same-stem group with
multiple images or multiple videos remains fully independent so no source file
can disappear from the book.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

FALLBACK_MAX_SECONDS = 120


def stem_key(path: Path) -> tuple[str, str]:
    return (path.parent.resolve().as_posix().casefold(), path.stem.casefold())


def _time_distance(left: Any, right: Any) -> float:
    return abs((left.taken_at - right.taken_at).total_seconds())


def ambiguous_stem_keys(
    images_by_stem: dict[tuple[str, str], list[Any]],
    videos_by_stem: dict[tuple[str, str], list[Any]],
) -> set[tuple[str, str]]:
    keys = set(images_by_stem) | set(videos_by_stem)
    return {
        key
        for key in keys
        if images_by_stem.get(key)
        and videos_by_stem.get(key)
        and (len(images_by_stem[key]) != 1 or len(videos_by_stem[key]) != 1)
    }


def pair_live_photos_strict(media: list[Any]) -> tuple[list[Any], set[Path]]:
    """Pair only confident Live Photos and preserve every ambiguous file."""
    images = [item for item in media if item.is_image]
    videos = [item for item in media if not item.is_image]
    used_videos: set[Path] = set()

    videos_by_id: dict[str, list[Any]] = defaultdict(list)
    images_by_stem: dict[tuple[str, str], list[Any]] = defaultdict(list)
    videos_by_stem: dict[tuple[str, str], list[Any]] = defaultdict(list)

    for image in images:
        images_by_stem[stem_key(image.source)].append(image)
    for video in videos:
        if video.content_id:
            videos_by_id[str(video.content_id)].append(video)
        videos_by_stem[stem_key(video.source)].append(video)

    ambiguous = ambiguous_stem_keys(images_by_stem, videos_by_stem)

    # Strong signal: Apple ContentIdentifier must match exactly, but even an
    # identifier cannot collapse an ambiguous IMG_1234.JPG/HEIC/MOV group.
    for image in images:
        if not image.content_id or stem_key(image.source) in ambiguous:
            continue
        candidates = [
            candidate
            for candidate in videos_by_id.get(str(image.content_id), [])
            if candidate.source not in used_videos
            and stem_key(candidate.source) not in ambiguous
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda candidate: _time_distance(image, candidate))
        image.live_source = best.source
        used_videos.add(best.source)

    # Weak signal: same folder + same stem is accepted only when unambiguous.
    for key, image_group in images_by_stem.items():
        if key in ambiguous:
            continue
        video_group = videos_by_stem.get(key, [])
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if image.live_source or video.source in used_videos:
            continue
        if image.content_id or video.content_id:
            continue
        if _time_distance(image, video) > FALLBACK_MAX_SECONDS:
            continue
        image.live_source = video.source
        used_videos.add(video.source)

    return media, used_videos


def parse_metadata_datetime(value: Any, fallback: dt.datetime) -> dt.datetime:
    if value in (None, ""):
        return fallback
    text = re.sub(r"([+-]\d\d):?(\d\d)$", r"\1:\2", str(value).strip())
    for fmt in (
        "%Y:%m:%d %H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            parsed = dt.datetime.strptime(text, fmt)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return fallback


def estimate_live_pairs_strict(
    paths: list[Path],
    metadata: dict[str, dict[str, Any]],
    image_exts: set[str],
    video_exts: set[str],
    content_id_keys: Iterable[str],
    date_keys: Iterable[str],
    first_value: Callable[[dict[str, Any], Iterable[str]], Any],
) -> int:
    """Use the same strict rules for the dry-run Live Photo count."""
    images = [path for path in paths if path.suffix.lower() in image_exts]
    videos = [path for path in paths if path.suffix.lower() in video_exts]

    image_info: dict[Path, tuple[str, dt.datetime]] = {}
    video_info: dict[Path, tuple[str, dt.datetime]] = {}
    videos_by_id: dict[str, list[Path]] = defaultdict(list)
    images_by_stem: dict[tuple[str, str], list[Path]] = defaultdict(list)
    videos_by_stem: dict[tuple[str, str], list[Path]] = defaultdict(list)

    def info(path: Path) -> tuple[str, dt.datetime]:
        row = metadata.get(str(path.resolve()), {})
        content_id = str(first_value(row, content_id_keys) or "").strip()
        fallback = dt.datetime.fromtimestamp(path.stat().st_mtime)
        taken_at = parse_metadata_datetime(first_value(row, date_keys), fallback)
        return content_id, taken_at

    for image in images:
        image_info[image] = info(image)
        images_by_stem[stem_key(image)].append(image)
    for video in videos:
        video_info[video] = info(video)
        content_id, _ = video_info[video]
        if content_id:
            videos_by_id[content_id].append(video)
        videos_by_stem[stem_key(video)].append(video)

    ambiguous = ambiguous_stem_keys(images_by_stem, videos_by_stem)
    used: set[Path] = set()
    paired_images: set[Path] = set()

    for image in images:
        content_id, image_time = image_info[image]
        if not content_id or stem_key(image) in ambiguous:
            continue
        candidates = [
            path
            for path in videos_by_id.get(content_id, [])
            if path not in used and stem_key(path) not in ambiguous
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda path: abs((video_info[path][1] - image_time).total_seconds()))
        used.add(best)
        paired_images.add(image)

    for key, image_group in images_by_stem.items():
        if key in ambiguous:
            continue
        video_group = videos_by_stem.get(key, [])
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if image in paired_images or video in used:
            continue
        image_id, image_time = image_info[image]
        video_id, video_time = video_info[video]
        if image_id or video_id:
            continue
        if abs((video_time - image_time).total_seconds()) > FALLBACK_MAX_SECONDS:
            continue
        used.add(video)
        paired_images.add(image)

    return len(used)
