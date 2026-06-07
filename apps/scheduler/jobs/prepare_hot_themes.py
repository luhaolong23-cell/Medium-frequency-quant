from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    snapshots = container.selection_service.prepare_hot_themes(
        trade_date=effective_date,
        market_codes=['ALL'],
        replace_market_codes=['ALL'],
    )
    return {
        'job': 'prepare_hot_themes',
        'trade_date': effective_date.isoformat(),
        'market_codes': ['ALL'],
        'heat_snapshot_count': len(snapshots),
        'source_mode': container.selection_service.source_mode,
    }
