CREATE TABLE IF NOT EXISTS countries (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    timezone TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exchanges (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL REFERENCES countries(code),
    mic TEXT,
    timezone TEXT NOT NULL,
    currency TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS markets (
    id BIGSERIAL PRIMARY KEY,
    market_code TEXT NOT NULL UNIQUE,
    market_name TEXT NOT NULL,
    country_code TEXT NOT NULL REFERENCES countries(code),
    region TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_proxies (
    id BIGSERIAL PRIMARY KEY,
    market_code TEXT NOT NULL REFERENCES markets(market_code),
    proxy_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange_code TEXT NOT NULL,
    currency TEXT NOT NULL,
    priority INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (market_code, symbol, exchange_code)
);

CREATE TABLE IF NOT EXISTS market_bars_daily (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC(18, 6) NOT NULL,
    high NUMERIC(18, 6) NOT NULL,
    low NUMERIC(18, 6) NOT NULL,
    close NUMERIC(18, 6) NOT NULL,
    adjusted_close NUMERIC(18, 6),
    volume NUMERIC(22, 2),
    currency TEXT NOT NULL,
    source TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, trade_date, source)
);

CREATE INDEX IF NOT EXISTS idx_market_bars_daily_symbol_date
    ON market_bars_daily (symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS market_features_daily (
    id BIGSERIAL PRIMARY KEY,
    market_code TEXT NOT NULL REFERENCES markets(market_code),
    trade_date DATE NOT NULL,
    price_proxy TEXT NOT NULL,
    ret_20d NUMERIC(12, 6),
    ret_60d NUMERIC(12, 6),
    ret_120d NUMERIC(12, 6),
    ret_252d NUMERIC(12, 6),
    ma_50 NUMERIC(18, 6),
    ma_120 NUMERIC(18, 6),
    ma_200 NUMERIC(18, 6),
    vol_20d NUMERIC(12, 6),
    vol_60d NUMERIC(12, 6),
    drawdown_60d NUMERIC(12, 6),
    relative_strength_world NUMERIC(12, 6),
    fx_ret_60d NUMERIC(12, 6),
    breadth_proxy NUMERIC(12, 6),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (market_code, trade_date)
);

CREATE TABLE IF NOT EXISTS market_regime_daily (
    id BIGSERIAL PRIMARY KEY,
    market_code TEXT NOT NULL REFERENCES markets(market_code),
    trade_date DATE NOT NULL,
    regime_status TEXT NOT NULL,
    bull_score NUMERIC(12, 6) NOT NULL,
    trend_score NUMERIC(12, 6) NOT NULL,
    relative_strength_score NUMERIC(12, 6) NOT NULL,
    vol_penalty_score NUMERIC(12, 6) NOT NULL,
    fx_penalty_score NUMERIC(12, 6) NOT NULL,
    trigger_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    source_used JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (market_code, trade_date, rule_version, config_version)
);

CREATE TABLE IF NOT EXISTS audit_job_runs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    UNIQUE (job_name, idempotency_key)
);
