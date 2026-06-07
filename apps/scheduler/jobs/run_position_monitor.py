from datetime import date

from packages.shared.container import get_container
from packages.shared.logging import get_logger, log_event


logger = get_logger(__name__)


def run(trade_date: date | None = None) -> dict:
    effective_date = trade_date or date.today()
    container = get_container()
    log_event(logger, 'scheduler.run_position_monitor.started', trade_date=effective_date.isoformat())
    signals, orders, positions = container.trading_service.run_position_monitor(effective_date)
    payload = {
        'job': 'run_position_monitor',
        'trade_date': effective_date.isoformat(),
        'generated_signals': len(signals),
        'executed_orders': len(orders),
        'open_positions': len([position for position in positions if position.status == 'OPEN']),
        'closed_positions': len([position for position in positions if position.status == 'CLOSED']),
        'source_mode': container.trading_service.source_mode,
        'position_data_source_mode': getattr(container.position_data_provider, 'source_mode', 'unknown'),
    }
    log_event(logger, 'scheduler.run_position_monitor.completed', **payload)
    return payload
