from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Tuple

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from .alerts import evaluate_budget_alerts
from .config import Settings
from .database import PostgresUsageRepository, create_pool, safely_save
from .logging import configure_logging, log_usage
from .pricing import PriceCatalog
from .tenancy import TenantIdentity, bearer_token


def _token_usage(body: Any) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if not isinstance(body, dict) or not isinstance(body.get("usage"), dict):
        return None, None, None
    usage = body["usage"]
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def create_app(
    settings: Optional[Settings] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    usage_repository: Optional[Any] = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    price_catalog = PriceCatalog.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.upstream = httpx.AsyncClient(
            base_url=resolved_settings.base_url,
            timeout=resolved_settings.timeout_seconds,
            transport=transport,
        )
        pool = None
        app.state.usage_repository = usage_repository
        if resolved_settings.multi_tenant_enabled and not resolved_settings.database_url:
            if usage_repository is None:
                raise RuntimeError("DATABASE_URL is required in multi-tenant mode")
        if usage_repository is None and resolved_settings.database_url:
            pool = await create_pool(resolved_settings.database_url)
            app.state.usage_repository = PostgresUsageRepository(pool)
        try:
            yield
        finally:
            await app.state.upstream.aclose()
            if pool is not None:
                await pool.close()

    app = FastAPI(title="LLM Cost Tracker", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        storage = "postgres" if resolved_settings.database_url else "console"
        return {
            "status": "ok",
            "provider": resolved_settings.provider,
            "storage": storage,
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Response:
        tenant: Optional[TenantIdentity] = None
        if resolved_settings.multi_tenant_enabled:
            token = bearer_token(authorization)
            repository = request.app.state.usage_repository
            if not token or repository is None or not hasattr(repository, "resolve_tenant"):
                raise HTTPException(status_code=401, detail="Invalid tenant API key")
            try:
                tenant = await repository.resolve_tenant(token)
            except Exception as exc:
                raise HTTPException(
                    status_code=503, detail="Tenant authentication unavailable"
                ) from exc
            if tenant is None:
                raise HTTPException(status_code=401, detail="Invalid tenant API key")
        elif resolved_settings.proxy_api_key:
            expected = f"Bearer {resolved_settings.proxy_api_key}"
            if authorization != expected:
                raise HTTPException(status_code=401, detail="Invalid proxy API key")
        if not resolved_settings.api_key:
            raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Request body must be JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("model"), str):
            raise HTTPException(status_code=422, detail="A string model field is required")
        if payload.get("stream") is True:
            raise HTTPException(status_code=501, detail="Streaming is not supported in M0")

        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        status_code = 502
        response_body: Any = None
        try:
            upstream_response = await request.app.state.upstream.post(
                "/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {resolved_settings.api_key}",
                    "Content-Type": "application/json",
                    "X-Request-ID": request_id,
                },
            )
            status_code = upstream_response.status_code
            try:
                response_body = upstream_response.json()
            except ValueError:
                response_body = None
            content_type = upstream_response.headers.get("content-type", "application/json")
            return Response(
                content=upstream_response.content,
                status_code=status_code,
                media_type=content_type.split(";", 1)[0],
            )
        except httpx.TimeoutException:
            status_code = 504
            return JSONResponse(status_code=504, content={"detail": "Upstream timed out"})
        except httpx.RequestError:
            status_code = 502
            return JSONResponse(status_code=502, content={"detail": "Upstream unavailable"})
        finally:
            input_tokens, output_tokens, total_tokens = _token_usage(response_body)
            estimated_cost = price_catalog.estimate(
                resolved_settings.provider,
                payload["model"],
                input_tokens,
                output_tokens,
            )
            metadata = {
                "event": "llm_request",
                "request_id": request_id,
                "provider": resolved_settings.provider,
                "model": payload["model"],
                "status_code": status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": (
                    str(estimated_cost) if estimated_cost is not None else None
                ),
                "tenant_id": str(tenant.id) if tenant is not None else None,
            }
            log_usage(metadata)
            await safely_save(request.app.state.usage_repository, metadata)
            await evaluate_budget_alerts(
                request.app.state.usage_repository,
                resolved_settings.daily_budget_usd,
                resolved_settings.monthly_budget_usd,
                resolved_settings.alert_webhook_url,
                tenant.id if tenant is not None else None,
            )

    return app


configure_logging()
app = create_app()
