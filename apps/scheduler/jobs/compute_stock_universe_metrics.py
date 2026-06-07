from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    tracked = container.regime_service.list_tracked_bull()
    market_codes = [snapshot.market_code for snapshot in tracked]
    rows = container.selection_service.compute_market_universe_metrics(
        trade_date=effective_date,
        market_codes=market_codes,
        replace_market_codes=market_codes,
    )
    return {
        'job': 'compute_stock_universe_metrics',
        'trade_date': effective_date.isoformat(),
        'tracked_bull_markets': market_codes,
        'universe_count': len(rows),
        'source_mode': container.selection_service.source_mode,
    }
