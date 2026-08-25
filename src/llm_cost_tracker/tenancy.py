from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Optional


KEY_PREFIX = "llmct_"


@dataclass(frozen=True)
class TenantIdentity:
    id: Any
    slug: str
    name: str


def generate_api_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        return None
    return token
