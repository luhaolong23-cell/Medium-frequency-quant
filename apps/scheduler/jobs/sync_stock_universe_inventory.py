from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    market_codes = ['ALL']
    rows = container.selection_service.sync_market_universe_inventory(
        trade_date=effective_date,
        market_codes=market_codes,
        replace_market_codes=market_codes,
    )
    return {
        'job': 'sync_stock_universe_inventory',
        'trade_date': effective_date.isoformat(),
        'market_codes': market_codes,
        'universe_count': len(rows),
        'source_mode': container.selection_service.source_mode,
    }
