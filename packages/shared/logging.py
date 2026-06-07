import json
import logging
from typing import Any


_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
        )
        _CONFIGURED = True
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info('%s %s', event, json.dumps(fields, ensure_ascii=False, default=str, sort_keys=True))
