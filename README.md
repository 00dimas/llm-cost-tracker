# LLM Cost Tracker

A lightweight proxy and dashboard for tracking cost and latency of LLM API calls across providers.

## What it does

The proxy sits in front of OpenAI/Anthropic-compatible providers (OpenAI, Groq, Gemini via their OpenAI-compatible endpoints) and logs every request — tokens in/out, estimated cost, latency, status — so a team can see which provider or endpoint is the most expensive or the slowest.

- **Proxy layer**: a single FastAPI gateway that forwards chat completion requests to the configured provider, transparent to the calling application.
- **Cost calculation**: pricing is kept in one JSON file (`src/llm_cost_tracker/data/pricing.json`) and synced into a `model_pricing` table via migration upserts — no hardcoded prices scattered through the code. Requests for unlisted models are still stored, with `estimated_cost_usd` left `null`.
- **Dashboard**: a Streamlit app with date-range and provider filters, cost/request/token summaries, daily cost charts, p50/p95/p99 latency, and an aggregate table. It only reads usage metadata — prompt and response bodies are never stored or displayed.
- **Budget alerting**: optional daily/monthly USD thresholds. Without a webhook URL, alerts are logged as JSON to the console; with one configured, the proxy POSTs a JSON payload (period, threshold, actual cost — never prompt/response content) once per period+threshold combination.
- **Multi-tenant mode**: opt-in, so single-tenant installs keep working unchanged. Tenants get an API key that's shown once and stored only as a SHA-256 hash plus a lookup prefix; the dashboard and budget alerts are scoped per tenant when the mode is enabled.
- **Privacy by default**: logging captures only metadata — request ID, provider, model, HTTP status, latency, token counts, estimated cost — never prompt or response content.

## Architecture

```text
App → LLM Proxy (log request + cost) → LLM Provider
  → response recorded → Dashboard reads from Postgres
```

## Stack

| Layer | Component |
|---|---|
| Proxy | FastAPI |
| Storage | PostgreSQL |
| Dashboard | Streamlit |
| CI | GitHub Actions with a PostgreSQL 16 service container |

## Replicating this project

Requirements: Python 3.9+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Fill in `LLM_API_KEY` and `DATABASE_URL` in `.env`. A local Postgres instance can be started with:

```bash
docker compose up -d postgres
```

Load the environment, run migrations, then start the server:

```bash
set -a
source .env
set +a
python -m llm_cost_tracker.migrate
uvicorn llm_cost_tracker.main:app --reload
```

In another terminal with the same environment, run the dashboard:

```bash
streamlit run src/llm_cost_tracker/dashboard.py
```

The dashboard defaults to `http://localhost:8501`.

Send a request through the proxy:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Hello"}]}'
```

`LLM_PROVIDER` supports `openai` (default), `groq`, and `gemini` through OpenAI-compatible endpoints; set `LLM_BASE_URL` explicitly for other providers. Streaming responses are not supported. If `DATABASE_URL` is left empty, the app still runs with console logging as a fallback.

### Budget alerts

```bash
DAILY_BUDGET_USD=10.00
MONTHLY_BUDGET_USD=200.00
# ALERT_WEBHOOK_URL=https://example.com/hooks/llm-budget
```

Alert deduplication uses a `budget_alerts` table created by migration — re-run `python -m llm_cost_tracker.migrate` if upgrading an existing install.

### Multi-tenant mode

```bash
python -m llm_cost_tracker.migrate
python -m llm_cost_tracker.tenants create \
  --slug acme \
  --name 'Acme Corporation' \
  --key-name production
```

The CLI prints the API key once. After setting `MULTI_TENANT_ENABLED=true`, calling applications must authenticate with the tenant key:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Authorization: Bearer llmct_REPLACE_WITH_TENANT_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Hello"}]}'
```

Revoke a key with:

```bash
python -m llm_cost_tracker.tenants revoke --slug acme --key-name production
```

Records created before multi-tenant mode was enabled keep `tenant_id = null` and are only visible while the mode is off.

### Access control (single-tenant)

Set `PROXY_API_KEY` and send `Authorization: Bearer <PROXY_API_KEY>` from the calling application. In multi-tenant mode, use the tenant API key instead and ignore `PROXY_API_KEY`.

### Testing

```bash
pytest
```

Without `TEST_DATABASE_URL`, PostgreSQL integration tests are skipped and only unit tests run. To run the full suite against a disposable database:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/llm_cost_tracker_test \
  pytest -q
```

The integration tests run every migration twice to check idempotency, verify the seeded pricing rows, and exercise persistence, tenant authentication, dashboard isolation, and budget-alert deduplication. This target database gets `TRUNCATE`d between runs — never point it at a development or production database.

The GitHub Actions workflow at `.github/workflows/ci.yml` runs unit and integration tests with a PostgreSQL 16 service on every push to `main` and on pull requests.

## Notes

Don't log full prompt/response content if it's sensitive — metadata (token count, model, cost, latency) is enough for cost tracking and keeps user data out of the store.
