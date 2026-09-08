"""Classify one known account for aggregate measurement, without reading its content."""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from core.database import session_scope
from core.models import User

_CLASSIFICATIONS = {"fixture": True, "customer": False}


def classify_account(
    account_id: str | uuid.UUID,
    classification: str,
    *,
    session: Session | None = None,
) -> bool:
    """Set one known account's measurement classification without loading account data."""
    try:
        user_id = uuid.UUID(str(account_id))
    except (TypeError, ValueError):
        return False
    value = _CLASSIFICATIONS.get(classification)
    if value is None:
        raise ValueError("classification must be fixture or customer")

    def apply(working_session: Session) -> bool:
        changed = working_session.execute(
            update(User).where(User.id == user_id).values(is_test_fixture=value)
        )
        return bool(changed.rowcount)

    if session is not None:
        return apply(session)
    with session_scope() as own_session:
        return apply(own_session)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="Known account UUID")
    parser.add_argument("--classification", choices=sorted(_CLASSIFICATIONS), required=True)
    args = parser.parse_args(argv)

    if classify_account(args.account_id, args.classification):
        print("Account measurement classification updated.")
        return 0
    print("No account classification was changed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
