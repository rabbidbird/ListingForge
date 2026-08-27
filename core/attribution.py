"""Signed, first-party acquisition attribution for public campaign links."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from itsdangerous import BadData, URLSafeTimedSerializer

from .config import get_settings

ATTRIBUTION_COOKIE_NAME = "sellerdrafts_attribution"
ATTRIBUTION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
_FIELD_LIMIT = 120
_FIELDS = {
    "utm_source": "acquisition_source",
    "utm_medium": "acquisition_medium",
    "utm_campaign": "acquisition_campaign",
    "utm_content": "acquisition_content",
    "utm_term": "acquisition_term",
}
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_settings().session_secret,
        salt="sellerdrafts-attribution-v1",
    )


def _clean(value: Any, *, limit: int = _FIELD_LIMIT) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = _CONTROL_CHARACTERS.sub("", " ".join(value.split()))
    return cleaned[:limit]


def pack_attribution(query: Mapping[str, Any], *, landing_path: str) -> str | None:
    """Return a signed cookie only for explicitly tagged campaign traffic."""
    values = {field: _clean(query.get(field)) for field in _FIELDS}
    if not values["utm_source"]:
        return None
    values["landing_path"] = _clean(landing_path, limit=200) or "/"
    return _serializer().dumps(values)


def unpack_attribution(cookie_value: str | None) -> dict[str, str]:
    if not cookie_value or len(cookie_value) > 4096:
        return {}
    try:
        payload = _serializer().loads(cookie_value, max_age=ATTRIBUTION_MAX_AGE_SECONDS)
    except (BadData, TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    values = {field: _clean(payload.get(field)) for field in _FIELDS}
    if not values["utm_source"]:
        return {}
    values["landing_path"] = _clean(payload.get("landing_path"), limit=200) or "/"
    return values


def user_attribution_fields(cookie_value: str | None) -> dict[str, str]:
    values = unpack_attribution(cookie_value)
    return {
        model_field: values[query_field]
        for query_field, model_field in _FIELDS.items()
        if values.get(query_field)
    } | ({"acquisition_landing_path": values["landing_path"]} if values.get("landing_path") else {})
