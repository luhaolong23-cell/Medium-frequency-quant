from datetime import date
from pathlib import Path

from packages.domain_core.market.entities import MarketFeature
from packages.shared.contracts import MarketFeatureRepository
from packages.shared.sqlite import initialize_sqlite, sqlite_session


class InMemoryMarketDataRepository(MarketFeatureRepository):
    backend_name = "memory"

    def __init__(self) -> None:
        self._features: dict[tuple[str, date], MarketFeature] = {}

    def upsert_features(self, features: list[MarketFeature]) -> None:
        for feature in features:
            self._features[(feature.market_code, feature.trade_date)] = feature

    def get_feature(self, market_code: str, trade_date: date) -> MarketFeature | None:
        return self._features.get((market_code, trade_date))

    def get_latest_feature(self, market_code: str) -> MarketFeature | None:
        matches = [
            feature
            for (current_market_code, _), feature in self._features.items()
            if current_market_code == market_code
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.trade_date)

    def list_features(self, trade_date: date) -> list[MarketFeature]:
        return sorted(
            [
                feature
                for (_, current_date), feature in self._features.items()
                if current_date == trade_date
            ],
            key=lambda item: item.market_code,
        )


class SqliteMarketDataRepository(MarketFeatureRepository):
    backend_name = "sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        initialize_sqlite(self._db_path)

    def upsert_features(self, features: list[MarketFeature]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO market_features_daily (
                    market_code,
                    trade_date,
                    price_proxy,
                    close,
                    ma_120,
                    ma_200,
                    ret_60d,
                    ret_120d,
                    vol_20d,
                    drawdown_60d,
                    relative_strength_world,
                    fx_ret_60d,
                    avg_volume_recent,
                    avg_volume_prior,
                    volume_ratio_5d,
                    consecutive_up_weeks,
                    ma_5,
                    ma_10,
                    ma_20,
                    ma_60,
                    ret_1d,
                    ret_5d,
                    turnover_ratio_20d,
                    avg_turnover_ratio_3d,
                    volume_up_days_2d,
                    volume_up_days_3d,
                    consecutive_up_days,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_code, trade_date) DO UPDATE SET
                    price_proxy = excluded.price_proxy,
                    close = excluded.close,
                    ma_120 = excluded.ma_120,
                    ma_200 = excluded.ma_200,
                    ret_60d = excluded.ret_60d,
                    ret_120d = excluded.ret_120d,
                    vol_20d = excluded.vol_20d,
                    drawdown_60d = excluded.drawdown_60d,
                    relative_strength_world = excluded.relative_strength_world,
                    fx_ret_60d = excluded.fx_ret_60d,
                    avg_volume_recent = excluded.avg_volume_recent,
                    avg_volume_prior = excluded.avg_volume_prior,
                    volume_ratio_5d = excluded.volume_ratio_5d,
                    consecutive_up_weeks = excluded.consecutive_up_weeks,
                    ma_5 = excluded.ma_5,
                    ma_10 = excluded.ma_10,
                    ma_20 = excluded.ma_20,
                    ma_60 = excluded.ma_60,
                    ret_1d = excluded.ret_1d,
                    ret_5d = excluded.ret_5d,
                    turnover_ratio_20d = excluded.turnover_ratio_20d,
                    avg_turnover_ratio_3d = excluded.avg_turnover_ratio_3d,
                    volume_up_days_2d = excluded.volume_up_days_2d,
                    volume_up_days_3d = excluded.volume_up_days_3d,
                    consecutive_up_days = excluded.consecutive_up_days,
                    source = excluded.source
                """,
                [
                    (
                        feature.market_code,
                        feature.trade_date.isoformat(),
                        feature.price_proxy,
                        feature.close,
                        feature.ma_120,
                        feature.ma_200,
                        feature.ret_60d,
                        feature.ret_120d,
                        feature.vol_20d,
                        feature.drawdown_60d,
                        feature.relative_strength_world,
                        feature.fx_ret_60d,
                        feature.avg_volume_recent,
                        feature.avg_volume_prior,
                        feature.volume_ratio_5d,
                        feature.consecutive_up_weeks,
                        feature.ma_5,
                        feature.ma_10,
                        feature.ma_20,
                        feature.ma_60,
                        feature.ret_1d,
                        feature.ret_5d,
                        feature.turnover_ratio_20d,
                        feature.avg_turnover_ratio_3d,
                        feature.volume_up_days_2d,
                        feature.volume_up_days_3d,
                        feature.consecutive_up_days,
                        feature.source,
                    )
                    for feature in features
                ],
            )

    def get_feature(self, market_code: str, trade_date: date) -> MarketFeature | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT * FROM market_features_daily WHERE market_code = ? AND trade_date = ?",
                (market_code, trade_date.isoformat()),
            ).fetchone()
        return _row_to_feature(row) if row else None

    def get_latest_feature(self, market_code: str) -> MarketFeature | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT * FROM market_features_daily WHERE market_code = ? ORDER BY trade_date DESC LIMIT 1",
                (market_code,),
            ).fetchone()
        return _row_to_feature(row) if row else None

    def list_features(self, trade_date: date) -> list[MarketFeature]:
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM market_features_daily WHERE trade_date = ? ORDER BY market_code",
                (trade_date.isoformat(),),
            ).fetchall()
        return [_row_to_feature(row) for row in rows]


def _row_to_feature(row) -> MarketFeature:
    return MarketFeature(
        market_code=row["market_code"],
        trade_date=date.fromisoformat(row["trade_date"]),
        price_proxy=row["price_proxy"],
        close=float(row["close"]),
        ma_120=float(row["ma_120"]),
        ma_200=float(row["ma_200"]),
        ret_60d=float(row["ret_60d"]),
        ret_120d=float(row["ret_120d"]),
        vol_20d=float(row["vol_20d"]),
        drawdown_60d=float(row["drawdown_60d"]),
        relative_strength_world=float(row["relative_strength_world"]),
        fx_ret_60d=float(row["fx_ret_60d"]),
        avg_volume_recent=float(row["avg_volume_recent"]),
        avg_volume_prior=float(row["avg_volume_prior"]),
        volume_ratio_5d=float(row["volume_ratio_5d"]),
        consecutive_up_weeks=int(row["consecutive_up_weeks"]),
        ma_5=float(row["ma_5"]),
        ma_10=float(row["ma_10"]),
        ma_20=float(row["ma_20"]),
        ma_60=float(row["ma_60"]),
        ret_1d=float(row["ret_1d"]),
        ret_5d=float(row["ret_5d"]),
        turnover_ratio_20d=float(row["turnover_ratio_20d"]),
        avg_turnover_ratio_3d=float(row["avg_turnover_ratio_3d"]),
        volume_up_days_2d=int(row["volume_up_days_2d"]),
        volume_up_days_3d=int(row["volume_up_days_3d"]),
        consecutive_up_days=int(row["consecutive_up_days"]),
        source=row["source"],
    )
