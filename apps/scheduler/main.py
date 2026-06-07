from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler

from apps.scheduler.jobs import (
    ingest_market_bars,
    prepare_hot_themes,
    run_coarse_screen,
    run_position_monitor,
    run_regime,
    sync_refdata,
    sync_stock_universe_inventory,
)
from packages.shared.api_models import JobRunResult
from packages.shared.container import get_container
from packages.shared.logging import get_logger, log_event
from packages.shared.runtime import project_root
from packages.shared.scheduler_logs import append_scheduler_job_log
from packages.shared.settings import load_app_config


logger = get_logger(__name__)


def _normalize_result_payload(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    model_dump = getattr(result, 'model_dump', None)
    if callable(model_dump):
        return model_dump()
    if hasattr(result, '__dict__'):
        return dict(result.__dict__)
    return {'value': result}


def _extract_trade_date(payload: dict[str, Any], fallback: date | None = None) -> str | None:
    if payload.get('trade_date'):
        return str(payload['trade_date'])
    if fallback is not None:
        return fallback.isoformat()
    return None


def _extract_market_codes(payload: dict[str, Any], fallback: list[str] | None = None) -> list[str]:
    if isinstance(payload.get('market_codes'), list):
        return [str(item) for item in payload['market_codes']]
    if isinstance(payload.get('tracked_bull_markets'), list):
        return [str(item) for item in payload['tracked_bull_markets']]
    return list(fallback or [])


def _execute_logged_job(
    job_name: str,
    runner: Callable[[Callable[[dict[str, Any]], None] | None], Any],
    *,
    trigger_mode: str,
    trade_date: date | None = None,
    market_codes: list[str] | None = None,
) -> Any:
    started_at = datetime.now(timezone.utc)
    log_event(
        logger,
        'scheduler.job.started',
        job_name=job_name,
        trigger_mode=trigger_mode,
        trade_date=trade_date.isoformat() if trade_date else None,
        market_codes=market_codes or [],
        started_at=started_at.isoformat(),
    )
    append_scheduler_job_log({
        'job_name': job_name,
        'trigger_mode': trigger_mode,
        'status': 'running',
        'trade_date': trade_date.isoformat() if trade_date else None,
        'market_codes': list(market_codes or []),
        'started_at': started_at.isoformat(),
        'completed_at': None,
        'duration_seconds': 0.0,
        'result': {},
        'error': None,
    })
    def _progress_callback(payload: dict[str, Any]) -> None:
        append_scheduler_job_log({
            'job_name': job_name,
            'trigger_mode': trigger_mode,
            'status': 'running',
            'trade_date': payload.get('trade_date', trade_date.isoformat() if trade_date else None),
            'market_codes': list(payload.get('market_codes', market_codes or [])),
            'started_at': started_at.isoformat(),
            'completed_at': None,
            'duration_seconds': 0.0,
            'result': payload,
            'error': None,
        })

    try:
        result = runner(_progress_callback)
        payload = _normalize_result_payload(result)
        completed_at = datetime.now(timezone.utc)
        entry = {
            'job_name': job_name,
            'trigger_mode': trigger_mode,
            'status': 'completed',
            'trade_date': _extract_trade_date(payload, trade_date),
            'market_codes': _extract_market_codes(payload, market_codes),
            'started_at': started_at.isoformat(),
            'completed_at': completed_at.isoformat(),
            'duration_seconds': round((completed_at - started_at).total_seconds(), 3),
            'result': payload,
            'error': None,
        }
        append_scheduler_job_log(entry)
        log_event(logger, 'scheduler.job.completed', **entry)
        return result
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        entry = {
            'job_name': job_name,
            'trigger_mode': trigger_mode,
            'status': 'failed',
            'trade_date': trade_date.isoformat() if trade_date else None,
            'market_codes': list(market_codes or []),
            'started_at': started_at.isoformat(),
            'completed_at': completed_at.isoformat(),
            'duration_seconds': round((completed_at - started_at).total_seconds(), 3),
            'result': {},
            'error': str(exc),
        }
        append_scheduler_job_log(entry)
        log_event(logger, 'scheduler.job.failed', **entry)
        raise


def run_daily(trade_date: date | None = None, market_codes: list[str] | None = None) -> JobRunResult:
    run_date = trade_date or date.today()
    requested_codes = market_codes or ['ALL']
    result = _execute_logged_job(
        'run_daily_workflow',
        lambda progress_callback=None: get_container().orchestrator.run(
            trade_date=run_date,
            market_codes=requested_codes,
            progress_callback=progress_callback,
        ),
        trigger_mode='manual',
        trade_date=run_date,
        market_codes=requested_codes,
    )
    if isinstance(result, JobRunResult):
        return result
    return JobRunResult.model_validate(result)


def initialize_scheduler_runtime(trade_date: date | None = None, market_codes: list[str] | None = None) -> None:
    run_date = trade_date or date.today()
    requested_codes = market_codes or ['ALL']
    _execute_logged_job(
        'run_daily_workflow',
        lambda progress_callback=None: get_container().orchestrator.run(
            trade_date=run_date,
            market_codes=requested_codes,
            progress_callback=progress_callback,
        ),
        trigger_mode='startup',
        trade_date=run_date,
        market_codes=requested_codes,
    )


def _wrap_scheduled_job(job_name: str, runner: Callable[[], Any], *, trade_date: date | None = None, market_codes: list[str] | None = None) -> Callable[[], Any]:
    def _run() -> Any:
        return _execute_logged_job(
            job_name,
            lambda progress_callback=None: runner(),
            trigger_mode='scheduled',
            trade_date=trade_date,
            market_codes=market_codes,
        )

    return _run


def build_scheduler() -> BlockingScheduler:
    config = load_app_config(project_root() / 'configs' / 'app.yaml')
    scheduler = BlockingScheduler(timezone=config.scheduler.timezone)
    scheduler.add_job(_wrap_scheduled_job('sync_refdata', sync_refdata.run), 'cron', hour=config.scheduler.jobs.sync_refdata_hour, id='sync_refdata', replace_existing=True)
    scheduler.add_job(_wrap_scheduled_job('ingest_market_bars', ingest_market_bars.run), 'cron', hour=config.scheduler.jobs.ingest_market_bars_hour, id='ingest_market_bars', replace_existing=True)
    scheduler.add_job(
        _wrap_scheduled_job('run_regime', run_regime.run, market_codes=['ALL']),
        'cron',
        day_of_week=config.scheduler.jobs.run_regime_day_of_week,
        hour=config.scheduler.jobs.run_regime_hour,
        id='run_regime',
        replace_existing=True,
    )
    scheduler.add_job(
        _wrap_scheduled_job('sync_stock_universe_inventory', sync_stock_universe_inventory.run, market_codes=['ALL']),
        'cron',
        day_of_week=config.scheduler.jobs.sync_stock_universe_inventory_day_of_week,
        hour=config.scheduler.jobs.sync_stock_universe_inventory_hour,
        id='sync_stock_universe_inventory',
        replace_existing=True,
    )
    scheduler.add_job(
        _wrap_scheduled_job('prepare_hot_themes', prepare_hot_themes.run, market_codes=['ALL']),
        'interval',
        days=config.scheduler.jobs.prepare_hot_themes_interval_days,
        id='prepare_hot_themes',
        replace_existing=True,
    )
    scheduler.add_job(_wrap_scheduled_job('run_daily_selection', run_coarse_screen.run), 'cron', hour=config.scheduler.jobs.run_stock_selection_hour, id='run_daily_selection', replace_existing=True)
    scheduler.add_job(_wrap_scheduled_job('run_position_monitor', run_position_monitor.run), 'cron', hour=config.scheduler.jobs.run_position_monitor_hour, id='run_position_monitor', replace_existing=True)
    return scheduler


def start_scheduler() -> None:
    scheduler = build_scheduler()
    try:
        initialize_scheduler_runtime(trade_date=date.today(), market_codes=['ALL'])
    except Exception as exc:  # noqa: BLE001
        log_event(logger, 'scheduler.bootstrap.failed', trade_date=date.today().isoformat(), market_codes=['ALL'], error=str(exc))
    log_event(logger, 'scheduler.started', timezone=str(scheduler.timezone))
    scheduler.start()


if __name__ == '__main__':
    start_scheduler()
