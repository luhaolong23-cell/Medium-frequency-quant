from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from packages.shared.runtime import project_root


def scheduler_log_path() -> Path:
    configured = os.environ.get('QUANT_SCHEDULER_LOG_PATH')
    if configured:
        return Path(configured)
    return project_root() / 'data' / 'scheduler-job-logs.jsonl'


def append_scheduler_job_log(entry: dict[str, Any]) -> None:
    path = scheduler_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, default=str, sort_keys=True))
        handle.write('\n')


def list_scheduler_job_logs(limit: int = 30) -> list[dict[str, Any]]:
    path = scheduler_log_path()
    if not path.exists():
        return []
    entries_by_run: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            key = (
                str(entry.get('job_name')),
                str(entry.get('trigger_mode')),
                str(entry.get('started_at')),
                json.dumps(entry.get('market_codes', []), ensure_ascii=False, sort_keys=True),
            )
            entries_by_run[key] = entry
    entries = list(entries_by_run.values())
    entries.reverse()
    if limit <= 0:
        return entries
    return entries[:limit]
