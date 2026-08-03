#!/usr/bin/env python3
"""Generate an offline QR image and optionally enable Shared Album in settings.js."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "media" / "shared-album-qr.png"
SETTINGS = ROOT / "content" / "settings.js"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать QR-код для Apple Shared Album")
    parser.add_argument("url", help="Публичная ссылка Shared Album")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Куда сохранить PNG")
    parser.add_argument("--no-enable", action="store_true", help="Не менять content/settings.js")
    return parser.parse_args()


def update_settings(url: str, qr_path: Path) -> None:
    text = SETTINGS.read_text(encoding="utf-8")
    relative = qr_path.resolve().relative_to(ROOT.resolve()).as_posix()
    replacements = {
        r"sharedAlbumEnabled:\s*(?:true|false)": "sharedAlbumEnabled: true",
        r"sharedAlbumUrl:\s*\"[^\"]*\"": f"sharedAlbumUrl: {json.dumps(url, ensure_ascii=False)}",
        r"sharedAlbumQr:\s*\"[^\"]*\"": f"sharedAlbumQr: {json.dumps(relative, ensure_ascii=False)}",
    }
    for pattern, value in replacements.items():
        text, count = re.subn(pattern, value, text, count=1)
        if count != 1:
            raise RuntimeError(f"Не найден параметр настроек: {pattern}")
    SETTINGS.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith(("https://", "http://")):
        raise SystemExit("Ссылка должна начинаться с https:// или http://")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=14,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#342c25", back_color="#fffaf0")
    image.save(output)

    if not args.no_enable:
        update_settings(url, output)

    print(f"QR сохранён: {output}")
    print("Shared Album включён в content/settings.js" if not args.no_enable else "Настройки не изменялись")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
