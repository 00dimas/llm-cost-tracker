import json
import logging
from typing import Optional
import uuid

import httpx
from fastapi.testclient import TestClient

from llm_cost_tracker.config import Settings
from llm_cost_tracker.main import create_app
from llm_cost_tracker.pricing import PriceCatalog
from llm_cost_tracker.tenancy import TenantIdentity


def settings(**overrides: object) -> Settings:
    values = {
        "provider": "test-provider",
        "api_key": "upstream-secret",
        "base_url": "https://llm.example/v1",
        "timeout_seconds": 1.0,
        "proxy_api_key": None,
        "database_url": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_health() -> None:
    app = create_app(settings())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "provider": "test-provider",
        "storage": "console",
    }


def test_proxies_request_and_logs_metadata_only(caplog) -> None:
    captured_request: Optional[httpx.Request] = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "private response"}}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "total_tokens": 15,
                },
            },
        )

    app = create_app(settings(), httpx.MockTransport(handler))
    caplog.set_level(logging.INFO, logger="llm_cost_tracker.usage")
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "test-model", "messages": [{"content": "private prompt"}]},
        )

    assert response.status_code == 200
    assert captured_request is not None
    assert captured_request.headers["authorization"] == "Bearer upstream-secret"
    logged = json.loads(caplog.records[-1].message)
    assert logged["input_tokens"] == 12
    assert logged["output_tokens"] == 3
    assert logged["total_tokens"] == 15
    assert "private prompt" not in caplog.text
    assert "private response" not in caplog.text


def test_rejects_streaming_without_contacting_upstream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Upstream should not be called")

    app = create_app(settings(), httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "test-model", "stream": True}
        )
    assert response.status_code == 501


def test_requires_proxy_key_when_configured() -> None:
    app = create_app(settings(proxy_api_key="proxy-secret"))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "test-model"}
        )
    assert response.status_code == 401


def test_calculates_cost_from_central_catalog() -> None:
    catalog = PriceCatalog.load()
    cost = catalog.estimate("openai", "gpt-5-mini", 1_000, 500)
    assert str(cost) == "0.0012500000"
    assert catalog.estimate("openai", "unknown-model", 1_000, 500) is None


def test_persists_metadata_with_estimated_cost() -> None:
    class RecordingRepository:
        def __init__(self) -> None:
            self.saved = []

        async def save(self, metadata) -> None:
            self.saved.append(metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [],
                "usage": {
                    "prompt_tokens": 1_000,
                    "completion_tokens": 500,
                    "total_tokens": 1_500,
                },
            },
        )

    repository = RecordingRepository()
    app = create_app(
        settings(provider="openai"),
        httpx.MockTransport(handler),
        usage_repository=repository,
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "gpt-5-mini", "messages": []}
        )

    assert response.status_code == 200
    assert len(repository.saved) == 1
    assert repository.saved[0]["estimated_cost_usd"] == "0.0012500000"
    assert "messages" not in repository.saved[0]


def test_persistence_failure_does_not_break_proxy_response(caplog) -> None:
    class FailingRepository:
        async def save(self, metadata) -> None:
            raise RuntimeError("database unavailable")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [], "usage": {}})

    app = create_app(
        settings(),
        httpx.MockTransport(handler),
        usage_repository=FailingRepository(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "test-model", "messages": []}
        )

    assert response.status_code == 200
    assert "Failed to persist LLM usage metadata" in caplog.text


def test_multi_tenant_mode_authenticates_and_tags_usage() -> None:
    tenant_id = uuid.uuid4()

    class TenantRepository:
        def __init__(self) -> None:
            self.saved = []

        async def resolve_tenant(self, api_key):
            if api_key == "tenant-secret":
                return TenantIdentity(tenant_id, "acme", "Acme")
            return None

        async def save(self, metadata):
            self.saved.append(metadata)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [], "usage": {}})

    repository = TenantRepository()
    app = create_app(
        settings(multi_tenant_enabled=True),
        httpx.MockTransport(handler),
        usage_repository=repository,
    )
    with TestClient(app) as client:
        unauthorized = client.post(
            "/v1/chat/completions", json={"model": "test-model"}
        )
        authorized = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer tenant-secret"},
            json={"model": "test-model"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert repository.saved[0]["tenant_id"] == str(tenant_id)
