from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess, StockUniverseView, UniverseEnrichmentRunView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/universe', tags=['universe'])


class UniverseEnrichmentRequest(BaseModel):
    trade_date: date | None = None
    market_codes: list[str] = Field(default_factory=lambda: ['ALL'])
    batch_limit: int | None = None
    batch_offset: int = 0


@router.get('/today', response_model=ApiSuccess[list[StockUniverseView]])
def universe_today(market_code: str | None = None, ticker: str | None = None) -> ApiSuccess[list[StockUniverseView]]:
    container = get_container()
    trade_date = _latest_universe_trade_date(container.selection_repository)
    if trade_date is None:
        return ApiSuccess(data=[])

    rows = container.selection_service.list_market_universe(trade_date, market_code=market_code)
    if ticker:
        wanted_ticker = ticker.strip().upper()
        rows = [row for row in rows if row.ticker.upper() == wanted_ticker]
    return ApiSuccess(data=[StockUniverseView.model_validate(row.__dict__) for row in rows])


def _latest_universe_trade_date(repository) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, '_market_universe', {})
        if not store:
            return None
        return max(trade_date for trade_date, _, _ in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None

    with sqlite_session(db_path) as connection:
        row = connection.execute('SELECT MAX(trade_date) AS trade_date FROM stock_universe_daily').fetchone()

    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])


@router.post('/enrich', response_model=ApiSuccess[UniverseEnrichmentRunView])
def enrich_universe(request: UniverseEnrichmentRequest) -> ApiSuccess[UniverseEnrichmentRunView]:
    container = get_container()
    trade_date = request.trade_date or _latest_universe_trade_date(container.selection_repository)
    if trade_date is None:
        return ApiSuccess(
            data=UniverseEnrichmentRunView(
                trade_date=date.today(),
                market_codes=[],
                processed_rows=0,
                enriched_rows=0,
                source_mode=container.selection_service.source_mode,
            )
        )

    resolved_market_codes = _resolve_market_codes(container, request.market_codes)
    before_rows = container.selection_service.list_market_universe(trade_date, market_code=None)
    before_by_key = {
        (row.market_code, row.ticker): row
        for row in before_rows
        if row.market_code in resolved_market_codes
    }
    unknown_rows = [
        row
        for row in before_by_key.values()
        if row.sector == 'Unknown' or row.industry == 'Unknown'
    ]
    unknown_rows.sort(
        key=lambda row: (
            -row.market_cap,
            -row.momentum_pct,
            -row.volume_ratio,
            row.market_code,
            row.ticker,
        )
    )
    selected_unknown_rows = unknown_rows[request.batch_offset:]
    if request.batch_limit is not None:
        selected_unknown_rows = selected_unknown_rows[: max(request.batch_limit, 0)]
    selected_unknown_keys = [(row.market_code, row.ticker) for row in selected_unknown_rows]
    repaired_rows = container.selection_service.repair_market_universe(
        trade_date,
        resolved_market_codes,
        limit=request.batch_limit,
        offset=request.batch_offset,
    )
    after_by_key = {(row.market_code, row.ticker): row for row in repaired_rows}
    enriched_rows = sum(
        1
        for key in selected_unknown_keys
        if key in after_by_key
        and (after_by_key[key].sector != 'Unknown' and after_by_key[key].industry != 'Unknown')
        and before_by_key.get(key) != after_by_key[key]
    )
    remaining_unknown_rows = sum(
        1
        for row in after_by_key.values()
        if row.sector == 'Unknown' or row.industry == 'Unknown'
    )
    return ApiSuccess(
        data=UniverseEnrichmentRunView(
            trade_date=trade_date,
            market_codes=resolved_market_codes,
            processed_rows=len(selected_unknown_keys),
            enriched_rows=enriched_rows,
            remaining_unknown_rows=remaining_unknown_rows,
            batch_limit=request.batch_limit,
            batch_offset=request.batch_offset,
            source_mode=container.selection_service.source_mode,
        )
    )


def _resolve_market_codes(container, market_codes: list[str]) -> list[str]:
    if market_codes == ['ALL']:
        return [item.market_code for item in container.markets_config.markets]
    wanted = set(market_codes)
    return [item.market_code for item in container.markets_config.markets if item.market_code in wanted]
