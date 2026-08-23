"""Apply Alembic migrations with a short database-readiness retry window."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from alembic import command

from .config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)


def _alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


@lru_cache(maxsize=1)
def expected_migration_heads() -> frozenset[str]:
    """Return the repository's declared Alembic heads."""
    return frozenset(ScriptDirectory.from_config(_alembic_config()).get_heads())


def database_at_migration_head(session: Session) -> bool:
    """Fail health checks when the database revision is absent or outdated."""
    current = frozenset(MigrationContext.configure(session.connection()).get_current_heads())
    return bool(current) and current == expected_migration_heads()


def main() -> None:
    get_settings().validate_for_production()
    config = _alembic_config()
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
