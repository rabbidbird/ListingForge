"""Audit and rebuild user-edited drafts against their original fact inventory."""

from __future__ import annotations

import copy
import re
from typing import Any

from .claims import audit_unverified_claims
from .generator import LLM_SAFE_GLUE_WORDS
from .seo_scorer import SEOScorer

_SOURCE_KEYS = (
    "product_name",
    "primary_keyword",
    "category",
    "material",
    "audience",
    "features",
    "extra_keywords",
    "platform",
    "item_noun",
    "color",
    "size",
    "occasion_or_recipient",
    "force_template",
)
_NEUTRAL_WORDS = LLM_SAFE_GLUE_WORDS | {
    "about",
    "audience",
    "color",
    "material",
    "occasion",
    "recipient",
    "size",
    "type",
}
_TOKEN = re.compile(r"[a-z0-9]+(?:['’/-][a-z0-9]+)*", flags=re.IGNORECASE)


def original_source_facts(result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("meta") or {}
    stored = meta.get("source_facts")
    if isinstance(stored, dict):
        return {
            key: copy.deepcopy(stored.get(key, [] if key in {"features", "extra_keywords"} else ""))
            for key in _SOURCE_KEYS
        }
    return {
        key: copy.deepcopy(meta.get(key, [] if key in {"features", "extra_keywords"} else ""))
        for key in _SOURCE_KEYS
    }


def _source_text(facts: dict[str, Any]) -> str:
    values: list[str] = []
    for value in facts.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            values.append(value)
    return "\n".join(values)


def audit_edited_fields(
    result: dict[str, Any], *, title: str, description: str, tags: list[str]
) -> list[dict[str, str]]:
    source = _source_text(original_source_facts(result))
    edited = "\n".join([title, description, *tags])
    claim_matches = audit_unverified_claims(edited, source)
    claim_tokens = {
        token.casefold() for match in claim_matches for token in _TOKEN.findall(match["phrase"])
    }
    source_tokens = {token.casefold() for token in _TOKEN.findall(source)}
    new_tokens = sorted(
        {
            token.casefold()
            for token in _TOKEN.findall(edited)
            if token.casefold() not in source_tokens
            and token.casefold() not in _NEUTRAL_WORDS
            and token.casefold() not in claim_tokens
        }
    )
    warnings = [
        {
            "kind": "claim",
            "phrase": match["phrase"],
            "category": match["category"],
            "message": (
                f"“{match['phrase']}” is not backed by the original supplied facts "
                f"({match['category']})."
            ),
        }
        for match in claim_matches
    ]
    if new_tokens:
        warnings.append(
            {
                "kind": "new_wording",
                "phrase": ", ".join(new_tokens),
                "category": "New wording",
                "message": (
                    "New wording not found in the original supplied facts: "
                    + ", ".join(new_tokens)
                    + ". Confirm it describes this exact product before export."
                ),
            }
        )
    return warnings


def recheck_edited_draft(
    result: dict[str, Any],
    *,
    title: str,
    description: str,
    tags: list[str],
    explicitly_verified: bool,
) -> dict[str, Any]:
    updated = copy.deepcopy(result)
    platform = str(updated.get("platform") or "etsy")
    facts = original_source_facts(updated)
    primary = str(facts.get("primary_keyword") or "")
    title_phrase = primary if primary and primary.casefold() in title.casefold() else ""
    tag_phrase = (
        primary if primary and any(primary.casefold() in tag.casefold() for tag in tags) else ""
    )
    scorer = SEOScorer()
    title_score = scorer.score_title(title, title_phrase, platform)
    description_score = scorer.score_description(description, "", [], require_draft_notice=False)
    tags_score = scorer.score_tags(tags, tag_phrase, platform)
    overall = scorer.overall_score(title_score, description_score, tags_score)
    warnings = audit_edited_fields(updated, title=title, description=description, tags=tags)
    if any(warning["kind"] == "claim" for warning in warnings):
        overall["status"] = "Verify"
    elif warnings and overall["status"] == "Pass":
        overall["status"] = "Review"

    updated["titles"] = [title]
    updated["best_title"] = title
    updated["description"] = description
    updated["tags"] = tags
    updated["scores"] = {
        "title": title_score,
        "description": description_score,
        "tags": tags_score,
        "overall": overall,
    }
    updated["review_notes"] = [
        *list(overall.get("feedback") or []),
        *(warning["message"] for warning in warnings),
    ] or ["No structural warning was found; verify every factual claim before publishing."]
    updated.setdefault("meta", {})["claim_warnings"] = [
        warning["phrase"] for warning in warnings if warning["kind"] == "claim"
    ]
    updated["meta"]["source_facts"] = facts
    updated["edit_review"] = {
        "warnings": warnings,
        "explicitly_verified": bool(explicitly_verified and warnings),
        "export_ready": bool(not warnings or explicitly_verified),
    }
    return updated


def draft_export_ready(result: dict[str, Any]) -> bool:
    review = result.get("edit_review")
    return not isinstance(review, dict) or bool(review.get("export_ready"))
