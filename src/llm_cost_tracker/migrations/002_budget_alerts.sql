CREATE TABLE IF NOT EXISTS budget_alerts (
    id BIGSERIAL PRIMARY KEY,
    period_type TEXT NOT NULL CHECK (period_type IN ('daily', 'monthly')),
    period_start DATE NOT NULL,
    threshold_usd NUMERIC(20, 10) NOT NULL CHECK (threshold_usd >= 0),
    actual_cost_usd NUMERIC(20, 10) NOT NULL CHECK (actual_cost_usd >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (period_type, period_start, threshold_usd)
);
