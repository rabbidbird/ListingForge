"""Transparent heuristic listing checklist; never a ranking or sales predictor."""

from __future__ import annotations

import re
from collections import Counter

TITLE_LIMITS = {"etsy": 140, "shopify": 70, "amazon": 75}
RESTRICTED_OR_RISKY_TERMS = {
    "#1",
    "best seller",
    "bestseller",
    "cure",
    "free shipping",
    "guaranteed",
    "limited stock",
    "medical grade",
    "ships fast",
    "top rated",
}
AMAZON_DISALLOWED_TITLE_CHARACTERS = set("!$?_{}^¬¦")


class SEOScorer:
    @staticmethod
    def score_title(title: str, primary_keyword: str, platform: str = "etsy") -> dict[str, object]:
        score = 0
        feedback: list[str] = []
        title_lower = title.lower().strip()
        keyword_lower = primary_keyword.lower().strip() if primary_keyword else ""
        length = len(title)
        limit = TITLE_LIMITS.get(platform, 70)
        if 1 <= length <= limit:
            score += 30
        else:
            if platform == "shopify":
                feedback.append(
                    "Title exceeds the SellerDrafts 70-character Shopify SEO-title target; "
                    "this is not presented as a universal product-title hard limit."
                )
            else:
                feedback.append(
                    f"Title exceeds the current {platform.title()} checklist limit ({limit})."
                )

        word_count = len(re.findall(r"\b\w+\b", title))
        if platform == "etsy" and word_count <= 15:
            score += 15
        elif platform == "etsy":
            feedback.append("Etsy currently suggests using fewer than 15 words where practical.")
        elif 3 <= word_count <= 15:
            score += 15

        if keyword_lower and keyword_lower in title_lower:
            score += 30
            if title_lower.find(keyword_lower) < 30:
                score += 10
        elif keyword_lower:
            feedback.append("The user-selected primary phrase is absent from the title.")

        words = re.findall(r"\b\w+\b", title_lower)
        repeated = [word for word, count in Counter(words).items() if count > 2]
        if repeated:
            feedback.append("Repeated words may reduce clarity: " + ", ".join(repeated[:5]))
        else:
            score += 10

        risky = [term for term in RESTRICTED_OR_RISKY_TERMS if term in title_lower]
        if risky:
            score -= 20
            feedback.append(
                "Verify or remove restricted/risky title terms: " + ", ".join(sorted(risky))
            )
        if platform == "amazon":
            bad_chars = sorted(set(title) & AMAZON_DISALLOWED_TITLE_CHARACTERS)
            if bad_chars:
                score -= 15
                feedback.append(
                    "Amazon title contains currently restricted characters: " + " ".join(bad_chars)
                )
            feedback.append(
                "Amazon category/media exceptions can differ; verify Seller Central before publishing."
            )

        return {
            "score": max(0, min(100, score)),
            "feedback": feedback,
            "length": length,
            "limit": limit,
            "keyword_present": bool(keyword_lower and keyword_lower in title_lower),
            "heuristic_only": True,
        }

    @staticmethod
    def score_description(
        description: str,
        primary_keyword: str,
        secondary_keywords: list[str] | None = None,
        *,
        require_draft_notice: bool = True,
    ) -> dict[str, object]:
        score = 0
        feedback: list[str] = []
        secondary_keywords = secondary_keywords or []
        lower = description.lower()
        length = len(description)
        word_count = len(re.findall(r"\b\w+\b", description))
        if word_count >= 35:
            score += 25
        else:
            feedback.append("Add more user-verified detail; the draft is currently brief.")
        if require_draft_notice:
            if "draft" in lower and ("verify" in lower or "review" in lower):
                score += 20
            else:
                feedback.append("Keep the DRAFT and human-verification notice visible.")

        primary = primary_keyword.lower().strip() if primary_keyword else ""
        primary_count = lower.count(primary) if primary else 0
        if 1 <= primary_count <= 5:
            score += 25
        elif primary_count > 5:
            score += 10
            feedback.append("The primary phrase may be repeated too often.")
        elif primary:
            feedback.append("The user-selected primary phrase is absent from the description.")

        if re.search(r"^\s*[•*-]", description, flags=re.MULTILINE):
            score += 15
        else:
            feedback.append("Bullets can make supplied product details easier to verify.")
        if "\n\n" in description:
            score += 10
        secondary_hits = sum(
            1 for keyword in secondary_keywords if keyword and keyword.lower() in lower
        )
        if secondary_keywords:
            score += round(5 * secondary_hits / len(secondary_keywords))

        risky = [term for term in RESTRICTED_OR_RISKY_TERMS if term in lower]
        if risky:
            score -= 20
            feedback.append("Verify or remove restricted/risky claims: " + ", ".join(sorted(risky)))
        return {
            "score": max(0, min(100, score)),
            "feedback": feedback,
            "length": length,
            "word_count": word_count,
            "primary_keyword_count": primary_count,
            "heuristic_only": True,
        }

    @staticmethod
    def score_tags(
        tags: list[str], primary_keyword: str, platform: str = "etsy"
    ) -> dict[str, object]:
        score = 0
        feedback: list[str] = []
        tags = [tag.strip().lower() for tag in tags if tag.strip()]
        if platform == "etsy":
            if len(tags) == 13:
                score += 30
            elif 1 <= len(tags) < 13:
                score += 15
                feedback.append(
                    "Etsy permits up to 13 tags; add only accurate, user-verified terms if available."
                )
            over_limit = [tag for tag in tags if len(tag) > 20]
            if over_limit:
                feedback.append(f"{len(over_limit)} Etsy tag(s) exceed 20 characters.")
            else:
                score += 20
        elif tags:
            score += 25

        primary = primary_keyword.lower().strip() if primary_keyword else ""
        if primary and any(primary in tag for tag in tags):
            score += 25
        elif primary:
            feedback.append("The user-selected primary phrase is absent from tags.")
        if len(tags) == len(set(tags)):
            score += 15
        else:
            feedback.append("Duplicate tags detected.")
        if all(re.fullmatch(r"[\w\s'-]+", tag, flags=re.UNICODE) for tag in tags):
            score += 10
        return {
            "score": max(0, min(100, score)),
            "feedback": feedback,
            "count": len(tags),
            "heuristic_only": True,
        }

    @staticmethod
    def overall_score(
        title_result: dict[str, object],
        description_result: dict[str, object],
        tags_result: dict[str, object],
    ) -> dict[str, object]:
        overall = round(
            float(title_result["score"]) * 0.40
            + float(description_result["score"]) * 0.35
            + float(tags_result["score"]) * 0.25,
            1,
        )
        grade = "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D"
        feedback = [
            *title_result["feedback"],
            *description_result["feedback"],
            *tags_result["feedback"],
        ]
        return {
            "overall": overall,
            "grade": grade,
            "title_score": title_result["score"],
            "description_score": description_result["score"],
            "tags_score": tags_result["score"],
            "feedback": feedback,
            "summary": "Heuristic checklist result only; it does not predict ranking, conversion, or sales.",
            "heuristic_only": True,
        }
