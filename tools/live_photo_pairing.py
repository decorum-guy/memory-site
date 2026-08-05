#!/usr/bin/env python3
"""Lossless Live Photo pairing shared by import, preflight and audit.

Pairing priority:
1. A unique Apple ContentIdentifier match is authoritative, even when Finder or
   Photos renamed the still image because another file already used the name.
2. An exact same-stem group containing multiple images or videos is considered
   ambiguous and stays fully independent, even if one identifier happens to
   match. This preserves cases such as JPG + HEIC + MOV that the user knows are
   three separate media.
3. Filename fallback is allowed only for one image + one video with the exact
   same stem, no identifiers, a close timestamp, and no sibling copy-name
   collision such as ``IMG_8271 2.HEIC`` next to ``IMG_8271.MOV``.

Source files are never renamed or changed.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

FALLBACK_MAX_SECONDS = 120

_COPY_SUFFIX_PATTERNS = (
    re.compile(r"^(?P<base>.+?)\s+\((?P<number>\d+)\)$", re.IGNORECASE),
    re.compile(r"^(?P<base>.+?)\s+(?P<number>[2-9]\d*)$", re.IGNORECASE),
    re.compile(r"^(?P<base>.+?)[_-](?P<number>[2-9]\d*)$", re.IGNORECASE),
    re.compile(r"^(?P<base>.+?)\s+(?:copy|копия)(?:\s+(?P<number>\d+))?$", re.IGNORECASE),
)


def stem_key(path: Path) -> tuple[str, str]:
    return (path.parent.resolve().as_posix().casefold(), path.stem.casefold())


def copy_family_stem(stem: str) -> str:
    """Return the probable pre-collision stem without modifying any file."""
    value = stem.strip()
    for pattern in _COPY_SUFFIX_PATTERNS:
        match = pattern.match(value)
        if match:
            base = match.group("base").strip()
            if base:
                return base
    return value


def copy_family_key(path: Path) -> tuple[str, str]:
    return (
        path.parent.resolve().as_posix().casefold(),
        copy_family_stem(path.stem).casefold(),
    )


def _time_distance(left: Any, right: Any) -> float:
    return abs((left.taken_at - right.taken_at).total_seconds())


def collision_family_keys(items: Iterable[Any]) -> set[tuple[str, str]]:
    """Families containing multiple actual stems, e.g. IMG_1 and IMG_1 2."""
    stems_by_family: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for item in items:
        stems_by_family[copy_family_key(item.source)].add(stem_key(item.source))
    return {key for key, stems in stems_by_family.items() if len(stems) > 1}


def ambiguous_exact_stem_keys(
    images_by_stem: dict[tuple[str, str], list[Any]],
    videos_by_stem: dict[tuple[str, str], list[Any]],
) -> set[tuple[str, str]]:
    """Exact stems containing 2+ images or 2+ videos alongside the other kind."""
    return {
        key
        for key in set(images_by_stem) & set(videos_by_stem)
        if len(images_by_stem[key]) != 1 or len(videos_by_stem[key]) != 1
    }


def pair_live_photos_strict(media: list[Any]) -> tuple[list[Any], set[Path]]:
    """Pair only confident Live Photos and preserve every ambiguous file."""
    images = [item for item in media if item.is_image]
    videos = [item for item in media if not item.is_image]
    used_videos: set[Path] = set()
    paired_images: set[Path] = set()

    images_by_id: dict[str, list[Any]] = defaultdict(list)
    videos_by_id: dict[str, list[Any]] = defaultdict(list)
    images_by_stem: dict[tuple[str, str], list[Any]] = defaultdict(list)
    videos_by_stem: dict[tuple[str, str], list[Any]] = defaultdict(list)

    for image in images:
        if image.content_id:
            images_by_id[str(image.content_id)].append(image)
        images_by_stem[stem_key(image.source)].append(image)
    for video in videos:
        if video.content_id:
            videos_by_id[str(video.content_id)].append(video)
        videos_by_stem[stem_key(video.source)].append(video)

    exact_stem_ambiguities = ambiguous_exact_stem_keys(images_by_stem, videos_by_stem)

    # Strong signal: a unique 1:1 Apple ID may cross stems, but must not consume
    # a same-stem JPG+HEIC+MOV group that is explicitly ambiguous.
    for content_id in sorted(set(images_by_id) & set(videos_by_id)):
        image_group = images_by_id[content_id]
        video_group = videos_by_id[content_id]
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if stem_key(image.source) in exact_stem_ambiguities:
            continue
        if stem_key(video.source) in exact_stem_ambiguities:
            continue
        if image.source in paired_images or video.source in used_videos:
            continue
        image.live_source = video.source
        paired_images.add(image.source)
        used_videos.add(video.source)

    # Weak signal: filename fallback is forbidden in any copy-name family.
    # This prevents IMG_8271.HEIC from stealing IMG_8271.MOV when the real Live
    # still was renamed to IMG_8271 2.HEIC and identifiers are missing.
    copy_collisions = collision_family_keys([*images, *videos])
    for key, image_group in images_by_stem.items():
        video_group = videos_by_stem.get(key, [])
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if image.source in paired_images or video.source in used_videos:
            continue
        if copy_family_key(image.source) in copy_collisions:
            continue
        if image.content_id or video.content_id:
            continue
        if _time_distance(image, video) > FALLBACK_MAX_SECONDS:
            continue
        image.live_source = video.source
        paired_images.add(image.source)
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
    """Use the same lossless rules for the dry-run Live Photo count."""
    images = [path for path in paths if path.suffix.lower() in image_exts]
    videos = [path for path in paths if path.suffix.lower() in video_exts]

    image_info: dict[Path, tuple[str, dt.datetime]] = {}
    video_info: dict[Path, tuple[str, dt.datetime]] = {}
    images_by_id: dict[str, list[Path]] = defaultdict(list)
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
        content_id, _ = image_info[image]
        if content_id:
            images_by_id[content_id].append(image)
        images_by_stem[stem_key(image)].append(image)
    for video in videos:
        video_info[video] = info(video)
        content_id, _ = video_info[video]
        if content_id:
            videos_by_id[content_id].append(video)
        videos_by_stem[stem_key(video)].append(video)

    exact_stem_ambiguities = ambiguous_exact_stem_keys(images_by_stem, videos_by_stem)
    used: set[Path] = set()
    paired_images: set[Path] = set()

    for content_id in sorted(set(images_by_id) & set(videos_by_id)):
        image_group = images_by_id[content_id]
        video_group = videos_by_id[content_id]
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if stem_key(image) in exact_stem_ambiguities or stem_key(video) in exact_stem_ambiguities:
            continue
        paired_images.add(image)
        used.add(video)

    path_items = [type("PathItem", (), {"source": path})() for path in [*images, *videos]]
    copy_collisions = collision_family_keys(path_items)

    for key, image_group in images_by_stem.items():
        video_group = videos_by_stem.get(key, [])
        if len(image_group) != 1 or len(video_group) != 1:
            continue
        image = image_group[0]
        video = video_group[0]
        if image in paired_images or video in used:
            continue
        if copy_family_key(image) in copy_collisions:
            continue
        image_id, image_time = image_info[image]
        video_id, video_time = video_info[video]
        if image_id or video_id:
            continue
        if abs((video_time - image_time).total_seconds()) > FALLBACK_MAX_SECONDS:
            continue
        paired_images.add(image)
        used.add(video)

    return len(used)
