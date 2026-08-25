import asyncio
import json
import logging
from datetime import date
from decimal import Decimal

from llm_cost_tracker.alerts import evaluate_budget_alerts
from llm_cost_tracker.database import PostgresUsageRepository


def test_emits_claimed_budget_alert_to_console(caplog) -> None:
    class Repository:
        async def claim_budget_alerts(self, daily, monthly):
            assert daily == Decimal("10")
            assert monthly is None
            return [
                {
                    "period_type": "daily",
                    "period_start": date(2026, 8, 25),
                    "threshold_usd": Decimal("10"),
                    "actual_cost_usd": Decimal("12.50"),
                }
            ]

    caplog.set_level(logging.WARNING, logger="llm_cost_tracker.alerts")
    asyncio.run(
        evaluate_budget_alerts(Repository(), Decimal("10"), None, None)
    )

    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "event": "llm_budget_threshold_exceeded",
        "period_type": "daily",
        "period_start": "2026-08-25",
        "threshold_usd": "10",
        "actual_cost_usd": "12.50",
    }


def test_repository_claims_daily_and_monthly_alerts_atomically() -> None:
    class Pool:
        def __init__(self):
            self.calls = []

        async def fetchrow(self, query, *args):
            self.calls.append((query, args))
            return None

    pool = Pool()
    repository = PostgresUsageRepository(pool)  # type: ignore[arg-type]
    alerts = asyncio.run(
        repository.claim_budget_alerts(Decimal("10"), Decimal("100"))
    )

    assert alerts == []
    assert len(pool.calls) == 2
    assert pool.calls[0][1][1:] == ("daily", Decimal("10"))
    assert pool.calls[1][1][1:] == ("monthly", Decimal("100"))
    assert pool.calls[1][1][0].day == 1
    assert "ON CONFLICT" in pool.calls[0][0]
