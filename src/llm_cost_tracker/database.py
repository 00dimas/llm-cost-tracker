from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg

from .tenancy import TenantIdentity, hash_api_key


logger = logging.getLogger("llm_cost_tracker.database")


class PostgresUsageRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def save(self, metadata: Dict[str, Any]) -> None:
        await self.pool.execute(
            """
            INSERT INTO llm_usage (
                request_id, provider, model, status_code, latency_ms,
                input_tokens, output_tokens, total_tokens, estimated_cost_usd,
                tenant_id
            ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10::uuid)
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
            metadata.get("tenant_id"),
        )

    async def resolve_tenant(self, api_key: str) -> Optional[TenantIdentity]:
        row = await self.pool.fetchrow(
            """
            SELECT tenants.id, tenants.slug, tenants.name
            FROM tenant_api_keys
            JOIN tenants ON tenants.id = tenant_api_keys.tenant_id
            WHERE tenant_api_keys.key_hash = $1
              AND tenant_api_keys.revoked_at IS NULL
            """,
            hash_api_key(api_key),
        )
        if not row:
            return None
        return TenantIdentity(id=row["id"], slug=row["slug"], name=row["name"])

    async def claim_budget_alerts(
        self,
        daily_threshold: Optional[Decimal],
        monthly_threshold: Optional[Decimal],
        tenant_id: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        periods = []
        if daily_threshold is not None:
            periods.append(("daily", now.date(), daily_threshold))
        if monthly_threshold is not None:
            periods.append(
                ("monthly", now.date().replace(day=1), monthly_threshold)
            )

        claimed = []
        for period_type, period_start, threshold in periods:
            row = await self.pool.fetchrow(
                """
                WITH current_total AS (
                    SELECT COALESCE(SUM(estimated_cost_usd), 0)::numeric AS cost
                    FROM llm_usage
                    WHERE occurred_at >= $1::date
                      AND tenant_id IS NOT DISTINCT FROM $4::uuid
                )
                INSERT INTO budget_alerts (
                    period_type, period_start, threshold_usd, actual_cost_usd,
                    tenant_id
                )
                SELECT $2, $1, $3, cost, $4
                FROM current_total
                WHERE cost >= $3
                ON CONFLICT DO NOTHING
                RETURNING period_type, period_start, threshold_usd, actual_cost_usd,
                    tenant_id
                """,
                period_start,
                period_type,
                threshold,
                tenant_id,
            )
            if row:
                claimed.append(dict(row))
        return claimed


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10)


async def safely_save(repository: Optional[Any], metadata: Dict[str, Any]) -> None:
    if repository is None:
        return
    try:
        await repository.save(metadata)
    except Exception:
        logger.exception("Failed to persist LLM usage metadata")
