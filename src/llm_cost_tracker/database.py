from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import asyncpg


logger = logging.getLogger("llm_cost_tracker.database")


class PostgresUsageRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def save(self, metadata: Dict[str, Any]) -> None:
        await self.pool.execute(
            """
            INSERT INTO llm_usage (
                request_id, provider, model, status_code, latency_ms,
                input_tokens, output_tokens, total_tokens, estimated_cost_usd
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (request_id) DO NOTHING
            """,
            metadata["request_id"],
            metadata["provider"],
            metadata["model"],
            metadata["status_code"],
            Decimal(str(metadata["latency_ms"])),
            metadata["input_tokens"],
            metadata["output_tokens"],
            metadata["total_tokens"],
            metadata["estimated_cost_usd"],
        )


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10)


async def safely_save(repository: Optional[Any], metadata: Dict[str, Any]) -> None:
    if repository is None:
        return
    try:
        await repository.save(metadata)
    except Exception:
        logger.exception("Failed to persist LLM usage metadata")
