from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


@dataclass(frozen=True)
class Settings:
    provider: str
    api_key: str
    base_url: str
    timeout_seconds: float = 60.0
    proxy_api_key: Optional[str] = None
    database_url: Optional[str] = None

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
        )
