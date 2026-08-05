#!/usr/bin/env python3
"""Run the existing importer with strict, lossless Live Photo pairing."""
from __future__ import annotations

import import_memories as engine
from live_photo_pairing import pair_live_photos_strict

engine.pair_live_photos = pair_live_photos_strict

if __name__ == "__main__":
    raise SystemExit(engine.main())
