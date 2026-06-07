from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    tracked_bull_snapshots = container.regime_service.list_tracked_bull()
    market_codes = [snapshot.market_code for snapshot in tracked_bull_snapshots]
    regime_trade_date = max((snapshot.trade_date for snapshot in tracked_bull_snapshots), default=None)
    candidates, watchlist = container.selection_service.run_daily_selection(
        trade_date=effective_date,
        market_codes=market_codes,
        replace_market_codes=market_codes,
        regime_trade_date=regime_trade_date,
    )
    signals, orders, positions = container.trading_service.run_daily(
        trade_date=effective_date,
        watchlist=watchlist,
    )
    return {
        'job': 'run_daily_selection',
        'trade_date': effective_date.isoformat(),
        'tracked_bull_markets': market_codes,
        'regime_trade_date': regime_trade_date.isoformat() if regime_trade_date else None,
        'selected_candidates': len(candidates),
        'watchlist_count': len(watchlist),
        'generated_signals': len(signals),
        'executed_orders': len(orders),
        'open_positions': len(positions),
        'source_mode': container.selection_service.source_mode,
    }
