"""Apply Alembic migrations with a short database-readiness retry window."""

from __future__ import annotations

import logging
import time

from alembic.config import Config

from alembic import command

from .config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    get_settings().validate_for_production()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    for attempt in range(1, 11):
        try:
            command.upgrade(config, "head")
            return
        except Exception:
            if attempt == 10:
                raise
            logger.warning("Database is not ready for migrations (attempt %s/10)", attempt)
            time.sleep(3)


if __name__ == "__main__":
    main()
