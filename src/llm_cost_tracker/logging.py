from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger("llm_cost_tracker.usage")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_usage(metadata: dict[str, Any]) -> None:
    """Log metadata only. Request and response content must never be added here."""
    logger.info(json.dumps(metadata, separators=(",", ":"), sort_keys=True))

