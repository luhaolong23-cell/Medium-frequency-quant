from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from apps.scheduler.main import run_daily as run_scheduler_daily
from packages.shared.api_models import ApiSuccess, JobRunResult

router = APIRouter(prefix="/admin", tags=["admin"])


class DailyRunRequest(BaseModel):
    trade_date: date | None = None
    market_codes: list[str] = Field(default_factory=lambda: ["ALL"])


@router.post("/run-daily", response_model=ApiSuccess[JobRunResult])
def run_daily(request: DailyRunRequest) -> ApiSuccess[JobRunResult]:
    run_date = request.trade_date or date.today()
    result = run_scheduler_daily(
        trade_date=run_date,
        market_codes=request.market_codes,
    )
    return ApiSuccess(data=result)
