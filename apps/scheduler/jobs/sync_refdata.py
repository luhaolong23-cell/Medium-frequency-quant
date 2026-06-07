from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    markets = get_container().refdata_service.sync_markets()
    effective_date = trade_date or date.today()
    return {
        "job": "sync_refdata",
        "trade_date": effective_date.isoformat(),
        "synced_markets": len(markets),
    }
