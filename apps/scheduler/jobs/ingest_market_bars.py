from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    features = container.market_data_service.ingest_daily(
        trade_date=effective_date,
        market_codes=["ALL"],
    )
    return {
        "job": "ingest_market_bars",
        "trade_date": effective_date.isoformat(),
        "computed_features": len(features),
        "sources": [container.market_data_service.source_mode],
    }
