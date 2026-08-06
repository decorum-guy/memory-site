#!/usr/bin/env python3
"""Local Memory/For You Studio server with incremental media import.

Use this instead of telegram_server.py when Memory Studio must accept new
photos, videos or explicit Live Photo pairs. Existing optional-chapter and
production apply endpoints are inherited unchanged.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import incremental_media_import as media_import
import telegram_server as base


FOR_YOU_DEFAULTS = {
    "kicker": "Несколько слов для тебя",
    "title": "For You",
    "subtitle": "Пожелания, которые я хочу оставить тебе рядом.",
}
base.DEFAULT_STATE.update(FOR_YOU_DEFAULTS)
_base_build_chapter = base.build_chapter


def build_for_you_chapter(state: dict[str, Any]):
    modes, chapter = _base_build_chapter(state)
    # Keep the technical id for compatibility with the existing Reader and
    # preview URL, but remove the old TG label from the visible chapter rail.
    chapter["number"] = "FY"
    return modes, chapter


base.build_chapter = build_for_you_chapter


class Handler(base.Handler):
    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            # Browsers routinely cancel an old byte-range request after seeking
            # or replacing a video source. This is a normal client disconnect,
            # not a server or media failure, so keep the local server quiet.
            self._range_remaining = None

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in {"/api/memory/import/upload", "/api/memory/import/process"}:
            super().do_POST()
            return
        try:
            if path == "/api/memory/import/upload":
                self.handle_memory_import_upload()
                return
            value = self.read_json()
            result = media_import.process_batch(
                batch_id=str(value.get("batchId") or ""),
                base_book=value.get("book"),
                pairs=value.get("pairs") if isinstance(value.get("pairs"), list) else [],
                target=value.get("target") if isinstance(value.get("target"), dict) else None,
            )
            self.send_json(result)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def handle_memory_import_upload(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        batch_id = self.headers.get("X-Memory-Batch", "")
        encoded_name = self.headers.get("X-Memory-Name", "media")
        modified_raw = self.headers.get("X-Memory-Modified", "0")
        try:
            modified_ms = int(modified_raw)
        except (TypeError, ValueError):
            modified_ms = 0
        entry = media_import.stage_upload(
            batch_id=batch_id,
            name=urllib.parse.unquote(encoded_name),
            stream=self.rfile,
            length=length,
            modified_ms=modified_ms,
        )
        self.send_json({"ok": True, **entry})


def main() -> int:
    base.Handler = Handler
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
