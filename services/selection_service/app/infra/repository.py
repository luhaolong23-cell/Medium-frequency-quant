import json
from datetime import date
from pathlib import Path

from packages.domain_core.selection.entities import (
    StockCandidate,
    StockMetadata,
    StockSeedSnapshot,
    StockWatchItem,
    StockUniverseSnapshot,
    ThemeHeatSnapshot,
    StockDailyBar,
)
from packages.shared.contracts import (
    StockCandidateRepository,
    StockMetadataRepository,
    StockSeedPoolRepository,
    StockUniverseRepository,
    StockBarRepository,
    StockWatchlistRepository,
    ThemeHeatRepository,
)
from packages.shared.sqlite import initialize_sqlite, sqlite_session


class InMemorySelectionRepository(
    StockSeedPoolRepository,
    StockMetadataRepository,
    StockUniverseRepository,
    StockBarRepository,
    StockCandidateRepository,
    StockWatchlistRepository,
    ThemeHeatRepository,
):
    backend_name = "memory"

    def __init__(self) -> None:
        self._seed_pool: dict[tuple[date, str, str], StockSeedSnapshot] = {}
        self._metadata: dict[tuple[str, str], StockMetadata] = {}
        self._market_universe: dict[tuple[date, str, str], StockUniverseSnapshot] = {}
        self._stock_bars: dict[tuple[str, str, date], StockDailyBar] = {}
        self._candidates: dict[tuple[str, str, date], StockCandidate] = {}
        self._watchlist: dict[tuple[date, str], StockWatchItem] = {}
        self._heat_snapshots: dict[tuple[date, str, str, str], ThemeHeatSnapshot] = {}

    def replace_seed_pool(self, trade_date: date, market_codes: list[str], seeds: list[StockSeedSnapshot]) -> None:
        wanted = set(market_codes)
        self._seed_pool = {
            key: seed
            for key, seed in self._seed_pool.items()
            if not (key[0] == trade_date and key[1] in wanted)
        }
        for seed in seeds:
            self._seed_pool[(seed.trade_date, seed.market_code, seed.ticker)] = seed

    def list_seed_pool(self, trade_date: date, market_code: str | None = None) -> list[StockSeedSnapshot]:
        rows = [
            seed
            for (current_date, current_market_code, _), seed in self._seed_pool.items()
            if current_date == trade_date and (market_code is None or current_market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (-item.theme_score, item.market_code, item.ticker))

    def upsert_metadata(self, metadata_rows: list[StockMetadata]) -> None:
        for row in metadata_rows:
            self._metadata[(row.market_code, row.ticker)] = row

    def get_metadata(self, market_code: str, ticker: str) -> StockMetadata | None:
        return self._metadata.get((market_code, ticker))

    def replace_market_universe(self, trade_date: date, market_codes: list[str], rows: list[StockUniverseSnapshot]) -> None:
        wanted = set(market_codes)
        self._market_universe = {
            key: row
            for key, row in self._market_universe.items()
            if not (key[0] == trade_date and key[1] in wanted)
        }
        for row in rows:
            self._market_universe[(row.trade_date, row.market_code, row.ticker)] = row

    def list_market_universe(self, trade_date: date, market_code: str | None = None) -> list[StockUniverseSnapshot]:
        rows = [
            row
            for (current_date, current_market_code, _), row in self._market_universe.items()
            if current_date == trade_date and (market_code is None or current_market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.market_code, item.ticker))

    def upsert_stock_bars(self, bars: list[StockDailyBar]) -> None:
        for bar in bars:
            self._stock_bars[(bar.market_code, bar.ticker, bar.trade_date)] = bar

    def list_stock_bars(self, market_code: str, ticker: str, trade_date: date | None = None) -> list[StockDailyBar]:
        rows = [
            bar
            for (current_market_code, current_ticker, current_trade_date), bar in self._stock_bars.items()
            if current_market_code == market_code
            and current_ticker == ticker
            and (trade_date is None or current_trade_date <= trade_date)
        ]
        return sorted(rows, key=lambda item: item.trade_date)

    def get_latest_stock_bar_date(self, market_code: str, ticker: str) -> date | None:
        rows = self.list_stock_bars(market_code, ticker)
        if not rows:
            return None
        return rows[-1].trade_date

    def replace_candidates(self, trade_date: date, market_codes: list[str], candidates: list[StockCandidate]) -> None:
        wanted = set(market_codes)
        self._candidates = {
            key: candidate
            for key, candidate in self._candidates.items()
            if not (key[2] == trade_date and key[0] in wanted)
        }
        for candidate in candidates:
            self._candidates[(candidate.market_code, candidate.ticker, candidate.trade_date)] = candidate

    def list_candidates(self, trade_date: date, market_code: str | None = None) -> list[StockCandidate]:
        rows = [
            candidate
            for (_, _, current_date), candidate in self._candidates.items()
            if current_date == trade_date and (market_code is None or candidate.market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.rank, -item.composite_score, item.ticker))

    def replace_watchlist(self, trade_date: date, watchlist: list[StockWatchItem]) -> None:
        self._watchlist = {
            key: item for key, item in self._watchlist.items() if key[0] != trade_date
        }
        for item in watchlist:
            self._watchlist[(item.trade_date, item.ticker)] = item

    @staticmethod
    def _watchlist_insert_values(item: StockWatchItem, *, include_legacy: set[str]) -> list[tuple[str, object]]:
        values = [
            ('trade_date', item.trade_date.isoformat()),
            ('market_code', item.market_code),
            ('ticker', item.ticker),
            ('regime_trade_date', item.regime_trade_date.isoformat() if item.regime_trade_date else None),
            ('watch_rank', item.watch_rank),
            ('company_name', item.company_name),
            ('sector', item.sector),
            ('industry', item.industry),
            ('close', item.close),
            ('ret_5d', item.ret_5d),
            ('ret_20d', item.ret_20d),
            ('ret_60d', item.ret_60d),
            ('ma_20', item.ma_20),
            ('ma_60', item.ma_60),
            ('avg_dollar_volume_3d', item.avg_dollar_volume_3d),
            ('avg_dollar_volume_5d', item.avg_dollar_volume_5d),
            ('avg_dollar_volume_20d', item.avg_dollar_volume_20d),
            ('volume_ratio_3d', item.volume_ratio_3d),
            ('volume_ratio_5d', item.volume_ratio_5d),
            ('volume_up_days_5d', item.volume_up_days_5d),
            ('distance_to_60d_high', item.distance_to_60d_high),
            ('momentum_acceleration', item.momentum_acceleration),
            ('vol_20d', item.vol_20d),
            ('composite_score', item.composite_score),
            ('theme_score', item.theme_score),
            ('lagging_score', item.lagging_score),
            ('trend_recovery_score', item.trend_recovery_score),
            ('momentum_acceleration_score', item.momentum_acceleration_score),
            ('volume_probe_score', item.volume_probe_score),
            ('risk_control_score', item.risk_control_score),
            ('valuation_band', item.valuation_band),
            ('market_cap_bucket', item.market_cap_bucket),
            ('theme_tags_json', json.dumps(item.theme_tags, sort_keys=True)),
            ('source', item.source),
            ('watch_reason', item.watch_reason),
        ]
        if 'volume_score' in include_legacy:
            values.append(('volume_score', item.volume_probe_score))
        if 'valuation_score' in include_legacy:
            values.append(('valuation_score', 0.0))
        if 'size_score' in include_legacy:
            values.append(('size_score', 0.0))
        return values

    def list_watchlist(self, trade_date: date, market_code: str | None = None) -> list[StockWatchItem]:
        rows = [
            item
            for (current_date, _), item in self._watchlist.items()
            if current_date == trade_date and (market_code is None or item.market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.watch_rank, item.ticker))

    def replace_heat_snapshots(self, trade_date: date, market_codes: list[str], snapshots: list[ThemeHeatSnapshot]) -> None:
        for snapshot in snapshots:
            key = (snapshot.trade_date, snapshot.market_code, snapshot.theme_type, snapshot.theme_name)
            self._heat_snapshots[key] = snapshot

    def list_heat_snapshots(
        self,
        trade_date: date,
        market_code: str | None = None,
        theme_type: str | None = None,
    ) -> list[ThemeHeatSnapshot]:
        rows = [
            snapshot
            for (current_date, current_market_code, current_theme_type, _), snapshot in self._heat_snapshots.items()
            if current_date == trade_date
            and (market_code is None or current_market_code == market_code)
            and (theme_type is None or current_theme_type == theme_type)
        ]
        return sorted(rows, key=lambda item: (-item.smoothed_heat_score, -item.raw_heat_score, item.theme_type, item.theme_name))


class SqliteSelectionRepository(
    StockSeedPoolRepository,
    StockMetadataRepository,
    StockUniverseRepository,
    StockBarRepository,
    StockCandidateRepository,
    StockWatchlistRepository,
    ThemeHeatRepository,
):
    backend_name = "sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        initialize_sqlite(self._db_path)

    def replace_seed_pool(self, trade_date: date, market_codes: list[str], seeds: list[StockSeedSnapshot]) -> None:
        with sqlite_session(self._db_path) as connection:
            if market_codes:
                placeholders = ', '.join('?' for _ in market_codes)
                connection.execute(
                    f"DELETE FROM stock_seed_pool_daily WHERE trade_date = ? AND market_code IN ({placeholders})",
                    [trade_date.isoformat(), *market_codes],
                )
            connection.executemany(
                """
                INSERT INTO stock_seed_pool_daily (
                    trade_date, market_code, ticker, company_name, sector, industry, exchange, currency, country_code,
                    seed_type, theme_tags_json, theme_score, valuation_score, size_score, valuation_band, market_cap_bucket, seed_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        seed.trade_date.isoformat(),
                        seed.market_code,
                        seed.ticker,
                        seed.company_name,
                        seed.sector,
                        seed.industry,
                        seed.exchange,
                        seed.currency,
                        seed.country_code,
                        seed.seed_type,
                        json.dumps(seed.theme_tags, sort_keys=True),
                        seed.theme_score,
                        seed.valuation_score,
                        seed.size_score,
                        seed.valuation_band,
                        seed.market_cap_bucket,
                        seed.seed_reason,
                    )
                    for seed in seeds
                ],
            )

    def list_seed_pool(self, trade_date: date, market_code: str | None = None) -> list[StockSeedSnapshot]:
        query = "SELECT * FROM stock_seed_pool_daily WHERE trade_date = ?"
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += " AND market_code = ?"
            params.append(market_code)
        query += " ORDER BY theme_score DESC, market_code, ticker"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_seed_snapshot(row) for row in rows]

    def upsert_metadata(self, metadata_rows: list[StockMetadata]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO stock_metadata (
                    market_code,
                    ticker,
                    company_name,
                    sector,
                    industry,
                    exchange,
                    currency,
                    country_code,
                    theme_tags_json,
                    theme_score,
                    valuation_score,
                    size_score,
                    valuation_band,
                    market_cap_bucket,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_code, ticker) DO UPDATE SET
                    company_name = excluded.company_name,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    exchange = excluded.exchange,
                    currency = excluded.currency,
                    country_code = excluded.country_code,
                    theme_tags_json = excluded.theme_tags_json,
                    theme_score = excluded.theme_score,
                    valuation_score = excluded.valuation_score,
                    size_score = excluded.size_score,
                    valuation_band = excluded.valuation_band,
                    market_cap_bucket = excluded.market_cap_bucket,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row.market_code,
                        row.ticker,
                        row.company_name,
                        row.sector,
                        row.industry,
                        row.exchange,
                        row.currency,
                        row.country_code,
                        json.dumps(row.theme_tags, sort_keys=True),
                        row.theme_score,
                        row.valuation_score,
                        row.size_score,
                        row.valuation_band,
                        row.market_cap_bucket,
                        row.updated_at.isoformat(),
                    )
                    for row in metadata_rows
                ],
            )

    def get_metadata(self, market_code: str, ticker: str) -> StockMetadata | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT * FROM stock_metadata WHERE market_code = ? AND ticker = ?",
                (market_code, ticker),
            ).fetchone()
        if row is None:
            return None
        return StockMetadata(
            market_code=row['market_code'],
            ticker=row['ticker'],
            company_name=row['company_name'],
            sector=row['sector'],
            industry=row['industry'],
            exchange=row['exchange'],
            currency=row['currency'],
            country_code=row['country_code'],
            theme_tags=json.loads(row['theme_tags_json']),
            theme_score=float(row['theme_score']),
            valuation_score=float(row['valuation_score']),
            size_score=float(row['size_score']),
            valuation_band=row['valuation_band'],
            market_cap_bucket=row['market_cap_bucket'],
            updated_at=date.fromisoformat(row['updated_at']),
        )

    def replace_market_universe(self, trade_date: date, market_codes: list[str], rows: list[StockUniverseSnapshot]) -> None:
        with sqlite_session(self._db_path) as connection:
            if market_codes:
                placeholders = ', '.join('?' for _ in market_codes)
                connection.execute(
                    f"DELETE FROM stock_universe_daily WHERE trade_date = ? AND market_code IN ({placeholders})",
                    [trade_date.isoformat(), *market_codes],
                )
            connection.executemany(
                """
                INSERT INTO stock_universe_daily (
                    trade_date, market_code, ticker, company_name, sector, industry, exchange, currency, country_code,
                    market_cap, price, price_position, momentum_pct, volume_ratio, ret_5d, ret_20d, ret_60d, ma_20, ma_60,
                    avg_dollar_volume_3d, avg_dollar_volume_20d, volume_ratio_3d, volume_up_days_5d, distance_to_60d_high,
                    momentum_acceleration, vol_20d, theme_tags_json, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.trade_date.isoformat(),
                        row.market_code,
                        row.ticker,
                        row.company_name,
                        row.sector,
                        row.industry,
                        row.exchange,
                        row.currency,
                        row.country_code,
                        row.market_cap,
                        row.price,
                        row.price_position,
                        row.momentum_pct,
                        row.volume_ratio,
                        row.ret_5d,
                        row.ret_20d,
                        row.ret_60d,
                        row.ma_20,
                        row.ma_60,
                        row.avg_dollar_volume_3d,
                        row.avg_dollar_volume_20d,
                        row.volume_ratio_3d,
                        row.volume_up_days_5d,
                        row.distance_to_60d_high,
                        row.momentum_acceleration,
                        row.vol_20d,
                        json.dumps(row.theme_tags, sort_keys=True),
                        row.source,
                    )
                    for row in rows
                ],
            )

    def list_market_universe(self, trade_date: date, market_code: str | None = None) -> list[StockUniverseSnapshot]:
        query = "SELECT * FROM stock_universe_daily WHERE trade_date = ?"
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += " AND market_code = ?"
            params.append(market_code)
        query += " ORDER BY market_code, ticker"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_market_universe_snapshot(row) for row in rows]

    def upsert_stock_bars(self, bars: list[StockDailyBar]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO stock_bars_daily (
                    market_code, ticker, trade_date, close, volume, source
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_code, ticker, trade_date) DO UPDATE SET
                    close = excluded.close,
                    volume = excluded.volume,
                    source = excluded.source
                """,
                [
                    (
                        bar.market_code,
                        bar.ticker,
                        bar.trade_date.isoformat(),
                        bar.close,
                        bar.volume,
                        bar.source,
                    )
                    for bar in bars
                ],
            )

    def list_stock_bars(self, market_code: str, ticker: str, trade_date: date | None = None) -> list[StockDailyBar]:
        query = "SELECT * FROM stock_bars_daily WHERE market_code = ? AND ticker = ?"
        params: list[str] = [market_code, ticker]
        if trade_date is not None:
            query += " AND trade_date <= ?"
            params.append(trade_date.isoformat())
        query += " ORDER BY trade_date"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_stock_bar(row) for row in rows]

    def get_latest_stock_bar_date(self, market_code: str, ticker: str) -> date | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT MAX(trade_date) AS trade_date FROM stock_bars_daily WHERE market_code = ? AND ticker = ?",
                (market_code, ticker),
            ).fetchone()
        if row is None or row['trade_date'] is None:
            return None
        return date.fromisoformat(row['trade_date'])

    def replace_candidates(self, trade_date: date, market_codes: list[str], candidates: list[StockCandidate]) -> None:
        with sqlite_session(self._db_path) as connection:
            if market_codes:
                placeholders = ', '.join('?' for _ in market_codes)
                connection.execute(
                    f"DELETE FROM stock_candidates_daily WHERE trade_date = ? AND market_code IN ({placeholders})",
                    [trade_date.isoformat(), *market_codes],
                )
            connection.executemany(
                """
                INSERT INTO stock_candidates_daily (
                    market_code, ticker, trade_date, regime_trade_date, company_name, sector, industry, seed_type, rank, close,
                    ret_5d, ret_20d, ret_60d, ma_20, ma_60, avg_dollar_volume_3d, avg_dollar_volume_5d, avg_dollar_volume_20d,
                    volume_ratio_3d, volume_ratio_5d, volume_up_days_5d, distance_to_60d_high, momentum_acceleration, vol_20d,
                    coarse_score, composite_score, theme_score, lagging_score, trend_recovery_score, momentum_acceleration_score,
                    volume_probe_score, risk_control_score, valuation_band, market_cap_bucket, theme_tags_json, source, screen_flags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        candidate.market_code,
                        candidate.ticker,
                        candidate.trade_date.isoformat(),
                        candidate.regime_trade_date.isoformat() if candidate.regime_trade_date else None,
                        candidate.company_name,
                        candidate.sector,
                        candidate.industry,
                        candidate.seed_type,
                        candidate.rank,
                        candidate.close,
                        candidate.ret_5d,
                        candidate.ret_20d,
                        candidate.ret_60d,
                        candidate.ma_20,
                        candidate.ma_60,
                        candidate.avg_dollar_volume_3d,
                        candidate.avg_dollar_volume_5d,
                        candidate.avg_dollar_volume_20d,
                        candidate.volume_ratio_3d,
                        candidate.volume_ratio_5d,
                        candidate.volume_up_days_5d,
                        candidate.distance_to_60d_high,
                        candidate.momentum_acceleration,
                        candidate.vol_20d,
                        candidate.coarse_score,
                        candidate.composite_score,
                        candidate.theme_score,
                        candidate.lagging_score,
                        candidate.trend_recovery_score,
                        candidate.momentum_acceleration_score,
                        candidate.volume_probe_score,
                        candidate.risk_control_score,
                        candidate.valuation_band,
                        candidate.market_cap_bucket,
                        json.dumps(candidate.theme_tags, sort_keys=True),
                        candidate.source,
                        json.dumps(candidate.screen_flags, sort_keys=True),
                    )
                    for candidate in candidates
                ],
            )

    def list_candidates(self, trade_date: date, market_code: str | None = None) -> list[StockCandidate]:
        query = "SELECT * FROM stock_candidates_daily WHERE trade_date = ?"
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += " AND market_code = ?"
            params.append(market_code)
        query += " ORDER BY rank ASC, composite_score DESC, ticker"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_candidate(row) for row in rows]

    def replace_watchlist(self, trade_date: date, watchlist: list[StockWatchItem]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.execute("DELETE FROM stock_watchlist_daily WHERE trade_date = ?", (trade_date.isoformat(),))
            table_columns = {row['name'] for row in connection.execute("PRAGMA table_info(stock_watchlist_daily)").fetchall()}
            columns = [
                'trade_date', 'market_code', 'ticker', 'regime_trade_date', 'watch_rank', 'company_name', 'sector', 'industry', 'close', 'ret_5d',
                'ret_20d', 'ret_60d', 'ma_20', 'ma_60', 'avg_dollar_volume_3d', 'avg_dollar_volume_5d', 'avg_dollar_volume_20d',
                'volume_ratio_3d', 'volume_ratio_5d', 'volume_up_days_5d', 'distance_to_60d_high', 'momentum_acceleration', 'vol_20d',
                'composite_score', 'theme_score', 'lagging_score', 'trend_recovery_score', 'momentum_acceleration_score', 'volume_probe_score',
                'risk_control_score', 'valuation_band', 'market_cap_bucket', 'theme_tags_json', 'source', 'watch_reason',
            ]
            if 'volume_score' in table_columns:
                columns.append('volume_score')
            if 'valuation_score' in table_columns:
                columns.append('valuation_score')
            if 'size_score' in table_columns:
                columns.append('size_score')
            placeholders = ', '.join('?' for _ in columns)
            column_sql = ', '.join(columns)
            connection.executemany(
                f"INSERT INTO stock_watchlist_daily ({column_sql}) VALUES ({placeholders})",
                [
                    tuple(value for _, value in self._watchlist_insert_values(item, include_legacy=table_columns))
                    for item in watchlist
                ],
            )

    @staticmethod
    def _watchlist_insert_values(item: StockWatchItem, *, include_legacy: set[str]) -> list[tuple[str, object]]:
        values = [
            ('trade_date', item.trade_date.isoformat()),
            ('market_code', item.market_code),
            ('ticker', item.ticker),
            ('regime_trade_date', item.regime_trade_date.isoformat() if item.regime_trade_date else None),
            ('watch_rank', item.watch_rank),
            ('company_name', item.company_name),
            ('sector', item.sector),
            ('industry', item.industry),
            ('close', item.close),
            ('ret_5d', item.ret_5d),
            ('ret_20d', item.ret_20d),
            ('ret_60d', item.ret_60d),
            ('ma_20', item.ma_20),
            ('ma_60', item.ma_60),
            ('avg_dollar_volume_3d', item.avg_dollar_volume_3d),
            ('avg_dollar_volume_5d', item.avg_dollar_volume_5d),
            ('avg_dollar_volume_20d', item.avg_dollar_volume_20d),
            ('volume_ratio_3d', item.volume_ratio_3d),
            ('volume_ratio_5d', item.volume_ratio_5d),
            ('volume_up_days_5d', item.volume_up_days_5d),
            ('distance_to_60d_high', item.distance_to_60d_high),
            ('momentum_acceleration', item.momentum_acceleration),
            ('vol_20d', item.vol_20d),
            ('composite_score', item.composite_score),
            ('theme_score', item.theme_score),
            ('lagging_score', item.lagging_score),
            ('trend_recovery_score', item.trend_recovery_score),
            ('momentum_acceleration_score', item.momentum_acceleration_score),
            ('volume_probe_score', item.volume_probe_score),
            ('risk_control_score', item.risk_control_score),
            ('valuation_band', item.valuation_band),
            ('market_cap_bucket', item.market_cap_bucket),
            ('theme_tags_json', json.dumps(item.theme_tags, sort_keys=True)),
            ('source', item.source),
            ('watch_reason', item.watch_reason),
        ]
        if 'volume_score' in include_legacy:
            values.append(('volume_score', item.volume_probe_score))
        if 'valuation_score' in include_legacy:
            values.append(('valuation_score', 0.0))
        if 'size_score' in include_legacy:
            values.append(('size_score', 0.0))
        return values

    def list_watchlist(self, trade_date: date, market_code: str | None = None) -> list[StockWatchItem]:
        query = "SELECT * FROM stock_watchlist_daily WHERE trade_date = ?"
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += " AND market_code = ?"
            params.append(market_code)
        query += " ORDER BY watch_rank ASC, ticker"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_watchlist_item(row) for row in rows]

    def replace_heat_snapshots(self, trade_date: date, market_codes: list[str], snapshots: list[ThemeHeatSnapshot]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO selection_heat_daily (
                    trade_date, market_code, theme_type, theme_name, raw_heat_score, smoothed_heat_score, constituent_count, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, market_code, theme_type, theme_name) DO UPDATE SET
                    raw_heat_score = excluded.raw_heat_score,
                    smoothed_heat_score = excluded.smoothed_heat_score,
                    constituent_count = excluded.constituent_count,
                    source = excluded.source
                """,
                [
                    (
                        item.trade_date.isoformat(),
                        item.market_code,
                        item.theme_type,
                        item.theme_name,
                        item.raw_heat_score,
                        item.smoothed_heat_score,
                        item.constituent_count,
                        item.source,
                    )
                    for item in snapshots
                ],
            )

    def list_heat_snapshots(
        self,
        trade_date: date,
        market_code: str | None = None,
        theme_type: str | None = None,
    ) -> list[ThemeHeatSnapshot]:
        query = "SELECT * FROM selection_heat_daily WHERE trade_date = ?"
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += " AND market_code = ?"
            params.append(market_code)
        if theme_type is not None:
            query += " AND theme_type = ?"
            params.append(theme_type)
        query += " ORDER BY smoothed_heat_score DESC, raw_heat_score DESC, theme_type, theme_name"
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_heat_snapshot(row) for row in rows]


def _row_to_seed_snapshot(row) -> StockSeedSnapshot:
    return StockSeedSnapshot(
        trade_date=date.fromisoformat(row['trade_date']),
        market_code=row['market_code'],
        ticker=row['ticker'],
        company_name=row['company_name'],
        sector=row['sector'],
        industry=row['industry'],
        exchange=row['exchange'],
        currency=row['currency'],
        country_code=row['country_code'],
        seed_type=row['seed_type'],
        theme_tags=json.loads(row['theme_tags_json']),
        theme_score=float(row['theme_score']),
        valuation_score=float(row['valuation_score']),
        size_score=float(row['size_score']),
        valuation_band=row['valuation_band'],
        market_cap_bucket=row['market_cap_bucket'],
        seed_reason=row['seed_reason'],
    )


def _row_to_stock_bar(row) -> StockDailyBar:
    return StockDailyBar(
        market_code=row['market_code'],
        ticker=row['ticker'],
        trade_date=date.fromisoformat(row['trade_date']),
        close=float(row['close']),
        volume=float(row['volume']),
        source=row['source'],
    )


def _row_to_market_universe_snapshot(row) -> StockUniverseSnapshot:
    return StockUniverseSnapshot(
        trade_date=date.fromisoformat(row['trade_date']),
        market_code=row['market_code'],
        ticker=row['ticker'],
        company_name=row['company_name'],
        sector=row['sector'],
        industry=row['industry'],
        exchange=row['exchange'],
        currency=row['currency'],
        country_code=row['country_code'],
        market_cap=float(row['market_cap']),
        price=float(row['price']),
        price_position=float(row['price_position']) if row['price_position'] is not None else None,
        momentum_pct=float(row['momentum_pct']),
        volume_ratio=float(row['volume_ratio']),
        ret_5d=float(row['ret_5d']) if row['ret_5d'] is not None else None,
        ret_20d=float(row['ret_20d']) if row['ret_20d'] is not None else None,
        ret_60d=float(row['ret_60d']) if row['ret_60d'] is not None else None,
        ma_20=float(row['ma_20']) if row['ma_20'] is not None else None,
        ma_60=float(row['ma_60']) if row['ma_60'] is not None else None,
        avg_dollar_volume_3d=float(row['avg_dollar_volume_3d']) if row['avg_dollar_volume_3d'] is not None else None,
        avg_dollar_volume_20d=float(row['avg_dollar_volume_20d']) if row['avg_dollar_volume_20d'] is not None else None,
        volume_ratio_3d=float(row['volume_ratio_3d']) if row['volume_ratio_3d'] is not None else None,
        volume_up_days_5d=int(row['volume_up_days_5d']) if row['volume_up_days_5d'] is not None else None,
        distance_to_60d_high=float(row['distance_to_60d_high']) if row['distance_to_60d_high'] is not None else None,
        momentum_acceleration=float(row['momentum_acceleration']) if row['momentum_acceleration'] is not None else None,
        vol_20d=float(row['vol_20d']) if row['vol_20d'] is not None else None,
        theme_tags=json.loads(row['theme_tags_json']),
        source=row['source'],
    )


def _row_to_candidate(row) -> StockCandidate:
    regime_trade_date = date.fromisoformat(row['regime_trade_date']) if row['regime_trade_date'] else None
    return StockCandidate(
        market_code=row['market_code'],
        ticker=row['ticker'],
        trade_date=date.fromisoformat(row['trade_date']),
        regime_trade_date=regime_trade_date,
        company_name=row['company_name'],
        sector=row['sector'],
        industry=row['industry'],
        seed_type=row['seed_type'],
        rank=int(row['rank']),
        close=float(row['close']),
        ret_5d=float(row['ret_5d']),
        ret_20d=float(row['ret_20d']),
        ret_60d=float(row['ret_60d']),
        ma_20=float(row['ma_20']),
        ma_60=float(row['ma_60']),
        avg_dollar_volume_3d=float(row['avg_dollar_volume_3d']),
        avg_dollar_volume_5d=float(row['avg_dollar_volume_5d']),
        avg_dollar_volume_20d=float(row['avg_dollar_volume_20d']),
        volume_ratio_3d=float(row['volume_ratio_3d']),
        volume_ratio_5d=float(row['volume_ratio_5d']),
        volume_up_days_5d=int(row['volume_up_days_5d']),
        distance_to_60d_high=float(row['distance_to_60d_high']),
        momentum_acceleration=float(row['momentum_acceleration']),
        vol_20d=float(row['vol_20d']),
        coarse_score=float(row['coarse_score']),
        composite_score=float(row['composite_score']),
        theme_score=float(row['theme_score']),
        lagging_score=float(row['lagging_score']),
        trend_recovery_score=float(row['trend_recovery_score']),
        momentum_acceleration_score=float(row['momentum_acceleration_score']),
        volume_probe_score=float(row['volume_probe_score']),
        risk_control_score=float(row['risk_control_score']),
        valuation_band=row['valuation_band'],
        market_cap_bucket=row['market_cap_bucket'],
        theme_tags=json.loads(row['theme_tags_json']),
        source=row['source'],
        screen_flags=json.loads(row['screen_flags_json']),
    )


def _row_to_watchlist_item(row) -> StockWatchItem:
    regime_trade_date = date.fromisoformat(row['regime_trade_date']) if row['regime_trade_date'] else None
    return StockWatchItem(
        market_code=row['market_code'],
        ticker=row['ticker'],
        trade_date=date.fromisoformat(row['trade_date']),
        regime_trade_date=regime_trade_date,
        watch_rank=int(row['watch_rank']),
        company_name=row['company_name'],
        sector=row['sector'],
        industry=row['industry'],
        close=float(row['close']),
        ret_5d=float(row['ret_5d']),
        ret_20d=float(row['ret_20d']),
        ret_60d=float(row['ret_60d']),
        ma_20=float(row['ma_20']),
        ma_60=float(row['ma_60']),
        avg_dollar_volume_3d=float(row['avg_dollar_volume_3d']),
        avg_dollar_volume_5d=float(row['avg_dollar_volume_5d']),
        avg_dollar_volume_20d=float(row['avg_dollar_volume_20d']),
        volume_ratio_3d=float(row['volume_ratio_3d']),
        volume_ratio_5d=float(row['volume_ratio_5d']),
        volume_up_days_5d=int(row['volume_up_days_5d']),
        distance_to_60d_high=float(row['distance_to_60d_high']),
        momentum_acceleration=float(row['momentum_acceleration']),
        vol_20d=float(row['vol_20d']),
        composite_score=float(row['composite_score']),
        theme_score=float(row['theme_score']),
        lagging_score=float(row['lagging_score']),
        trend_recovery_score=float(row['trend_recovery_score']),
        momentum_acceleration_score=float(row['momentum_acceleration_score']),
        volume_probe_score=float(row['volume_probe_score']),
        risk_control_score=float(row['risk_control_score']),
        valuation_band=row['valuation_band'],
        market_cap_bucket=row['market_cap_bucket'],
        theme_tags=json.loads(row['theme_tags_json']),
        source=row['source'],
        watch_reason=row['watch_reason'],
    )


def _row_to_heat_snapshot(row) -> ThemeHeatSnapshot:
    return ThemeHeatSnapshot(
        trade_date=date.fromisoformat(row['trade_date']),
        market_code=row['market_code'],
        theme_type=row['theme_type'],
        theme_name=row['theme_name'],
        raw_heat_score=float(row['raw_heat_score']),
        smoothed_heat_score=float(row['smoothed_heat_score']),
        constituent_count=int(row['constituent_count']),
        source=row['source'],
    )
