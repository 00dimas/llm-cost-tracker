from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


def _optional_decimal(name: str) -> Optional[Decimal]:
    raw_value = os.getenv(name)
    if not raw_value:
        return None
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal number") from exc
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _boolean(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    base_url: str
    timeout_seconds: float = 60.0
    proxy_api_key: Optional[str] = None
    database_url: Optional[str] = None
    daily_budget_usd: Optional[Decimal] = None
    monthly_budget_usd: Optional[Decimal] = None
    alert_webhook_url: Optional[str] = None
    multi_tenant_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        base_url = os.getenv("LLM_BASE_URL") or PROVIDER_BASE_URLS.get(provider)
        if not base_url:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{provider}'; set LLM_BASE_URL explicitly"
            )

        return cls(
            provider=provider,
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=base_url.rstrip("/"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
            proxy_api_key=os.getenv("PROXY_API_KEY") or None,
            database_url=os.getenv("DATABASE_URL") or None,
            daily_budget_usd=_optional_decimal("DAILY_BUDGET_USD"),
            monthly_budget_usd=_optional_decimal("MONTHLY_BUDGET_USD"),
            alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL") or None,
            multi_tenant_enabled=_boolean("MULTI_TENANT_ENABLED"),
        )
