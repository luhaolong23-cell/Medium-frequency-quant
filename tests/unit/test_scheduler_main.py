import unittest
from datetime import date
from unittest.mock import patch

from apps.scheduler.main import build_scheduler, start_scheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class SchedulerMainTests(unittest.TestCase):
    def test_build_scheduler_uses_staggered_incremental_runtime(self) -> None:
        scheduler = build_scheduler()
        jobs = {job.id: job for job in scheduler.get_jobs()}

        self.assertIsInstance(jobs['sync_refdata'].trigger, CronTrigger)
        self.assertEqual(str(jobs['sync_refdata'].trigger), "cron[hour='0']")
        self.assertIsInstance(jobs['ingest_market_bars'].trigger, CronTrigger)
        self.assertEqual(str(jobs['ingest_market_bars'].trigger), "cron[hour='1']")
        self.assertIsInstance(jobs['run_regime'].trigger, CronTrigger)
        self.assertEqual(str(jobs['run_regime'].trigger), "cron[day_of_week='mon', hour='2']")
        self.assertIsInstance(jobs['sync_stock_universe_inventory'].trigger, CronTrigger)
        self.assertEqual(str(jobs['sync_stock_universe_inventory'].trigger), "cron[day_of_week='mon', hour='3']")
        self.assertIsInstance(jobs['prepare_hot_themes'].trigger, IntervalTrigger)
        self.assertEqual(jobs['prepare_hot_themes'].trigger.interval.days, 3)
        self.assertNotIn('sync_stock_universe_bars', jobs)
        self.assertNotIn('compute_stock_universe_metrics', jobs)
        self.assertIsInstance(jobs['run_daily_selection'].trigger, CronTrigger)
        self.assertEqual(str(jobs['run_daily_selection'].trigger), "cron[hour='6']")
        self.assertIsInstance(jobs['run_position_monitor'].trigger, CronTrigger)
        self.assertEqual(str(jobs['run_position_monitor'].trigger), "cron[hour='7']")
        self.assertNotIn('sync_background_universe_inventory', jobs)

    def test_start_scheduler_runs_initial_full_workflow_before_start(self) -> None:
        class _StubScheduler:
            def __init__(self) -> None:
                self.started = False
                self.timezone = 'UTC'

            def start(self) -> None:
                self.started = True

        scheduler = _StubScheduler()
        with patch('apps.scheduler.main.build_scheduler', return_value=scheduler), patch('apps.scheduler.main.initialize_scheduler_runtime') as init_mock:
            start_scheduler()

        init_mock.assert_called_once_with(trade_date=date.today(), market_codes=['ALL'])
        self.assertTrue(scheduler.started)

    def test_start_scheduler_still_starts_when_initial_workflow_fails(self) -> None:
        class _StubScheduler:
            def __init__(self) -> None:
                self.started = False
                self.timezone = 'UTC'

            def start(self) -> None:
                self.started = True

        scheduler = _StubScheduler()
        with patch('apps.scheduler.main.build_scheduler', return_value=scheduler), patch('apps.scheduler.main.initialize_scheduler_runtime', side_effect=RuntimeError('init failed')):
            start_scheduler()

        self.assertTrue(scheduler.started)


if __name__ == '__main__':
    unittest.main()
