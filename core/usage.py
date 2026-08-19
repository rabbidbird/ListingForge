"""
Usage tracking with per-user plans and quota counters.

Tracks:
- plan by user (`usage_users`)
- daily counts by user/date (`usage_daily`)
- monthly counts by user/month (`usage_monthly`)

Persisted to SQLite in `data/listings.db`.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict, Optional


DB_PATH = Path(__file__).parent.parent / "data" / "listings.db"
USAGE_FILE = Path(__file__).parent.parent / "data" / "usage.json"
MIGRATION_MARKER = Path(__file__).parent.parent / "data" / ".usage_json_migrated"


def _env_limit(name: str, default: int) -> int:
    value = os.environ.get(name)
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


PLANS = {
    "free": {
        "label": "Free",
        "daily": _env_limit("LISTINGFORGE_FREE_DAILY_LIMIT", 8),
        "monthly": _env_limit("LISTINGFORGE_FREE_MONTHLY_LIMIT", 40),
    },
    "starter": {
        "label": "Starter",
        "daily": _env_limit("LISTINGFORGE_STARTER_DAILY_LIMIT", 50),
        "monthly": _env_limit("LISTINGFORGE_STARTER_MONTHLY_LIMIT", 500),
    },
    "pro": {
        "label": "Pro",
        "daily": None,
        "monthly": None,
    },
    "agency": {
        "label": "Agency",
        "daily": None,
        "monthly": None,
    },
}

def normalize_plan(plan: Optional[str]) -> str:
    if plan and str(plan).strip() in PLANS:
        return str(plan).strip()
    return DEFAULT_PLAN


DEFAULT_PLAN = normalize_plan(os.environ.get("LISTINGFORGE_DEFAULT_PLAN", "free"))


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_users (
            user_id TEXT PRIMARY KEY,
            plan TEXT NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_daily (
            user_id TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, usage_date),
            FOREIGN KEY (user_id) REFERENCES usage_users(user_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_monthly (
            user_id TEXT NOT NULL,
            usage_month TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, usage_month),
            FOREIGN KEY (user_id) REFERENCES usage_users(user_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_user_date ON usage_daily(user_id, usage_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_monthly_user_month ON usage_monthly(user_id, usage_month)")
    conn.commit()


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iter_legacy_usage_records():
    if not USAGE_FILE.exists():
        return []

    try:
        import json

        data = json.loads(USAGE_FILE.read_text())
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    if "users" in data and isinstance(data["users"], dict):
        records = []
        for user_id, payload in data["users"].items():
            if not isinstance(payload, dict):
                continue
            plan = normalize_plan(payload.get("plan"))
            records.append((str(user_id), plan, payload))
        return records

    # Backward-compatible legacy shape:
    # {"daily":..., "monthly":..., "total":..., "plan": "free"}
    legacy_plan = normalize_plan(data.get("plan"))
    return [("anonymous", legacy_plan, data)]


def _normalize_map(value) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(k): _to_int(v, 0) for k, v in value.items() if isinstance(k, str)}


def _migrate_legacy_usage(conn: sqlite3.Connection):
    if MIGRATION_MARKER.exists():
        return
    records = _iter_legacy_usage_records()
    if not records:
        return

    today = date.today().isoformat()
    for user_id, plan, payload in records:
        daily = _normalize_map(payload.get("daily"))
        monthly = _normalize_map(payload.get("monthly"))
        total = _to_int(payload.get("total"), 0)

        # Ensure user exists
        row = conn.execute("SELECT plan FROM usage_users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO usage_users (user_id, plan, total, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, plan, max(0, total), today, today),
            )
        else:
            # Keep existing plan but import historical total.
            conn.execute(
                """
                UPDATE usage_users
                SET total = COALESCE(total, 0) + ?, updated_at = ?
                WHERE user_id = ?
                """,
                (total, today, user_id),
            )

        for day, count in daily.items():
            if count <= 0:
                continue
            conn.execute(
                """
                INSERT INTO usage_daily (user_id, usage_date, count)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, usage_date) DO UPDATE SET
                    count = usage_daily.count + excluded.count
                """,
                (user_id, day, count),
            )

        for usage_month, count in monthly.items():
            if count <= 0:
                continue
            conn.execute(
                """
                INSERT INTO usage_monthly (user_id, usage_month, count)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, usage_month) DO UPDATE SET
                    count = usage_monthly.count + excluded.count
                """,
                (user_id, usage_month, count),
            )

    conn.commit()
    try:
        MIGRATION_MARKER.write_text(today, encoding="utf-8")
    except Exception:
        pass


def get_plan(user_id: str = "anonymous") -> str:
    return get_usage(user_id)["plan"]


def set_plan(user_id: str = "anonymous", plan: str = DEFAULT_PLAN) -> str:
    user_id = user_id or "anonymous"
    plan = normalize_plan(plan)
    today = date.today().isoformat()
    conn = _connect()
    _ensure_schema(conn)
    _migrate_legacy_usage(conn)

    conn.execute(
        """
        INSERT INTO usage_users (user_id, plan, total, created_at, updated_at)
        VALUES (?, ?, 0, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            plan = excluded.plan,
            updated_at = excluded.updated_at
        """,
        (user_id, plan, today, today),
    )
    conn.commit()
    conn.close()
    return plan


def _remaining(limit: Optional[int], used: int) -> Optional[int]:
    if limit is None:
        return None
    return max(0, limit - used)


def get_usage(user_id: str = "anonymous") -> Dict:
    user_id = user_id or "anonymous"
    today = date.today().isoformat()
    month = date.today().strftime("%Y-%m")
    now = date.today().isoformat()

    conn = _connect()
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    _migrate_legacy_usage(conn)

    user_row = conn.execute(
        "SELECT plan, total FROM usage_users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if user_row is None:
        plan = DEFAULT_PLAN
        conn.execute(
            """
            INSERT INTO usage_users (user_id, plan, total, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (user_id, plan, now, now),
        )
    else:
        plan = normalize_plan(user_row["plan"])

    conn.execute(
        "UPDATE usage_users SET updated_at = ? WHERE user_id = ?",
        (now, user_id),
    )

    if user_row is not None and int(user_row["total"] or 0) < 0:
        conn.execute("UPDATE usage_users SET total = 0 WHERE user_id = ?", (user_id,))

    today = date.today().isoformat()
    month = date.today().strftime("%Y-%m")

    daily_count = conn.execute(
        "SELECT count FROM usage_daily WHERE user_id = ? AND usage_date = ?",
        (user_id, today),
    ).fetchone()
    daily_count = int(daily_count["count"]) if daily_count else 0

    monthly_count = conn.execute(
        "SELECT count FROM usage_monthly WHERE user_id = ? AND usage_month = ?",
        (user_id, month),
    ).fetchone()
    monthly_count = int(monthly_count["count"]) if monthly_count else 0

    if user_row is not None:
        total = int(user_row["total"] or 0)
    else:
        total = conn.execute("SELECT total FROM usage_users WHERE user_id = ?", (user_id,)).fetchone()["total"]
        total = int(total or 0)

    limits = PLANS[plan]
    daily_limit = limits["daily"]
    monthly_limit = limits["monthly"]

    daily_remaining = _remaining(daily_limit, daily_count)
    monthly_remaining = _remaining(monthly_limit, monthly_count)
    if daily_remaining is None and monthly_remaining is None:
        remaining_total = None
    elif daily_remaining is None:
        remaining_total = monthly_remaining
    elif monthly_remaining is None:
        remaining_total = daily_remaining
    else:
        remaining_total = min(daily_remaining, monthly_remaining)

    can_generate = (
        (daily_limit is None or daily_count < daily_limit)
        and (monthly_limit is None or monthly_count < monthly_limit)
    )

    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "plan": plan,
        "plan_label": limits["label"],
        "daily": daily_count,
        "monthly": monthly_count,
        "total": total,
        "daily_limit": daily_limit,
        "monthly_limit": monthly_limit,
        "daily_remaining": daily_remaining,
        "monthly_remaining": monthly_remaining,
        "remaining_total": remaining_total,
        "can_generate": can_generate,
    }


def record_generation(user_id: str = "anonymous") -> Dict:
    """Record one generation and return updated usage."""
    usage = get_usage(user_id)
    if not usage["can_generate"]:
        return usage

    user_id = user_id or "anonymous"
    today = date.today().isoformat()
    month = date.today().strftime("%Y-%m")
    now = date.today().isoformat()
    conn = _connect()
    _ensure_schema(conn)
    _migrate_legacy_usage(conn)

    conn.execute(
        """
        INSERT INTO usage_users (user_id, plan, total, created_at, updated_at)
        VALUES (?, ?, 0, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (user_id, usage["plan"], now, now),
    )
    conn.execute(
        """
        INSERT INTO usage_daily (user_id, usage_date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, usage_date) DO UPDATE SET
            count = usage_daily.count + 1
        """,
        (user_id, today),
    )
    conn.execute(
        """
        INSERT INTO usage_monthly (user_id, usage_month, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, usage_month) DO UPDATE SET
            count = usage_monthly.count + 1
        """,
        (user_id, month),
    )
    conn.execute(
        """
        UPDATE usage_users
        SET total = COALESCE(total, 0) + 1, updated_at = ?
        WHERE user_id = ?
        """,
        (now, user_id),
    )

    conn.execute(
        """
        DELETE FROM usage_daily
        WHERE user_id = ?
          AND usage_date NOT IN (
            SELECT usage_date
            FROM usage_daily
            WHERE user_id = ?
            ORDER BY usage_date DESC
            LIMIT 14
          )
        """,
        (user_id, user_id),
    )
    conn.commit()
    conn.close()
    return get_usage(user_id)


def is_limit_reached(user_id: str = "anonymous") -> bool:
    return not get_usage(user_id)["can_generate"]
