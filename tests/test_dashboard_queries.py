import asyncio
from datetime import date
from decimal import Decimal
import uuid

from llm_cost_tracker.dashboard_queries import fetch_dashboard_data


class FakeConnection:
    def __init__(self) -> None:
        self.calls = []
        self.closed = False

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        if "SELECT DISTINCT" in query:
            return [{"provider": "gemini"}, {"provider": "openai"}]
        return [
            {
                "day": date(2026, 8, 25),
                "provider": "openai",
                "cost_usd": Decimal("1.25"),
                "request_count": 4,
            }
        ]

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return {
            "request_count": 4,
            "total_cost_usd": Decimal("1.25"),
            "total_tokens": 5000,
            "unpriced_request_count": 1,
            "latency_p50_ms": 100.0,
            "latency_p95_ms": 450.0,
            "latency_p99_ms": 900.0,
        }

    async def close(self):
        self.closed = True


def test_fetches_aggregates_with_safe_filters(monkeypatch) -> None:
    connection = FakeConnection()

    async def fake_connect(database_url):
        assert database_url == "postgresql://example"
        return connection

    monkeypatch.setattr("asyncpg.connect", fake_connect)
    tenant_id = uuid.uuid4()
    data = asyncio.run(
        fetch_dashboard_data(
            "postgresql://example",
            date(2026, 8, 1),
            date(2026, 8, 25),
            "openai",
            tenant_id,
        )
    )

    assert data.providers == ["gemini", "openai"]
    assert data.summary["total_cost_usd"] == Decimal("1.25")
    assert data.summary["latency_p95_ms"] == 450.0
    assert data.daily_costs[0]["request_count"] == 4
    assert connection.calls[1][1] == (
        date(2026, 8, 1),
        date(2026, 8, 26),
        "openai",
        tenant_id,
    )
    assert "$3::text" in connection.calls[1][0]
    assert "tenant_id IS NOT DISTINCT FROM $4::uuid" in connection.calls[1][0]
    assert connection.closed is True
