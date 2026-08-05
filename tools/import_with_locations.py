#!/usr/bin/env python3
"""Runs the safe Memory import workflow and then enriches the result with places.

Examples:
  python tools/import_with_locations.py dry-run ~/Projects/memory-source
  python tools/import_with_locations.py test ~/Projects/memory-source --open
  python tools/import_with_locations.py import ~/Projects/memory-source --yes
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "tools" / "import_workflow_strict.py"
ENRICHER = ROOT / "tools" / "location_enrichment.py"
TEST_ROOT = ROOT / ".memory-test" / "site"
SHARED_CACHE = ROOT / ".memory-location-cache.json"


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Импорт Memory Site с названиями мест через macOS")
    parser.add_argument("mode", choices=["dry-run", "test", "import"])
    parser.add_argument("source", type=Path)
    parser.add_argument("--no-geocode", action="store_true", help="Не использовать геокодер macOS")
    parser.add_argument("--open", action="store_true", help="Открыть готовую книгу после импорта и геокодирования")
    args, passthrough = parser.parse_known_args()
    return args, passthrough


def sync_cache_to_test() -> None:
    if not SHARED_CACHE.is_file() or not TEST_ROOT.is_dir():
        return
    shutil.copy2(SHARED_CACHE, TEST_ROOT / SHARED_CACHE.name)


def sync_cache_from_test() -> None:
    test_cache = TEST_ROOT / SHARED_CACHE.name
    if test_cache.is_file():
        shutil.copy2(test_cache, SHARED_CACHE)


def open_book(root: Path) -> None:
    url = (root / "index.html").resolve().as_uri() + "?opened=1#memory-book"
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        webbrowser.open(url)


def main() -> int:
    args, passthrough = parse_args()
    source = args.source.expanduser().resolve()
    workflow_command = [sys.executable, str(WORKFLOW), args.mode, str(source), *passthrough]
    result = subprocess.run(workflow_command)
    if result.returncode != 0 or args.mode == "dry-run":
        return result.returncode

    target_root = TEST_ROOT if args.mode == "test" else ROOT
    if args.mode == "test":
        sync_cache_to_test()

    enrich_command = [
        sys.executable,
        str(ENRICHER),
        str(source),
        "--root",
        str(target_root),
    ]
    if args.no_geocode:
        enrich_command.append("--no-geocode")

    print("\n=== MEMORY LOCATION ENRICHMENT ===")
    enriched = subprocess.run(enrich_command)
    if args.mode == "test" and enriched.returncode == 0:
        sync_cache_from_test()
        print(f"Общий кэш мест сохранён: {SHARED_CACHE}")

    if enriched.returncode != 0:
        print(
            "Импорт медиа завершён, но названия мест не добавлены. "
            "Исправь ошибку выше и повтори только tools/location_enrichment.py.",
            file=sys.stderr,
        )
        return enriched.returncode

    if args.open:
        open_book(target_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
