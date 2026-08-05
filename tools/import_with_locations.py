#!/usr/bin/env python3
"""Runs the safe Memory import workflow and then enriches the result with places.

Examples:
  python tools/import_with_locations.py dry-run ~/Projects/memory-source
  python tools/import_with_locations.py test ~/Projects/memory-source --open
  python tools/import_with_locations.py import ~/Projects/memory-source --yes
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "tools" / "import_workflow.py"
ENRICHER = ROOT / "tools" / "location_enrichment.py"
TEST_ROOT = ROOT / ".memory-test" / "site"


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Импорт Memory Site с названиями мест через macOS")
    parser.add_argument("mode", choices=["dry-run", "test", "import"])
    parser.add_argument("source", type=Path)
    parser.add_argument("--no-geocode", action="store_true", help="Не использовать геокодер macOS")
    args, passthrough = parser.parse_known_args()
    return args, passthrough


def main() -> int:
    args, passthrough = parse_args()
    source = args.source.expanduser().resolve()
    workflow_command = [sys.executable, str(WORKFLOW), args.mode, str(source), *passthrough]
    result = subprocess.run(workflow_command)
    if result.returncode != 0 or args.mode == "dry-run":
        return result.returncode

    target_root = TEST_ROOT if args.mode == "test" else ROOT
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
    if enriched.returncode != 0:
        print(
            "Импорт медиа завершён, но названия мест не добавлены. "
            "Исправь ошибку выше и повтори только tools/location_enrichment.py.",
            file=sys.stderr,
        )
    return enriched.returncode


if __name__ == "__main__":
    raise SystemExit(main())
