from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    tracked = {snapshot.market_code for snapshot in container.regime_service.list_tracked_bull()}
    all_codes = [market.market_code for market in container.markets_config.markets]
    background_codes = [market_code for market_code in all_codes if market_code not in tracked]
    rows = container.selection_service.sync_market_universe_inventory(
        trade_date=effective_date,
        market_codes=background_codes,
        replace_market_codes=background_codes,
    )
    return {
        'job': 'sync_background_universe_inventory',
        'trade_date': effective_date.isoformat(),
        'background_markets': background_codes,
        'universe_count': len(rows),
        'source_mode': container.selection_service.source_mode,
    }
