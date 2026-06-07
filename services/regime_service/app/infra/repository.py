import json
from datetime import date
from pathlib import Path

from packages.domain_core.market.entities import RegimeSnapshot
from packages.shared.contracts import RegimeSnapshotRepository
from packages.shared.sqlite import initialize_sqlite, sqlite_session


class InMemoryRegimeRepository(RegimeSnapshotRepository):
    backend_name = "memory"

    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, date], RegimeSnapshot] = {}

    def upsert_snapshots(self, snapshots: list[RegimeSnapshot]) -> None:
        for snapshot in snapshots:
            self._snapshots[(snapshot.market_code, snapshot.trade_date)] = snapshot

    def get_snapshot(self, market_code: str, trade_date: date) -> RegimeSnapshot | None:
        return self._snapshots.get((market_code, trade_date))

    def get_latest_snapshot(self, market_code: str) -> RegimeSnapshot | None:
        matches = [
            snapshot
            for (current_market_code, _), snapshot in self._snapshots.items()
            if current_market_code == market_code
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.trade_date)

    def list_by_date(self, trade_date: date) -> list[RegimeSnapshot]:
        return sorted(
            [
                snapshot
                for (_, current_date), snapshot in self._snapshots.items()
                if current_date == trade_date
            ],
            key=lambda item: item.market_code,
        )

    def list_latest(self) -> list[RegimeSnapshot]:
        if not self._snapshots:
            return []
        latest_trade_date = max(current_date for _, current_date in self._snapshots.keys())
        return self.list_by_date(latest_trade_date)

    def list_tracked_bull(self) -> list[RegimeSnapshot]:
        latest_bull_by_market: dict[str, RegimeSnapshot] = {}
        for snapshot in self._snapshots.values():
            if snapshot.regime_status != 'BULL':
                continue
            current = latest_bull_by_market.get(snapshot.market_code)
            if current is None or snapshot.trade_date > current.trade_date:
                latest_bull_by_market[snapshot.market_code] = snapshot
        return sorted(latest_bull_by_market.values(), key=lambda item: item.market_code)


class SqliteRegimeRepository(RegimeSnapshotRepository):
    backend_name = "sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        initialize_sqlite(self._db_path)

    def upsert_snapshots(self, snapshots: list[RegimeSnapshot]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO market_regime_daily (
                    market_code,
                    trade_date,
                    regime_status,
                    bull_score,
                    trend_score,
                    relative_strength_score,
                    risk_penalty_score,
                    trigger_flags_json,
                    source_used_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_code, trade_date) DO UPDATE SET
                    regime_status = excluded.regime_status,
                    bull_score = excluded.bull_score,
                    trend_score = excluded.trend_score,
                    relative_strength_score = excluded.relative_strength_score,
                    risk_penalty_score = excluded.risk_penalty_score,
                    trigger_flags_json = excluded.trigger_flags_json,
                    source_used_json = excluded.source_used_json
                """,
                [
                    (
                        snapshot.market_code,
                        snapshot.trade_date.isoformat(),
                        snapshot.regime_status,
                        snapshot.bull_score,
                        snapshot.trend_score,
                        snapshot.relative_strength_score,
                        snapshot.risk_penalty_score,
                        json.dumps(snapshot.trigger_flags, sort_keys=True),
                        json.dumps(snapshot.source_used, sort_keys=True),
                    )
                    for snapshot in snapshots
                ],
            )

    def get_snapshot(self, market_code: str, trade_date: date) -> RegimeSnapshot | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT * FROM market_regime_daily WHERE market_code = ? AND trade_date = ?",
                (market_code, trade_date.isoformat()),
            ).fetchone()
        return _row_to_snapshot(row) if row else None

    def list_by_date(self, trade_date: date) -> list[RegimeSnapshot]:
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM market_regime_daily WHERE trade_date = ? ORDER BY market_code",
                (trade_date.isoformat(),),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def get_latest_snapshot(self, market_code: str) -> RegimeSnapshot | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                "SELECT * FROM market_regime_daily WHERE market_code = ? ORDER BY trade_date DESC LIMIT 1",
                (market_code,),
            ).fetchone()
        return _row_to_snapshot(row) if row else None

    def list_latest(self) -> list[RegimeSnapshot]:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute("SELECT MAX(trade_date) AS trade_date FROM market_regime_daily").fetchone()
        if row is None or row['trade_date'] is None:
            return []
        return self.list_by_date(date.fromisoformat(row['trade_date']))

    def list_tracked_bull(self) -> list[RegimeSnapshot]:
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(
                """
                SELECT mr.*
                FROM market_regime_daily mr
                JOIN (
                    SELECT market_code, MAX(trade_date) AS trade_date
                    FROM market_regime_daily
                    WHERE regime_status = 'BULL'
                    GROUP BY market_code
                ) tracked
                  ON tracked.market_code = mr.market_code
                 AND tracked.trade_date = mr.trade_date
                ORDER BY mr.market_code
                """
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]


def _row_to_snapshot(row) -> RegimeSnapshot:
    return RegimeSnapshot(
        market_code=row['market_code'],
        trade_date=date.fromisoformat(row['trade_date']),
        regime_status=row['regime_status'],
        bull_score=float(row['bull_score']),
        trend_score=float(row['trend_score']),
        relative_strength_score=float(row['relative_strength_score']),
        risk_penalty_score=float(row['risk_penalty_score']),
        trigger_flags=json.loads(row['trigger_flags_json']),
        source_used=json.loads(row['source_used_json']),
    )
