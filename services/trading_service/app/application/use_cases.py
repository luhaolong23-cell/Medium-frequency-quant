from datetime import date, datetime, timezone

from packages.domain_core.selection.entities import StockWatchItem
from packages.domain_core.trading.entities import PaperOrder, PaperPosition, TradeSignal
from packages.shared.contracts import PaperOrderRepository, PaperPositionRepository, PositionDataProvider, TradeSignalRepository
from packages.shared.logging import get_logger, log_event
from packages.shared.settings import TradingRulesConfig


logger = get_logger(__name__)


class TradingService:
    def __init__(
        self,
        rules: TradingRulesConfig,
        signal_repository: TradeSignalRepository,
        order_repository: PaperOrderRepository,
        position_repository: PaperPositionRepository,
        position_data_provider: PositionDataProvider,
    ) -> None:
        self._rules = rules
        self._signal_repository = signal_repository
        self._order_repository = order_repository
        self._position_repository = position_repository
        self._position_data_provider = position_data_provider

    @property
    def source_mode(self) -> str:
        return 'paper'

    def run_daily(self, trade_date: date, watchlist: list[StockWatchItem]) -> tuple[list[TradeSignal], list[PaperOrder], list[PaperPosition]]:
        threshold = self._rules.signal.min_volume_ratio_5d
        notional = self._rules.execution.fixed_order_amount
        quantity_precision = self._rules.execution.quantity_precision
        signals: list[TradeSignal] = []
        orders: list[PaperOrder] = []
        new_positions: list[PaperPosition] = []

        for item in watchlist:
            triggered = item.volume_ratio_5d >= threshold
            signal = TradeSignal(
                market_code=item.market_code,
                ticker=item.ticker,
                trade_date=trade_date,
                side='BUY',
                signal_type='BUY_VOLUME_SURGE',
                triggered=triggered,
                signal_reason=self._build_buy_signal_reason(item=item, threshold=threshold),
                close=item.close,
                volume_ratio_5d=item.volume_ratio_5d,
                threshold_volume_ratio=threshold,
                order_notional=notional,
                source='paper',
            )
            signals.append(signal)
            if not triggered:
                continue
            existing = self._position_repository.get_position(item.market_code, item.ticker)
            if existing is not None and existing.status == 'OPEN':
                continue
            quantity = round(notional / max(item.close, 0.0001), quantity_precision)
            invested_notional = round(quantity * item.close, 4)
            filled_at = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc)
            order = PaperOrder(
                order_id=f'{trade_date.isoformat()}:{item.market_code}:{item.ticker}:BUY',
                market_code=item.market_code,
                ticker=item.ticker,
                trade_date=trade_date,
                side='BUY',
                order_type='MARKET',
                status='FILLED',
                signal_type=signal.signal_type,
                signal_reason=signal.signal_reason,
                position_effect='OPEN',
                position_status_before='NONE',
                position_status_after='OPEN',
                requested_notional=notional,
                quantity=quantity,
                limit_price=item.close,
                filled_price=item.close,
                filled_at=filled_at,
                source='paper',
            )
            orders.append(order)
            new_positions.append(
                PaperPosition(
                    market_code=item.market_code,
                    ticker=item.ticker,
                    opened_trade_date=trade_date,
                    last_trade_date=trade_date,
                    quantity=quantity,
                    avg_price=item.close,
                    invested_notional=invested_notional,
                    peak_price=item.close,
                    last_close=item.close,
                    last_volume_ratio_5d=item.volume_ratio_5d,
                    consecutive_decline_days=0,
                    unrealized_pnl=0.0,
                    unrealized_return=0.0,
                    entry_signal_type=signal.signal_type,
                    last_signal_type=signal.signal_type,
                    last_signal_reason=signal.signal_reason,
                    status='OPEN',
                )
            )

        self._store_signals(trade_date=trade_date, new_signals=signals)
        if orders:
            self._order_repository.append_orders(orders)
        if new_positions:
            self._position_repository.upsert_positions(new_positions)
        positions = self._position_repository.list_positions(status='OPEN')
        log_event(
            logger,
            'trading.run_daily.completed',
            trade_date=trade_date.isoformat(),
            watchlist_count=len(watchlist),
            signal_count=len(signals),
            triggered_signal_count=sum(1 for signal in signals if signal.triggered),
            order_count=len(orders),
            open_position_count=len(positions),
            signals=[
                {
                    'market_code': signal.market_code,
                    'ticker': signal.ticker,
                    'side': signal.side,
                    'signal_type': signal.signal_type,
                    'triggered': signal.triggered,
                    'volume_ratio_5d': round(signal.volume_ratio_5d, 4),
                    'threshold_volume_ratio': round(signal.threshold_volume_ratio, 4),
                }
                for signal in signals
            ],
            orders=[
                {
                    'market_code': order.market_code,
                    'ticker': order.ticker,
                    'side': order.side,
                    'requested_notional': order.requested_notional,
                    'quantity': order.quantity,
                    'filled_price': round(order.filled_price, 4),
                    'position_status_after': order.position_status_after,
                }
                for order in orders
            ],
            positions=[
                {
                    'market_code': position.market_code,
                    'ticker': position.ticker,
                    'quantity': position.quantity,
                    'avg_price': round(position.avg_price, 4),
                    'peak_price': round(position.peak_price, 4),
                    'status': position.status,
                }
                for position in positions
            ],
        )
        return signals, orders, positions

    def run_position_monitor(self, trade_date: date) -> tuple[list[TradeSignal], list[PaperOrder], list[PaperPosition]]:
        open_positions = self._position_repository.list_positions(status='OPEN')
        if not open_positions:
            log_event(
                logger,
                'trading.run_position_monitor.completed',
                trade_date=trade_date.isoformat(),
                inspected_positions=0,
                signal_count=0,
                order_count=0,
                open_position_count=0,
                closed_position_count=0,
                position_data_source_mode=getattr(self._position_data_provider, 'source_mode', 'unknown'),
            )
            return [], [], []

        threshold_days = self._rules.exit.consecutive_shrink_down_days
        drawdown_limit = self._rules.exit.max_drawdown_from_peak_pct
        quantity_precision = self._rules.execution.quantity_precision
        signals: list[TradeSignal] = []
        orders: list[PaperOrder] = []
        updated_positions: list[PaperPosition] = []

        for position in open_positions:
            history = self._position_data_provider.fetch_history(position.ticker, trade_date)
            relevant_history = [row for row in history if row[0] >= position.opened_trade_date]
            if not relevant_history:
                relevant_history = history
            latest_date, latest_close, _ = relevant_history[-1]
            peak_price = max(position.peak_price, max(close for _, close, _ in relevant_history))
            volume_ratio_5d = self._compute_volume_ratio_5d(relevant_history)
            consecutive_decline_days = self._compute_consecutive_shrink_down_days(relevant_history)
            unrealized_pnl = round((latest_close - position.avg_price) * position.quantity, 4)
            unrealized_return = round((latest_close / position.avg_price) - 1, 6) if position.avg_price else 0.0
            drawdown_pct = round((peak_price - latest_close) / peak_price, 6) if peak_price else 0.0
            order_notional = round(position.quantity * latest_close, 4)
            sell_by_drawdown = peak_price > 0 and drawdown_pct >= drawdown_limit
            sell_by_shrink_down = consecutive_decline_days >= threshold_days

            if sell_by_drawdown:
                signal_type = 'SELL_TRAILING_DRAWDOWN'
                triggered = True
                signal_reason = self._build_sell_signal_reason(
                    signal_type=signal_type,
                    latest_close=latest_close,
                    peak_price=peak_price,
                    drawdown_pct=drawdown_pct,
                    drawdown_limit=drawdown_limit,
                    consecutive_decline_days=consecutive_decline_days,
                    threshold_days=threshold_days,
                    volume_ratio_5d=volume_ratio_5d,
                )
            elif sell_by_shrink_down:
                signal_type = 'SELL_SHRINK_DOWN'
                triggered = True
                signal_reason = self._build_sell_signal_reason(
                    signal_type=signal_type,
                    latest_close=latest_close,
                    peak_price=peak_price,
                    drawdown_pct=drawdown_pct,
                    drawdown_limit=drawdown_limit,
                    consecutive_decline_days=consecutive_decline_days,
                    threshold_days=threshold_days,
                    volume_ratio_5d=volume_ratio_5d,
                )
            else:
                signal_type = 'SELL_POSITION_MONITOR'
                triggered = False
                signal_reason = self._build_sell_signal_reason(
                    signal_type=signal_type,
                    latest_close=latest_close,
                    peak_price=peak_price,
                    drawdown_pct=drawdown_pct,
                    drawdown_limit=drawdown_limit,
                    consecutive_decline_days=consecutive_decline_days,
                    threshold_days=threshold_days,
                    volume_ratio_5d=volume_ratio_5d,
                )

            signal = TradeSignal(
                market_code=position.market_code,
                ticker=position.ticker,
                trade_date=trade_date,
                side='SELL',
                signal_type=signal_type,
                triggered=triggered,
                signal_reason=signal_reason,
                close=latest_close,
                volume_ratio_5d=volume_ratio_5d,
                threshold_volume_ratio=0.0,
                order_notional=order_notional,
                source='paper',
            )
            signals.append(signal)

            if triggered:
                filled_at = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc)
                order = PaperOrder(
                    order_id=f'{trade_date.isoformat()}:{position.market_code}:{position.ticker}:SELL',
                    market_code=position.market_code,
                    ticker=position.ticker,
                    trade_date=trade_date,
                    side='SELL',
                    order_type='MARKET',
                    status='FILLED',
                    signal_type=signal.signal_type,
                    signal_reason=signal.signal_reason,
                    position_effect='CLOSE',
                    position_status_before='OPEN',
                    position_status_after='CLOSED',
                    requested_notional=order_notional,
                    quantity=round(position.quantity, quantity_precision),
                    limit_price=latest_close,
                    filled_price=latest_close,
                    filled_at=filled_at,
                    source='paper',
                )
                orders.append(order)
                updated_positions.append(
                    PaperPosition(
                        market_code=position.market_code,
                        ticker=position.ticker,
                        opened_trade_date=position.opened_trade_date,
                        last_trade_date=latest_date,
                        quantity=position.quantity,
                        avg_price=position.avg_price,
                        invested_notional=position.invested_notional,
                        peak_price=peak_price,
                        last_close=latest_close,
                        last_volume_ratio_5d=volume_ratio_5d,
                        consecutive_decline_days=consecutive_decline_days,
                        unrealized_pnl=unrealized_pnl,
                        unrealized_return=unrealized_return,
                        entry_signal_type=position.entry_signal_type,
                        last_signal_type=signal.signal_type,
                        last_signal_reason=signal.signal_reason,
                        closed_trade_date=trade_date,
                        closed_price=latest_close,
                        status='CLOSED',
                    )
                )
                continue

            updated_positions.append(
                PaperPosition(
                    market_code=position.market_code,
                    ticker=position.ticker,
                    opened_trade_date=position.opened_trade_date,
                    last_trade_date=latest_date,
                    quantity=position.quantity,
                    avg_price=position.avg_price,
                    invested_notional=position.invested_notional,
                    peak_price=peak_price,
                    last_close=latest_close,
                    last_volume_ratio_5d=volume_ratio_5d,
                    consecutive_decline_days=consecutive_decline_days,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_return=unrealized_return,
                    entry_signal_type=position.entry_signal_type,
                    last_signal_type=signal.signal_type,
                    last_signal_reason=signal.signal_reason,
                    status='OPEN',
                )
            )

        self._store_signals(trade_date=trade_date, new_signals=signals)
        if orders:
            self._order_repository.append_orders(orders)
        if updated_positions:
            self._position_repository.upsert_positions(updated_positions)
        positions = self._position_repository.list_positions(status=None)
        log_event(
            logger,
            'trading.run_position_monitor.completed',
            trade_date=trade_date.isoformat(),
            inspected_positions=len(open_positions),
            signal_count=len(signals),
            triggered_signal_count=sum(1 for signal in signals if signal.triggered),
            order_count=len(orders),
            open_position_count=sum(1 for position in positions if position.status == 'OPEN'),
            closed_position_count=sum(1 for position in positions if position.status == 'CLOSED'),
            position_data_source_mode=getattr(self._position_data_provider, 'source_mode', 'unknown'),
            signals=[
                {
                    'market_code': signal.market_code,
                    'ticker': signal.ticker,
                    'side': signal.side,
                    'signal_type': signal.signal_type,
                    'triggered': signal.triggered,
                    'close': round(signal.close, 4),
                    'volume_ratio_5d': round(signal.volume_ratio_5d, 4),
                }
                for signal in signals
            ],
            orders=[
                {
                    'market_code': order.market_code,
                    'ticker': order.ticker,
                    'side': order.side,
                    'signal_type': order.signal_type,
                    'filled_price': round(order.filled_price, 4),
                    'position_status_after': order.position_status_after,
                }
                for order in orders
            ],
            positions=[
                {
                    'market_code': position.market_code,
                    'ticker': position.ticker,
                    'last_close': round(position.last_close, 4),
                    'peak_price': round(position.peak_price, 4),
                    'consecutive_decline_days': position.consecutive_decline_days,
                    'status': position.status,
                }
                for position in positions
            ],
        )
        return signals, orders, positions

    def manual_sell_positions(self, trade_date: date, positions: list[tuple[str, str]]) -> tuple[list[TradeSignal], list[PaperOrder], list[PaperPosition]]:
        quantity_precision = self._rules.execution.quantity_precision
        signals: list[TradeSignal] = []
        orders: list[PaperOrder] = []
        updated_positions: list[PaperPosition] = []

        for market_code, ticker in positions:
            position = self._position_repository.get_position(market_code, ticker)
            if position is None or position.status != 'OPEN':
                continue

            history = self._position_data_provider.fetch_history(ticker, trade_date)
            relevant_history = [row for row in history if row[0] >= position.opened_trade_date]
            if not relevant_history:
                relevant_history = history

            if relevant_history:
                latest_date, latest_close, _ = relevant_history[-1]
                peak_price = max(position.peak_price, max(close for _, close, _ in relevant_history))
                volume_ratio_5d = self._compute_volume_ratio_5d(relevant_history)
                consecutive_decline_days = self._compute_consecutive_shrink_down_days(relevant_history)
            else:
                latest_date = trade_date
                latest_close = position.last_close
                peak_price = position.peak_price
                volume_ratio_5d = position.last_volume_ratio_5d
                consecutive_decline_days = position.consecutive_decline_days

            unrealized_pnl = round((latest_close - position.avg_price) * position.quantity, 4)
            unrealized_return = round((latest_close / position.avg_price) - 1, 6) if position.avg_price else 0.0
            order_notional = round(position.quantity * latest_close, 4)
            signal_reason = (
                f'SELL_MANUAL close={latest_close:.2f} avg_price={position.avg_price:.2f} '
                f'volume_ratio_5d={volume_ratio_5d:.2f} selected_by=user'
            )
            signal = TradeSignal(
                market_code=position.market_code,
                ticker=position.ticker,
                trade_date=trade_date,
                side='SELL',
                signal_type='SELL_MANUAL',
                triggered=True,
                signal_reason=signal_reason,
                close=latest_close,
                volume_ratio_5d=volume_ratio_5d,
                threshold_volume_ratio=0.0,
                order_notional=order_notional,
                source='paper',
            )
            signals.append(signal)

            filled_at = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc)
            order = PaperOrder(
                order_id=f'{trade_date.isoformat()}:{position.market_code}:{position.ticker}:SELL_MANUAL',
                market_code=position.market_code,
                ticker=position.ticker,
                trade_date=trade_date,
                side='SELL',
                order_type='MARKET',
                status='FILLED',
                signal_type=signal.signal_type,
                signal_reason=signal.signal_reason,
                position_effect='CLOSE',
                position_status_before='OPEN',
                position_status_after='CLOSED',
                requested_notional=order_notional,
                quantity=round(position.quantity, quantity_precision),
                limit_price=latest_close,
                filled_price=latest_close,
                filled_at=filled_at,
                source='paper',
            )
            orders.append(order)
            updated_positions.append(
                PaperPosition(
                    market_code=position.market_code,
                    ticker=position.ticker,
                    opened_trade_date=position.opened_trade_date,
                    last_trade_date=latest_date,
                    quantity=position.quantity,
                    avg_price=position.avg_price,
                    invested_notional=position.invested_notional,
                    peak_price=peak_price,
                    last_close=latest_close,
                    last_volume_ratio_5d=volume_ratio_5d,
                    consecutive_decline_days=consecutive_decline_days,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_return=unrealized_return,
                    entry_signal_type=position.entry_signal_type,
                    last_signal_type=signal.signal_type,
                    last_signal_reason=signal.signal_reason,
                    closed_trade_date=trade_date,
                    closed_price=latest_close,
                    status='CLOSED',
                )
            )

        if signals:
            self._store_signals(trade_date=trade_date, new_signals=signals)
        if orders:
            self._order_repository.append_orders(orders)
        if updated_positions:
            self._position_repository.upsert_positions(updated_positions)
        positions_after = self._position_repository.list_positions(status='OPEN')
        log_event(
            logger,
            'trading.manual_sell_positions.completed',
            trade_date=trade_date.isoformat(),
            requested_count=len(positions),
            sold_count=len(updated_positions),
            open_position_count=len(positions_after),
            sold_positions=[f'{position.market_code}:{position.ticker}' for position in updated_positions],
        )
        return signals, orders, updated_positions

    def list_signals(self, trade_date: date, market_code: str | None = None) -> list[TradeSignal]:
        return self._signal_repository.list_signals(trade_date=trade_date, market_code=market_code)

    def list_orders(self, trade_date: date, market_code: str | None = None) -> list[PaperOrder]:
        return self._order_repository.list_orders(trade_date=trade_date, market_code=market_code)

    def list_positions(self, status: str | None = 'OPEN', market_code: str | None = None) -> list[PaperPosition]:
        return self._position_repository.list_positions(status=status, market_code=market_code)

    def _store_signals(self, trade_date: date, new_signals: list[TradeSignal]) -> None:
        existing = self._signal_repository.list_signals(trade_date=trade_date)
        merged: dict[tuple[date, str, str, str, str], TradeSignal] = {
            (signal.trade_date, signal.market_code, signal.ticker, signal.signal_type, signal.side): signal
            for signal in existing
        }
        for signal in new_signals:
            merged[(signal.trade_date, signal.market_code, signal.ticker, signal.signal_type, signal.side)] = signal
        self._signal_repository.replace_signals(trade_date=trade_date, signals=list(merged.values()))

    @staticmethod
    def _compute_volume_ratio_5d(history: list[tuple[date, float, float]]) -> float:
        if len(history) < 10:
            return 0.0
        recent = history[-5:]
        prior = history[-10:-5]
        recent_avg = sum(volume for _, _, volume in recent) / len(recent)
        prior_avg = sum(volume for _, _, volume in prior) / len(prior)
        if prior_avg <= 0:
            return 0.0
        return round(recent_avg / prior_avg, 6)

    @staticmethod
    def _compute_consecutive_shrink_down_days(history: list[tuple[date, float, float]]) -> int:
        if len(history) < 2:
            return 0
        count = 0
        for index in range(len(history) - 1, 0, -1):
            _, close_today, volume_today = history[index]
            _, close_prev, volume_prev = history[index - 1]
            if close_today < close_prev and volume_today < volume_prev:
                count += 1
                continue
            break
        return count

    @staticmethod
    def _build_buy_signal_reason(item: StockWatchItem, threshold: float) -> str:
        return (
            f'volume_ratio={item.volume_ratio_5d:.2f} threshold={threshold:.2f} '
            f'watch_rank={item.watch_rank} composite={item.composite_score:.2f}'
        )

    @staticmethod
    def _build_sell_signal_reason(
        *,
        signal_type: str,
        latest_close: float,
        peak_price: float,
        drawdown_pct: float,
        drawdown_limit: float,
        consecutive_decline_days: int,
        threshold_days: int,
        volume_ratio_5d: float,
    ) -> str:
        return (
            f'{signal_type} close={latest_close:.2f} peak={peak_price:.2f} '
            f'drawdown_pct={drawdown_pct:.2%} drawdown_limit={drawdown_limit:.0%} '
            f'consecutive_shrink_down_days={consecutive_decline_days} threshold_days={threshold_days} '
            f'volume_ratio_5d={volume_ratio_5d:.2f}'
        )
