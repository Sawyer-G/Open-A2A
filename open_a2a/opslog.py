import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


def json_enabled() -> bool:
    return os.getenv("OA2A_LOG_JSON", "").strip().lower() in ("1", "true", "yes")


def log_event(service: str, level: str, event: str, **fields: Any) -> None:
    """
    Minimal structured logging helper (JSON line).

    - Enabled when OA2A_LOG_JSON=1.
    - Keeps current print-based logs intact by being opt-in.
    - Uses stdlib only.
    """
    if not json_enabled():
        return
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "level": level,
        "event": event,
        **fields,
    }
    try:
        logging.getLogger(service).info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Never break runtime due to logging.
        return

