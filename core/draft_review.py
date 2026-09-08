"""Audit and rebuild user-edited drafts against their original fact inventory."""

from __future__ import annotations

import copy
import re
from typing import Any

from .claims import NEGATION_WORDS, audit_unverified_claims
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
_FACT_TOKEN = re.compile(r"\d+(?:\.\d+)?(?:/\d+)?|[a-z]+(?:['’/-][a-z0-9]+)*", re.IGNORECASE)
_NEGATION_PATTERN = re.compile(
    rf"(?<!\w)(?:{'|'.join(re.escape(word) for word in NEGATION_WORDS)})(?!\w)",
    flags=re.IGNORECASE,
)


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


def _factual_source_spans(facts: dict[str, Any]) -> list[str]:
    """Return supplied spans whose internal number or polarity must stay intact."""

    values: list[str] = []
    for key, raw_value in facts.items():
        if key in {"category", "platform", "force_template"}:
            continue
        candidates = raw_value if isinstance(raw_value, list) else [raw_value]
        for candidate in candidates:
            value = " ".join(str(candidate).split())
            if not value or (not re.search(r"\d", value) and not _NEGATION_PATTERN.search(value)):
                continue
            if value.casefold() not in {existing.casefold() for existing in values}:
                values.append(value)
    return values


def _source_span_warnings(
    result: dict[str, Any], facts: dict[str, Any], *, title: str, description: str, tags: list[str]
) -> list[dict[str, str]]:
    """Detect changed factual spans per field, even when the vocabulary is unchanged."""

    stored_fields = (result.get("meta") or {}).get("source_rendered_fields")
    stored_fields = stored_fields if isinstance(stored_fields, dict) else {}
    original_fields = {
        "title": str(stored_fields.get("title") or result.get("best_title") or ""),
        "description": str(stored_fields.get("description") or result.get("description") or ""),
        "tags": "\n".join(
            str(tag) for tag in list(stored_fields.get("tags") or result.get("tags") or [])
        ),
    }
    edited_fields = {"title": title, "description": description, "tags": "\n".join(tags)}
    warnings: list[dict[str, str]] = []
    for span in _factual_source_spans(facts):
        source_span = span.casefold()
        for field, original in original_fields.items():
            if (
                source_span not in original.casefold()
                or source_span in edited_fields[field].casefold()
            ):
                continue
            warnings.append(
                {
                    "kind": "fact_span",
                    "phrase": span,
                    "category": "Source fact changed",
                    "message": (
                        f"The supplied factual span “{span}” was changed in the {field}. "
                        "Restore the exact verified wording or explicitly verify the edit before export."
                    ),
                }
            )
    return warnings


def _legacy_product_span_warnings(
    result: dict[str, Any], facts: dict[str, Any], *, title: str
) -> list[dict[str, str]]:
    """Flag a legacy title that looks like a partial mandatory product assertion.

    Old rows have no immutable rendered-field baseline. This deliberately does
    not flag a title merely because it omits a product phrase: it needs a strong
    token overlap that indicates the phrase was started and then damaged.
    """

    if isinstance((result.get("meta") or {}).get("source_rendered_fields"), dict):
        return []
    product = " ".join(str(facts.get("product_name") or "").split())
    if not product or (not re.search(r"\d", product) and not _NEGATION_PATTERN.search(product)):
        return []
    source_tokens = [token.casefold() for token in _FACT_TOKEN.findall(product)]
    title_tokens = [token.casefold() for token in _FACT_TOKEN.findall(title)]
    if not source_tokens or product.casefold() in " ".join(title_tokens):
        return []
    source_counts = {token: source_tokens.count(token) for token in set(source_tokens)}
    title_counts = {token: title_tokens.count(token) for token in set(title_tokens)}
    overlap = sum(min(count, title_counts.get(token, 0)) for token, count in source_counts.items())
    non_negated_tokens = [token for token in source_tokens if token not in NEGATION_WORDS]
    likely_partial = overlap >= max(2, len(source_tokens) - 1) or (
        bool(_NEGATION_PATTERN.search(product))
        and bool(non_negated_tokens)
        and all(token in title_counts for token in non_negated_tokens)
    )
    if not likely_partial:
        return []
    return [
        {
            "kind": "fact_span",
            "phrase": product,
            "category": "Legacy source fact changed",
            "message": (
                f"The stored title appears to contain a partial version of the supplied product "
                f"fact “{product}”. Restore the exact verified wording or explicitly verify the "
                "legacy edit before export."
            ),
        }
    ]


def audit_edited_fields(
    result: dict[str, Any], *, title: str, description: str, tags: list[str]
) -> list[dict[str, str]]:
    facts = original_source_facts(result)
    source = _source_text(facts)
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
    warnings.extend(
        _source_span_warnings(result, facts, title=title, description=description, tags=tags)
    )
    warnings.extend(_legacy_product_span_warnings(result, facts, title=title))
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
    validation_warnings = [
        {
            "kind": "platform_validation",
            "phrase": "tags",
            "category": "Platform validation",
            "message": message,
        }
        for message in scorer.validate_tags(tags, platform)
    ]
    title_limit = scorer.score_title(title, "", platform).get("limit", 70)
    if platform != "shopify" and len(title) > int(title_limit):
        validation_warnings.append(
            {
                "kind": "platform_validation",
                "phrase": "title",
                "category": "Platform validation",
                "message": f"Title exceeds the current {platform.title()} checklist limit ({title_limit}).",
            }
        )
    warnings.extend(validation_warnings)
    if validation_warnings or any(warning["kind"] == "claim" for warning in warnings):
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
    updated["meta"].setdefault(
        "source_rendered_fields",
        {
            "title": str(result.get("best_title") or ""),
            "description": str(result.get("description") or ""),
            "tags": list(result.get("tags") or []),
        },
    )
    updated["edit_review"] = {
        "warnings": warnings,
        "explicitly_verified": bool(explicitly_verified and warnings),
        "export_ready": bool(not validation_warnings and (not warnings or explicitly_verified)),
    }
    return updated


def draft_export_ready(result: dict[str, Any]) -> bool:
    platform = str(result.get("platform") or "etsy")
    title = str(result.get("best_title") or "")
    title_limit = SEOScorer.score_title(title, "", platform).get("limit", 70)
    if (platform != "shopify" and len(title) > int(title_limit)) or SEOScorer.validate_tags(
        list(result.get("tags") or []), platform
    ):
        return False
    review = result.get("edit_review")
    return not isinstance(review, dict) or bool(review.get("export_ready"))
