import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    market_code TEXT PRIMARY KEY,
    market_name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    region TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_proxies (
    market_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    proxy_type TEXT NOT NULL,
    exchange_code TEXT NOT NULL,
    currency TEXT NOT NULL,
    priority INTEGER NOT NULL,
    PRIMARY KEY (market_code, symbol),
    FOREIGN KEY (market_code) REFERENCES markets(market_code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_features_daily (
    market_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    price_proxy TEXT NOT NULL,
    close REAL NOT NULL,
    ma_120 REAL NOT NULL,
    ma_200 REAL NOT NULL,
    ret_60d REAL NOT NULL,
    ret_120d REAL NOT NULL,
    vol_20d REAL NOT NULL,
    drawdown_60d REAL NOT NULL,
    relative_strength_world REAL NOT NULL,
    fx_ret_60d REAL NOT NULL,
    avg_volume_recent REAL NOT NULL DEFAULT 0,
    avg_volume_prior REAL NOT NULL DEFAULT 0,
    volume_ratio_5d REAL NOT NULL DEFAULT 0,
    consecutive_up_weeks INTEGER NOT NULL DEFAULT 0,
    ma_5 REAL NOT NULL DEFAULT 0,
    ma_10 REAL NOT NULL DEFAULT 0,
    ma_20 REAL NOT NULL DEFAULT 0,
    ma_60 REAL NOT NULL DEFAULT 0,
    ret_1d REAL NOT NULL DEFAULT 0,
    ret_5d REAL NOT NULL DEFAULT 0,
    turnover_ratio_20d REAL NOT NULL DEFAULT 0,
    avg_turnover_ratio_3d REAL NOT NULL DEFAULT 0,
    volume_up_days_2d INTEGER NOT NULL DEFAULT 0,
    volume_up_days_3d INTEGER NOT NULL DEFAULT 0,
    consecutive_up_days INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, trade_date)
);

CREATE TABLE IF NOT EXISTS market_regime_daily (
    market_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    regime_status TEXT NOT NULL,
    bull_score REAL NOT NULL,
    trend_score REAL NOT NULL,
    relative_strength_score REAL NOT NULL,
    risk_penalty_score REAL NOT NULL,
    trigger_flags_json TEXT NOT NULL,
    source_used_json TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, trade_date)
);

CREATE TABLE IF NOT EXISTS stock_seed_pool_daily (
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    exchange TEXT NOT NULL,
    currency TEXT NOT NULL,
    country_code TEXT NOT NULL,
    seed_type TEXT NOT NULL,
    theme_tags_json TEXT NOT NULL DEFAULT '[]',
    theme_score REAL NOT NULL DEFAULT 0,
    valuation_score REAL NOT NULL DEFAULT 0,
    size_score REAL NOT NULL DEFAULT 0,
    valuation_band TEXT NOT NULL DEFAULT '',
    market_cap_bucket TEXT NOT NULL DEFAULT '',
    seed_reason TEXT NOT NULL DEFAULT '',
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, market_code, ticker)
);

CREATE TABLE IF NOT EXISTS stock_metadata (
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    exchange TEXT NOT NULL,
    currency TEXT NOT NULL,
    country_code TEXT NOT NULL,
    theme_tags_json TEXT NOT NULL DEFAULT '[]',
    theme_score REAL NOT NULL DEFAULT 0,
    valuation_score REAL NOT NULL DEFAULT 0,
    size_score REAL NOT NULL DEFAULT 0,
    valuation_band TEXT NOT NULL DEFAULT '',
    market_cap_bucket TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market_code, ticker)
);

CREATE TABLE IF NOT EXISTS stock_bars_daily (
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, ticker, trade_date)
);

CREATE TABLE IF NOT EXISTS stock_universe_daily (
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    exchange TEXT NOT NULL,
    currency TEXT NOT NULL,
    country_code TEXT NOT NULL,
    market_cap REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    price_position REAL,
    momentum_pct REAL NOT NULL DEFAULT 0,
    volume_ratio REAL NOT NULL DEFAULT 0,
    ret_5d REAL,
    ret_20d REAL,
    ret_60d REAL,
    ma_20 REAL,
    ma_60 REAL,
    avg_dollar_volume_3d REAL,
    avg_dollar_volume_20d REAL,
    volume_ratio_3d REAL,
    volume_up_days_5d INTEGER,
    distance_to_60d_high REAL,
    momentum_acceleration REAL,
    vol_20d REAL,
    theme_tags_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, market_code, ticker)
);

CREATE TABLE IF NOT EXISTS stock_candidates_daily (
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    regime_trade_date TEXT,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    seed_type TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    close REAL NOT NULL,
    ret_5d REAL NOT NULL DEFAULT 0,
    ret_20d REAL NOT NULL DEFAULT 0,
    ret_60d REAL NOT NULL DEFAULT 0,
    ma_20 REAL NOT NULL DEFAULT 0,
    ma_60 REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_3d REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_5d REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_20d REAL NOT NULL DEFAULT 0,
    volume_ratio_3d REAL NOT NULL DEFAULT 0,
    volume_ratio_5d REAL NOT NULL DEFAULT 0,
    volume_up_days_5d INTEGER NOT NULL DEFAULT 0,
    distance_to_60d_high REAL NOT NULL DEFAULT 0,
    momentum_acceleration REAL NOT NULL DEFAULT 0,
    vol_20d REAL NOT NULL DEFAULT 0,
    coarse_score REAL NOT NULL,
    composite_score REAL NOT NULL DEFAULT 0,
    theme_score REAL NOT NULL DEFAULT 0,
    lagging_score REAL NOT NULL DEFAULT 0,
    trend_recovery_score REAL NOT NULL DEFAULT 0,
    momentum_acceleration_score REAL NOT NULL DEFAULT 0,
    volume_probe_score REAL NOT NULL DEFAULT 0,
    risk_control_score REAL NOT NULL DEFAULT 0,
    valuation_band TEXT NOT NULL DEFAULT '',
    market_cap_bucket TEXT NOT NULL DEFAULT '',
    theme_tags_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    screen_flags_json TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, ticker, trade_date)
);

CREATE TABLE IF NOT EXISTS stock_watchlist_daily (
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    regime_trade_date TEXT,
    watch_rank INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    close REAL NOT NULL,
    ret_5d REAL NOT NULL DEFAULT 0,
    ret_20d REAL NOT NULL DEFAULT 0,
    ret_60d REAL NOT NULL DEFAULT 0,
    ma_20 REAL NOT NULL DEFAULT 0,
    ma_60 REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_3d REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_5d REAL NOT NULL DEFAULT 0,
    avg_dollar_volume_20d REAL NOT NULL DEFAULT 0,
    volume_ratio_3d REAL NOT NULL DEFAULT 0,
    volume_ratio_5d REAL NOT NULL DEFAULT 0,
    volume_up_days_5d INTEGER NOT NULL DEFAULT 0,
    distance_to_60d_high REAL NOT NULL DEFAULT 0,
    momentum_acceleration REAL NOT NULL DEFAULT 0,
    vol_20d REAL NOT NULL DEFAULT 0,
    composite_score REAL NOT NULL,
    theme_score REAL NOT NULL,
    lagging_score REAL NOT NULL DEFAULT 0,
    trend_recovery_score REAL NOT NULL DEFAULT 0,
    momentum_acceleration_score REAL NOT NULL DEFAULT 0,
    volume_probe_score REAL NOT NULL DEFAULT 0,
    risk_control_score REAL NOT NULL DEFAULT 0,
    valuation_band TEXT NOT NULL,
    market_cap_bucket TEXT NOT NULL,
    theme_tags_json TEXT NOT NULL,
    source TEXT NOT NULL,
    watch_reason TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, ticker)
);

CREATE TABLE IF NOT EXISTS selection_heat_daily (
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    theme_type TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    raw_heat_score REAL NOT NULL,
    smoothed_heat_score REAL NOT NULL,
    constituent_count INTEGER NOT NULL,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, market_code, theme_type, theme_name)
);

CREATE TABLE IF NOT EXISTS trade_signals_daily (
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'BUY',
    signal_type TEXT NOT NULL,
    triggered INTEGER NOT NULL,
    signal_reason TEXT NOT NULL,
    close REAL NOT NULL,
    volume_ratio_5d REAL NOT NULL,
    threshold_volume_ratio REAL NOT NULL,
    order_notional REAL NOT NULL,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, ticker, signal_type)
);

CREATE TABLE IF NOT EXISTS paper_orders (
    order_id TEXT PRIMARY KEY,
    trade_date TEXT NOT NULL,
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    status TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_reason TEXT NOT NULL DEFAULT '',
    position_effect TEXT NOT NULL DEFAULT '',
    position_status_before TEXT NOT NULL DEFAULT '',
    position_status_after TEXT NOT NULL DEFAULT '',
    requested_notional REAL NOT NULL,
    quantity REAL NOT NULL,
    limit_price REAL NOT NULL,
    filled_price REAL NOT NULL,
    filled_at TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_positions (
    market_code TEXT NOT NULL,
    ticker TEXT NOT NULL,
    opened_trade_date TEXT NOT NULL,
    last_trade_date TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    invested_notional REAL NOT NULL,
    peak_price REAL NOT NULL DEFAULT 0,
    last_close REAL NOT NULL DEFAULT 0,
    last_volume_ratio_5d REAL NOT NULL DEFAULT 0,
    consecutive_decline_days INTEGER NOT NULL DEFAULT 0,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    unrealized_return REAL NOT NULL DEFAULT 0,
    entry_signal_type TEXT NOT NULL DEFAULT '',
    last_signal_type TEXT NOT NULL DEFAULT '',
    last_signal_reason TEXT NOT NULL DEFAULT '',
    closed_trade_date TEXT,
    closed_price REAL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, ticker)
);
"""

EXTRA_COLUMNS = {
    'market_features_daily': {
        'ma_5': 'REAL NOT NULL DEFAULT 0',
        'ma_10': 'REAL NOT NULL DEFAULT 0',
        'ma_20': 'REAL NOT NULL DEFAULT 0',
        'ma_60': 'REAL NOT NULL DEFAULT 0',
        'ret_1d': 'REAL NOT NULL DEFAULT 0',
        'ret_5d': 'REAL NOT NULL DEFAULT 0',
        'turnover_ratio_20d': 'REAL NOT NULL DEFAULT 0',
        'avg_turnover_ratio_3d': 'REAL NOT NULL DEFAULT 0',
        'volume_up_days_2d': 'INTEGER NOT NULL DEFAULT 0',
        'volume_up_days_3d': 'INTEGER NOT NULL DEFAULT 0',
        'consecutive_up_days': 'INTEGER NOT NULL DEFAULT 0',
    },
    'stock_metadata': {
        'theme_tags_json': "TEXT NOT NULL DEFAULT '[]'",
        'theme_score': 'REAL NOT NULL DEFAULT 0',
        'valuation_score': 'REAL NOT NULL DEFAULT 0',
        'size_score': 'REAL NOT NULL DEFAULT 0',
        'valuation_band': "TEXT NOT NULL DEFAULT ''",
        'market_cap_bucket': "TEXT NOT NULL DEFAULT ''",
    },
    'stock_universe_daily': {
        'ret_5d': 'REAL',
        'ret_20d': 'REAL',
        'ret_60d': 'REAL',
        'ma_20': 'REAL',
        'ma_60': 'REAL',
        'avg_dollar_volume_3d': 'REAL',
        'avg_dollar_volume_20d': 'REAL',
        'volume_ratio_3d': 'REAL',
        'volume_up_days_5d': 'INTEGER',
        'distance_to_60d_high': 'REAL',
        'momentum_acceleration': 'REAL',
        'vol_20d': 'REAL',
    },
    'stock_candidates_daily': {
        'regime_trade_date': 'TEXT',
        'rank': 'INTEGER NOT NULL DEFAULT 0',
        'ret_5d': 'REAL NOT NULL DEFAULT 0',
        'ret_20d': 'REAL NOT NULL DEFAULT 0',
        'ma_20': 'REAL NOT NULL DEFAULT 0',
        'ma_60': 'REAL NOT NULL DEFAULT 0',
        'avg_dollar_volume_3d': 'REAL NOT NULL DEFAULT 0',
        'avg_dollar_volume_5d': 'REAL NOT NULL DEFAULT 0',
        'volume_ratio_3d': 'REAL NOT NULL DEFAULT 0',
        'volume_ratio_5d': 'REAL NOT NULL DEFAULT 0',
        'volume_up_days_5d': 'INTEGER NOT NULL DEFAULT 0',
        'distance_to_60d_high': 'REAL NOT NULL DEFAULT 0',
        'momentum_acceleration': 'REAL NOT NULL DEFAULT 0',
        'composite_score': 'REAL NOT NULL DEFAULT 0',
        'theme_score': 'REAL NOT NULL DEFAULT 0',
        'lagging_score': 'REAL NOT NULL DEFAULT 0',
        'trend_recovery_score': 'REAL NOT NULL DEFAULT 0',
        'momentum_acceleration_score': 'REAL NOT NULL DEFAULT 0',
        'volume_probe_score': 'REAL NOT NULL DEFAULT 0',
        'risk_control_score': 'REAL NOT NULL DEFAULT 0',
        'valuation_band': "TEXT NOT NULL DEFAULT ''",
        'market_cap_bucket': "TEXT NOT NULL DEFAULT ''",
        'theme_tags_json': "TEXT NOT NULL DEFAULT '[]'",
    },
    'stock_watchlist_daily': {
        'ret_5d': 'REAL NOT NULL DEFAULT 0',
        'ret_20d': 'REAL NOT NULL DEFAULT 0',
        'ma_20': 'REAL NOT NULL DEFAULT 0',
        'ma_60': 'REAL NOT NULL DEFAULT 0',
        'avg_dollar_volume_3d': 'REAL NOT NULL DEFAULT 0',
        'avg_dollar_volume_5d': 'REAL NOT NULL DEFAULT 0',
        'volume_ratio_3d': 'REAL NOT NULL DEFAULT 0',
        'volume_ratio_5d': 'REAL NOT NULL DEFAULT 0',
        'volume_up_days_5d': 'INTEGER NOT NULL DEFAULT 0',
        'distance_to_60d_high': 'REAL NOT NULL DEFAULT 0',
        'momentum_acceleration': 'REAL NOT NULL DEFAULT 0',
        'lagging_score': 'REAL NOT NULL DEFAULT 0',
        'trend_recovery_score': 'REAL NOT NULL DEFAULT 0',
        'momentum_acceleration_score': 'REAL NOT NULL DEFAULT 0',
        'volume_probe_score': 'REAL NOT NULL DEFAULT 0',
        'risk_control_score': 'REAL NOT NULL DEFAULT 0',
    },
    'trade_signals_daily': {
        'side': "TEXT NOT NULL DEFAULT 'BUY'",
    },
    'paper_orders': {
        'signal_reason': "TEXT NOT NULL DEFAULT ''",
        'position_effect': "TEXT NOT NULL DEFAULT ''",
        'position_status_before': "TEXT NOT NULL DEFAULT ''",
        'position_status_after': "TEXT NOT NULL DEFAULT ''",
    },
    'paper_positions': {
        'peak_price': 'REAL NOT NULL DEFAULT 0',
        'last_close': 'REAL NOT NULL DEFAULT 0',
        'last_volume_ratio_5d': 'REAL NOT NULL DEFAULT 0',
        'consecutive_decline_days': 'INTEGER NOT NULL DEFAULT 0',
        'unrealized_pnl': 'REAL NOT NULL DEFAULT 0',
        'unrealized_return': 'REAL NOT NULL DEFAULT 0',
        'entry_signal_type': "TEXT NOT NULL DEFAULT ''",
        'last_signal_type': "TEXT NOT NULL DEFAULT ''",
        'last_signal_reason': "TEXT NOT NULL DEFAULT ''",
        'closed_trade_date': 'TEXT',
        'closed_price': 'REAL',
    },
}


def initialize_sqlite(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite_session(db_path) as connection:
        connection.executescript(SQLITE_SCHEMA)
        for table_name, columns in EXTRA_COLUMNS.items():
            existing_columns = {row['name'] for row in connection.execute(f'PRAGMA table_info({table_name})').fetchall()}
            for column_name, column_spec in columns.items():
                if column_name not in existing_columns:
                    connection.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_spec}')


@contextmanager
def sqlite_session(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
