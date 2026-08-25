CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_api_keys (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE (tenant_id, name)
);

ALTER TABLE llm_usage
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE budget_alerts
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE budget_alerts
    DROP CONSTRAINT IF EXISTS budget_alerts_period_type_period_start_threshold_usd_key;

CREATE INDEX IF NOT EXISTS llm_usage_tenant_occurred_at_idx
    ON llm_usage (tenant_id, occurred_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS budget_alerts_tenant_period_threshold_idx
    ON budget_alerts (
        COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid),
        period_type,
        period_start,
        threshold_usd
    );
