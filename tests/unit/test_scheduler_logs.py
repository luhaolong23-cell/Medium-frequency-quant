import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.shared.scheduler_logs import append_scheduler_job_log, list_scheduler_job_logs


class SchedulerLogsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_log_path = os.environ.get('QUANT_SCHEDULER_LOG_PATH')
        self._temp_dir = TemporaryDirectory()
        self._log_path = Path(self._temp_dir.name) / 'scheduler-job-logs.jsonl'
        os.environ['QUANT_SCHEDULER_LOG_PATH'] = str(self._log_path)

    def tearDown(self) -> None:
        if self._original_log_path is None:
            os.environ.pop('QUANT_SCHEDULER_LOG_PATH', None)
        else:
            os.environ['QUANT_SCHEDULER_LOG_PATH'] = self._original_log_path
        self._temp_dir.cleanup()

    def test_list_scheduler_job_logs_returns_running_entry(self) -> None:
        append_scheduler_job_log(
            {
                'job_name': 'run_daily_workflow',
                'trigger_mode': 'startup',
                'status': 'running',
                'trade_date': '2026-06-07',
                'market_codes': ['ALL'],
                'started_at': '2026-06-06T22:15:48.602729+00:00',
                'completed_at': None,
                'duration_seconds': 0.0,
                'result': {},
                'error': None,
            }
        )

        rows = list_scheduler_job_logs()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'running')
        self.assertEqual(rows[0]['trigger_mode'], 'startup')


    def test_list_scheduler_job_logs_keeps_latest_running_payload_for_same_run(self) -> None:
        started_at = '2026-06-06T22:15:48.602729+00:00'
        append_scheduler_job_log(
            {
                'job_name': 'run_daily_workflow',
                'trigger_mode': 'startup',
                'status': 'running',
                'trade_date': '2026-06-07',
                'market_codes': ['ALL'],
                'started_at': started_at,
                'completed_at': None,
                'duration_seconds': 0.0,
                'result': {'current_step': 'sync_refdata'},
                'error': None,
            }
        )
        append_scheduler_job_log(
            {
                'job_name': 'run_daily_workflow',
                'trigger_mode': 'startup',
                'status': 'running',
                'trade_date': '2026-06-07',
                'market_codes': ['ALL'],
                'started_at': started_at,
                'completed_at': None,
                'duration_seconds': 0.0,
                'result': {'current_step': 'run_regime', 'computed_regimes': 30},
                'error': None,
            }
        )

        rows = list_scheduler_job_logs()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'running')
        self.assertEqual(rows[0]['result']['current_step'], 'run_regime')
        self.assertEqual(rows[0]['result']['computed_regimes'], 30)

    def test_list_scheduler_job_logs_keeps_latest_status_for_same_run(self) -> None:
        started_at = '2026-06-06T22:15:48.602729+00:00'
        append_scheduler_job_log(
            {
                'job_name': 'run_daily_workflow',
                'trigger_mode': 'startup',
                'status': 'running',
                'trade_date': '2026-06-07',
                'market_codes': ['ALL'],
                'started_at': started_at,
                'completed_at': None,
                'duration_seconds': 0.0,
                'result': {},
                'error': None,
            }
        )
        append_scheduler_job_log(
            {
                'job_name': 'run_daily_workflow',
                'trigger_mode': 'startup',
                'status': 'completed',
                'trade_date': '2026-06-07',
                'market_codes': ['ALL'],
                'started_at': started_at,
                'completed_at': '2026-06-06T22:16:48.602729+00:00',
                'duration_seconds': 60.0,
                'result': {'computed_regimes': 30},
                'error': None,
            }
        )

        rows = list_scheduler_job_logs()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'completed')
        self.assertEqual(rows[0]['result']['computed_regimes'], 30)


if __name__ == '__main__':
    unittest.main()
