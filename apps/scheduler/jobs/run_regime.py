from datetime import date

from packages.shared.container import get_container


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    snapshots = get_container().regime_service.run_daily(
        trade_date=effective_date,
        market_codes=["ALL"],
    )
    return {
        "job": "run_regime",
        "trade_date": effective_date.isoformat(),
        "computed_regimes": len(snapshots),
    }
