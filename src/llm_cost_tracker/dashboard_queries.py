from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg


@dataclass(frozen=True)
class DashboardData:
    providers: List[str]
    summary: Dict[str, Any]
    daily_costs: List[Dict[str, Any]]


async def fetch_dashboard_data(
    database_url: str,
    start_date: date,
    end_date: date,
    provider: Optional[str] = None,
) -> DashboardData:
    """Fetch aggregate metadata only; raw prompts and responses are never queried."""
    connection = await asyncpg.connect(database_url)
    end_exclusive = end_date + timedelta(days=1)
    try:
        providers = await connection.fetch(
            "SELECT DISTINCT provider FROM llm_usage ORDER BY provider"
        )
        summary = await connection.fetchrow(
            """
            SELECT
                COUNT(*)::bigint AS request_count,
                COALESCE(SUM(estimated_cost_usd), 0)::numeric AS total_cost_usd,
                COALESCE(SUM(total_tokens), 0)::bigint AS total_tokens,
                COUNT(*) FILTER (WHERE estimated_cost_usd IS NULL)::bigint
                    AS unpriced_request_count
            FROM llm_usage
            WHERE occurred_at >= $1::date
              AND occurred_at < $2::date
              AND ($3::text IS NULL OR provider = $3)
            """,
            start_date,
            end_exclusive,
            provider,
        )
        daily_rows = await connection.fetch(
            """
            SELECT
                occurred_at::date AS day,
                provider,
                COALESCE(SUM(estimated_cost_usd), 0)::numeric AS cost_usd,
                COUNT(*)::bigint AS request_count
            FROM llm_usage
            WHERE occurred_at >= $1::date
              AND occurred_at < $2::date
              AND ($3::text IS NULL OR provider = $3)
            GROUP BY occurred_at::date, provider
            ORDER BY day, provider
            """,
            start_date,
            end_exclusive,
            provider,
        )
        return DashboardData(
            providers=[row["provider"] for row in providers],
            summary=dict(summary or {}),
            daily_costs=[dict(row) for row in daily_rows],
        )
    finally:
        await connection.close()


def empty_summary() -> Dict[str, Any]:
    return {
        "request_count": 0,
        "total_cost_usd": Decimal("0"),
        "total_tokens": 0,
        "unpriced_request_count": 0,
    }
