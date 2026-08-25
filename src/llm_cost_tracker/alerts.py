from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx


logger = logging.getLogger("llm_cost_tracker.alerts")


async def evaluate_budget_alerts(
    repository: Optional[Any],
    daily_threshold: Optional[Decimal],
    monthly_threshold: Optional[Decimal],
    webhook_url: Optional[str],
    tenant_id: Optional[Any] = None,
) -> None:
    if repository is None or not hasattr(repository, "claim_budget_alerts"):
        return
    if daily_threshold is None and monthly_threshold is None:
        return
    try:
        alerts = await repository.claim_budget_alerts(
            daily_threshold, monthly_threshold, tenant_id
        )
        for alert in alerts:
            payload = _serialize_alert(alert)
            if webhook_url:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(webhook_url, json=payload)
                    response.raise_for_status()
            else:
                logger.warning(
                    json.dumps(payload, separators=(",", ":"), sort_keys=True)
                )
    except Exception:
        logger.exception("Failed to evaluate or deliver budget alert")


def _serialize_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": "llm_budget_threshold_exceeded",
        "period_type": alert["period_type"],
        "period_start": str(alert["period_start"]),
        "threshold_usd": str(alert["threshold_usd"]),
        "actual_cost_usd": str(alert["actual_cost_usd"]),
        "tenant_id": str(alert["tenant_id"]) if alert.get("tenant_id") else None,
    }
