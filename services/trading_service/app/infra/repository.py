from datetime import date, datetime
from pathlib import Path

from packages.domain_core.trading.entities import PaperOrder, PaperPosition, TradeSignal
from packages.shared.contracts import PaperOrderRepository, PaperPositionRepository, TradeSignalRepository
from packages.shared.sqlite import initialize_sqlite, sqlite_session


class InMemoryTradingRepository(TradeSignalRepository, PaperOrderRepository, PaperPositionRepository):
    backend_name = 'memory'

    def __init__(self) -> None:
        self._signals: dict[tuple[date, str, str, str, str], TradeSignal] = {}
        self._orders: dict[str, PaperOrder] = {}
        self._positions: dict[tuple[str, str], PaperPosition] = {}

    def replace_signals(self, trade_date: date, signals: list[TradeSignal]) -> None:
        self._signals = {key: signal for key, signal in self._signals.items() if key[0] != trade_date}
        for signal in signals:
            self._signals[(signal.trade_date, signal.market_code, signal.ticker, signal.signal_type, signal.side)] = signal

    def list_signals(self, trade_date: date, market_code: str | None = None) -> list[TradeSignal]:
        rows = [
            signal
            for (current_date, current_market_code, _, _, _), signal in self._signals.items()
            if current_date == trade_date and (market_code is None or current_market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.market_code, item.ticker, item.side, item.signal_type))

    def append_orders(self, orders: list[PaperOrder]) -> None:
        for order in orders:
            self._orders[order.order_id] = order

    def list_orders(self, trade_date: date, market_code: str | None = None) -> list[PaperOrder]:
        rows = [
            order
            for order in self._orders.values()
            if order.trade_date == trade_date and (market_code is None or order.market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.market_code, item.ticker, item.trade_date, item.order_id))

    def upsert_positions(self, positions: list[PaperPosition]) -> None:
        for position in positions:
            self._positions[(position.market_code, position.ticker)] = position

    def list_positions(self, status: str | None = None, market_code: str | None = None) -> list[PaperPosition]:
        rows = [
            position
            for position in self._positions.values()
            if (status is None or position.status == status) and (market_code is None or position.market_code == market_code)
        ]
        return sorted(rows, key=lambda item: (item.market_code, item.ticker))

    def get_position(self, market_code: str, ticker: str) -> PaperPosition | None:
        return self._positions.get((market_code, ticker))


class SqliteTradingRepository(TradeSignalRepository, PaperOrderRepository, PaperPositionRepository):
    backend_name = 'sqlite'

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        initialize_sqlite(self._db_path)

    def replace_signals(self, trade_date: date, signals: list[TradeSignal]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.execute('DELETE FROM trade_signals_daily WHERE trade_date = ?', (trade_date.isoformat(),))
            connection.executemany(
                """
                INSERT INTO trade_signals_daily (
                    trade_date,
                    market_code,
                    ticker,
                    side,
                    signal_type,
                    triggered,
                    signal_reason,
                    close,
                    volume_ratio_5d,
                    threshold_volume_ratio,
                    order_notional,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        signal.trade_date.isoformat(),
                        signal.market_code,
                        signal.ticker,
                        signal.side,
                        signal.signal_type,
                        1 if signal.triggered else 0,
                        signal.signal_reason,
                        signal.close,
                        signal.volume_ratio_5d,
                        signal.threshold_volume_ratio,
                        signal.order_notional,
                        signal.source,
                    )
                    for signal in signals
                ],
            )

    def list_signals(self, trade_date: date, market_code: str | None = None) -> list[TradeSignal]:
        query = 'SELECT * FROM trade_signals_daily WHERE trade_date = ?'
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += ' AND market_code = ?'
            params.append(market_code)
        query += ' ORDER BY market_code, ticker, side, signal_type'
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            TradeSignal(
                market_code=row['market_code'],
                ticker=row['ticker'],
                trade_date=date.fromisoformat(row['trade_date']),
                side=row['side'],
                signal_type=row['signal_type'],
                triggered=bool(row['triggered']),
                signal_reason=row['signal_reason'],
                close=float(row['close']),
                volume_ratio_5d=float(row['volume_ratio_5d']),
                threshold_volume_ratio=float(row['threshold_volume_ratio']),
                order_notional=float(row['order_notional']),
                source=row['source'],
            )
            for row in rows
        ]

    def append_orders(self, orders: list[PaperOrder]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO paper_orders (
                    order_id,
                    trade_date,
                    market_code,
                    ticker,
                    side,
                    order_type,
                    status,
                    signal_type,
                    signal_reason,
                    position_effect,
                    position_status_before,
                    position_status_after,
                    requested_notional,
                    quantity,
                    limit_price,
                    filled_price,
                    filled_at,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        order.order_id,
                        order.trade_date.isoformat(),
                        order.market_code,
                        order.ticker,
                        order.side,
                        order.order_type,
                        order.status,
                        order.signal_type,
                        order.signal_reason,
                        order.position_effect,
                        order.position_status_before,
                        order.position_status_after,
                        order.requested_notional,
                        order.quantity,
                        order.limit_price,
                        order.filled_price,
                        order.filled_at.isoformat(),
                        order.source,
                    )
                    for order in orders
                ],
            )

    def list_orders(self, trade_date: date, market_code: str | None = None) -> list[PaperOrder]:
        query = 'SELECT * FROM paper_orders WHERE trade_date = ?'
        params: list[str] = [trade_date.isoformat()]
        if market_code is not None:
            query += ' AND market_code = ?'
            params.append(market_code)
        query += ' ORDER BY market_code, ticker, order_id'
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            PaperOrder(
                order_id=row['order_id'],
                market_code=row['market_code'],
                ticker=row['ticker'],
                trade_date=date.fromisoformat(row['trade_date']),
                side=row['side'],
                order_type=row['order_type'],
                status=row['status'],
                signal_type=row['signal_type'],
                signal_reason=row['signal_reason'],
                position_effect=row['position_effect'],
                position_status_before=row['position_status_before'],
                position_status_after=row['position_status_after'],
                requested_notional=float(row['requested_notional']),
                quantity=float(row['quantity']),
                limit_price=float(row['limit_price']),
                filled_price=float(row['filled_price']),
                filled_at=datetime.fromisoformat(row['filled_at']),
                source=row['source'],
            )
            for row in rows
        ]

    def upsert_positions(self, positions: list[PaperPosition]) -> None:
        with sqlite_session(self._db_path) as connection:
            connection.executemany(
                """
                INSERT INTO paper_positions (
                    market_code,
                    ticker,
                    opened_trade_date,
                    last_trade_date,
                    quantity,
                    avg_price,
                    invested_notional,
                    peak_price,
                    last_close,
                    last_volume_ratio_5d,
                    consecutive_decline_days,
                    unrealized_pnl,
                    unrealized_return,
                    entry_signal_type,
                    last_signal_type,
                    last_signal_reason,
                    closed_trade_date,
                    closed_price,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_code, ticker) DO UPDATE SET
                    last_trade_date = excluded.last_trade_date,
                    quantity = excluded.quantity,
                    avg_price = excluded.avg_price,
                    invested_notional = excluded.invested_notional,
                    peak_price = excluded.peak_price,
                    last_close = excluded.last_close,
                    last_volume_ratio_5d = excluded.last_volume_ratio_5d,
                    consecutive_decline_days = excluded.consecutive_decline_days,
                    unrealized_pnl = excluded.unrealized_pnl,
                    unrealized_return = excluded.unrealized_return,
                    entry_signal_type = excluded.entry_signal_type,
                    last_signal_type = excluded.last_signal_type,
                    last_signal_reason = excluded.last_signal_reason,
                    closed_trade_date = excluded.closed_trade_date,
                    closed_price = excluded.closed_price,
                    status = excluded.status
                """,
                [
                    (
                        position.market_code,
                        position.ticker,
                        position.opened_trade_date.isoformat(),
                        position.last_trade_date.isoformat(),
                        position.quantity,
                        position.avg_price,
                        position.invested_notional,
                        position.peak_price,
                        position.last_close,
                        position.last_volume_ratio_5d,
                        position.consecutive_decline_days,
                        position.unrealized_pnl,
                        position.unrealized_return,
                        position.entry_signal_type,
                        position.last_signal_type,
                        position.last_signal_reason,
                        position.closed_trade_date.isoformat() if position.closed_trade_date is not None else None,
                        position.closed_price,
                        position.status,
                    )
                    for position in positions
                ],
            )

    def list_positions(self, status: str | None = None, market_code: str | None = None) -> list[PaperPosition]:
        query = 'SELECT * FROM paper_positions WHERE 1 = 1'
        params: list[str] = []
        if status is not None:
            query += ' AND status = ?'
            params.append(status)
        if market_code is not None:
            query += ' AND market_code = ?'
            params.append(market_code)
        query += ' ORDER BY market_code, ticker'
        with sqlite_session(self._db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_position(row) for row in rows]

    def get_position(self, market_code: str, ticker: str) -> PaperPosition | None:
        with sqlite_session(self._db_path) as connection:
            row = connection.execute(
                'SELECT * FROM paper_positions WHERE market_code = ? AND ticker = ?',
                (market_code, ticker),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_position(row)

    @staticmethod
    def _row_to_position(row) -> PaperPosition:
        return PaperPosition(
            market_code=row['market_code'],
            ticker=row['ticker'],
            opened_trade_date=date.fromisoformat(row['opened_trade_date']),
            last_trade_date=date.fromisoformat(row['last_trade_date']),
            quantity=float(row['quantity']),
            avg_price=float(row['avg_price']),
            invested_notional=float(row['invested_notional']),
            peak_price=float(row['peak_price']),
            last_close=float(row['last_close']),
            last_volume_ratio_5d=float(row['last_volume_ratio_5d']),
            consecutive_decline_days=int(row['consecutive_decline_days']),
            unrealized_pnl=float(row['unrealized_pnl']),
            unrealized_return=float(row['unrealized_return']),
            entry_signal_type=row['entry_signal_type'],
            last_signal_type=row['last_signal_type'],
            last_signal_reason=row['last_signal_reason'],
            closed_trade_date=date.fromisoformat(row['closed_trade_date']) if row['closed_trade_date'] else None,
            closed_price=float(row['closed_price']) if row['closed_price'] is not None else None,
            status=row['status'],
        )
