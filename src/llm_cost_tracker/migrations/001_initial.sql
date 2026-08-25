CREATE TABLE IF NOT EXISTS model_pricing (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_price_per_million NUMERIC(20, 10) NOT NULL CHECK (input_price_per_million >= 0),
    output_price_per_million NUMERIC(20, 10) NOT NULL CHECK (output_price_per_million >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    source_url TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, model)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id UUID NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms NUMERIC(14, 2) NOT NULL CHECK (latency_ms >= 0),
    input_tokens INTEGER CHECK (input_tokens >= 0),
    output_tokens INTEGER CHECK (output_tokens >= 0),
    total_tokens INTEGER CHECK (total_tokens >= 0),
    estimated_cost_usd NUMERIC(20, 10) CHECK (estimated_cost_usd >= 0)
);

CREATE INDEX IF NOT EXISTS llm_usage_occurred_at_idx ON llm_usage (occurred_at DESC);
CREATE INDEX IF NOT EXISTS llm_usage_provider_model_idx ON llm_usage (provider, model);
