import asyncio
import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

from llm_cost_tracker.dashboard_queries import fetch_dashboard_data
from llm_cost_tracker.database import PostgresUsageRepository, create_pool
from llm_cost_tracker.migrate import migrate
from llm_cost_tracker.tenants import create_tenant


DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
def test_postgres_migrations_and_tenant_isolation() -> None:
    asyncio.run(_run_integration_scenario(DATABASE_URL))


async def _run_integration_scenario(database_url: str) -> None:
    await migrate(database_url)
    pool = await create_pool(database_url)
    try:
        await pool.execute(
            "TRUNCATE budget_alerts, llm_usage, tenant_api_keys, tenants "
            "RESTART IDENTITY CASCADE"
        )
        pricing_count = await pool.fetchval("SELECT COUNT(*) FROM model_pricing")
        assert pricing_count == 3

        first_key = await create_tenant(
            database_url, "integration-a", "Integration A", "test"
        )
        second_key = await create_tenant(
            database_url, "integration-b", "Integration B", "test"
        )
        repository = PostgresUsageRepository(pool)
        first_tenant = await repository.resolve_tenant(first_key)
        second_tenant = await repository.resolve_tenant(second_key)
        assert first_tenant is not None
        assert second_tenant is not None
        assert first_tenant.id != second_tenant.id

        await repository.save(_usage(first_tenant.id, "0.0012500000"))
        await repository.save(_usage(second_tenant.id, "2.0000000000"))

        first_dashboard = await fetch_dashboard_data(
            database_url,
            date.today(),
            date.today(),
            tenant_id=first_tenant.id,
        )
        second_dashboard = await fetch_dashboard_data(
            database_url,
            date.today(),
            date.today(),
            tenant_id=second_tenant.id,
        )
        assert first_dashboard.summary["request_count"] == 1
        assert first_dashboard.summary["total_cost_usd"] == Decimal(
            "0.0012500000"
        )
        assert second_dashboard.summary["request_count"] == 1
        assert second_dashboard.summary["total_cost_usd"] == Decimal(
            "2.0000000000"
        )

        claimed = await repository.claim_budget_alerts(
            Decimal("0.001"), None, first_tenant.id
        )
        duplicate = await repository.claim_budget_alerts(
            Decimal("0.001"), None, first_tenant.id
        )
        assert len(claimed) == 1
        assert duplicate == []

        # Every migration must remain safe to run again on an existing database.
        await migrate(database_url)
    finally:
        await pool.execute(
            "TRUNCATE budget_alerts, llm_usage, tenant_api_keys, tenants "
            "RESTART IDENTITY CASCADE"
        )
        await pool.close()


def _usage(tenant_id: uuid.UUID, cost: str):
    return {
        "request_id": str(uuid.uuid4()),
        "provider": "openai",
        "model": "gpt-5-mini",
        "status_code": 200,
        "latency_ms": 125.5,
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
        "estimated_cost_usd": cost,
        "tenant_id": str(tenant_id),
    }
