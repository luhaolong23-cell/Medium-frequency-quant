from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    tracked = container.regime_service.list_tracked_bull()
    market_codes = [snapshot.market_code for snapshot in tracked]
    bars = container.selection_service.sync_market_universe_bars(
        trade_date=effective_date,
        market_codes=market_codes,
    )
    return {
        'job': 'sync_stock_universe_bars',
        'trade_date': effective_date.isoformat(),
        'tracked_bull_markets': market_codes,
        'bar_count': len(bars),
        'source_mode': container.selection_service.source_mode,
    }
