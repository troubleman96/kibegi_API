from __future__ import annotations

import logging
import time

from .config import get_settings
from .db import Database
from .worker import Indexer


logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    database = Database(settings)
    database.open()
    indexer = Indexer(settings, database)
    interval = max(5, settings.job_stale_minutes * 4)
    try:
        while True:
            try:
                result = indexer.process_due()
                logger.info("AI indexing sweep: %s", result)
            except Exception:
                logger.exception("AI indexing sweep failed")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("AI indexing worker stopped")
    finally:
        database.close()


if __name__ == "__main__":
    main()
