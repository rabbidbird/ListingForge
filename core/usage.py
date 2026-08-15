"""
Simple local usage tracking + free tier limits for ListingForge.
For a real multi-user SaaS this would move to a proper database + user accounts.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional

USAGE_FILE = Path(__file__).parent.parent / "data" / "usage.json"

# Free tier limits
FREE_DAILY_LIMIT = 8
FREE_MONTHLY_LIMIT = 40


def _load() -> Dict:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text())
        except Exception:
            pass
    return {"daily": {}, "monthly": {}, "total": 0}


def _save(data: Dict):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def get_usage() -> Dict:
    data = _load()
    today = date.today().isoformat()
    month = date.today().strftime("%Y-%m")

    daily_count = data.get("daily", {}).get(today, 0)
    monthly_count = data.get("monthly", {}).get(month, 0)

    return {
        "daily": daily_count,
        "monthly": monthly_count,
        "total": data.get("total", 0),
        "daily_limit": FREE_DAILY_LIMIT,
        "monthly_limit": FREE_MONTHLY_LIMIT,
        "daily_remaining": max(0, FREE_DAILY_LIMIT - daily_count),
        "monthly_remaining": max(0, FREE_MONTHLY_LIMIT - monthly_count),
        "can_generate": daily_count < FREE_DAILY_LIMIT and monthly_count < FREE_MONTHLY_LIMIT,
    }


def record_generation() -> Dict:
    """Record one generation and return updated usage."""
    data = _load()
    today = date.today().isoformat()
    month = date.today().strftime("%Y-%m")

    data.setdefault("daily", {})
    data.setdefault("monthly", {})

    data["daily"][today] = data["daily"].get(today, 0) + 1
    data["monthly"][month] = data["monthly"].get(month, 0) + 1
    data["total"] = data.get("total", 0) + 1

    if len(data["daily"]) > 14:
        for k in sorted(data["daily"].keys())[:-14]:
            del data["daily"][k]

    _save(data)
    return get_usage()


def is_limit_reached() -> bool:
    return not get_usage()["can_generate"]
