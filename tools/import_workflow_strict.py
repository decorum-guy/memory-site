#!/usr/bin/env python3
"""Run the safe import workflow with strict Live Photo detection."""
from __future__ import annotations

from pathlib import Path

import import_workflow as workflow
from live_photo_pairing import estimate_live_pairs_strict

ROOT = Path(__file__).resolve().parents[1]
workflow.ENGINE = ROOT / "tools" / "import_memories_strict.py"


def strict_estimate(paths, metadata):
    return estimate_live_pairs_strict(
        paths=paths,
        metadata=metadata,
        image_exts=workflow.IMAGE_EXTS,
        video_exts=workflow.VIDEO_EXTS,
        content_id_keys=workflow.CONTENT_ID_KEYS,
        date_keys=workflow.DATE_KEYS,
        first_value=workflow.first_metadata_value,
    )


workflow.estimate_live_pairs = strict_estimate

if __name__ == "__main__":
    raise SystemExit(workflow.main())
