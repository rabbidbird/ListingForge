"""The only authorized path for single and bulk listing generation."""

from __future__ import annotations

import uuid
from typing import Any

from .database import session_scope
from .events import record_product_event, record_product_event_once
from .generator import ListingGenerator
from .llm import is_llm_available
from .usage import complete_generation, fail_generation, reserve_generation
from .utils import clean_optional_text, get_listing_by_id, save_listing, update_listing


class GenerationInputError(ValueError):
    pass


def _bounded(value: Any, *, name: str, maximum: int, required: bool = False) -> str:
    text = clean_optional_text(value)
    if required and not text:
        raise GenerationInputError(f"{name} is required.")
    if len(text) > maximum:
        raise GenerationInputError(f"{name} must be {maximum} characters or fewer.")
    return text


def normalize_generation_input(data: dict[str, Any]) -> dict[str, Any]:
    product_name = _bounded(
        data.get("product_name"), name="Product name", maximum=300, required=True
    )
    primary_keyword = _bounded(data.get("primary_keyword"), name="Primary keyword", maximum=300)
    category = _bounded(data.get("category", "default"), name="Category", maximum=80) or "default"
    material = _bounded(data.get("material"), name="Material / attribute", maximum=300)
    audience = _bounded(data.get("audience"), name="Audience", maximum=300)
    item_noun = _bounded(data.get("item_noun"), name="Item noun", maximum=120)
    color = _bounded(data.get("color"), name="Color", maximum=120)
    size = _bounded(data.get("size"), name="Size", maximum=120)
    occasion_or_recipient = _bounded(
        data.get("occasion_or_recipient"), name="Occasion or recipient", maximum=300
    )
    platform = clean_optional_text(data.get("platform", "etsy")).lower() or "etsy"
    if platform not in {"etsy", "shopify", "amazon"}:
        raise GenerationInputError("Platform must be Etsy, Shopify, or Amazon.")

    raw_features = data.get("features") or []
    raw_extras = data.get("extra_keywords") or []
    if isinstance(raw_features, str):
        raw_features = raw_features.split("|")
    if isinstance(raw_extras, str):
        raw_extras = raw_extras.split(",")
    features = [
        _bounded(value, name="Feature", maximum=500)
        for value in list(raw_features)[:8]
        if clean_optional_text(value)
    ]
    extras = [
        _bounded(value, name="Extra keyword", maximum=120)
        for value in list(raw_extras)[:20]
        if clean_optional_text(value)
    ]
    return {
        "product_name": product_name,
        "primary_keyword": primary_keyword,
        "category": category,
        "material": material,
        "audience": audience,
        "item_noun": item_noun,
        "color": color,
        "size": size,
        "occasion_or_recipient": occasion_or_recipient,
        "features": features,
        "extra_keywords": extras,
        "platform": platform,
        "force_template": bool(data.get("force_template", False)),
    }


def generate_for_user(
    user_id: uuid.UUID, data: dict[str, Any], *, mode: str = "single"
) -> tuple[dict[str, Any], uuid.UUID]:
    payload = normalize_generation_input(data)
    llm_requested = is_llm_available() and not payload["force_template"]
    provider = "llm" if llm_requested else "template"
    event_id, _plan = reserve_generation(user_id, mode=mode, provider=provider)
    try:
        generator = ListingGenerator(use_llm=llm_requested)
        result = generator.generate_full_listing(**payload)
        with session_scope() as session:
            listing_id = save_listing(user_id, result, session=session)
            complete_generation(event_id, listing_id, session=session)
            record_product_event_once(user_id, "first_draft_generated", session=session)
        return result, listing_id
    except Exception as exc:
        fail_generation(event_id, type(exc).__name__)
        record_product_event(user_id, "generation_failed")
        raise


def regenerate_for_user(user_id: uuid.UUID, listing_id: str | uuid.UUID) -> dict[str, Any]:
    existing = get_listing_by_id(user_id, listing_id)
    if existing is None:
        raise GenerationInputError("Draft not found or not authorized.")
    meta = existing.get("meta") or {}
    payload = normalize_generation_input(meta.get("source_facts") or meta)
    llm_requested = is_llm_available() and not payload["force_template"]
    provider = "llm" if llm_requested else "template"
    event_id, _plan = reserve_generation(user_id, mode="single", provider=provider)
    try:
        result = ListingGenerator(use_llm=llm_requested).generate_full_listing(**payload)
        with session_scope() as session:
            if not update_listing(user_id, listing_id, result, session=session):
                raise GenerationInputError("Draft not found or not authorized.")
            complete_generation(event_id, uuid.UUID(str(listing_id)), session=session)
        return result
    except Exception as exc:
        fail_generation(event_id, type(exc).__name__)
        record_product_event(user_id, "generation_failed")
        raise
