"""Fact-locked draft listing generator.

Only user-supplied product attributes may appear. The optional LLM path is
discarded wholesale if strict source-vocabulary validation fails.
"""

from __future__ import annotations

import re
from typing import Any

from .llm import generate_with_llm, is_llm_available
from .seo_scorer import SEOScorer

PLATFORM_TITLE_LIMITS = {"etsy": 140, "shopify": 70, "amazon": 75}
KNOWN_CATEGORIES = {
    "jewelry",
    "home_decor",
    "apparel",
    "art_prints",
    "beauty",
    "digital",
    "default",
}

# Product attributes and promotional assertions that require explicit sourcing.
PROHIBITED_UNLESS_SUPPLIED = {
    "#1",
    "14k",
    "18k",
    "archival",
    "artisan",
    "authentic",
    "bamboo",
    "best seller",
    "best-seller",
    "bestseller",
    "biodegradable",
    "brass",
    "breathable",
    "certified",
    "clinical grade",
    "clinical-grade",
    "commercial use",
    "commercial-use",
    "cotton",
    "cruelty free",
    "cruelty-free",
    "custom",
    "customer favorite",
    "dishwasher safe",
    "durable",
    "eco friendly",
    "eco-friendly",
    "exclusive",
    "fade resistant",
    "fade-resistant",
    "fast shipping",
    "five star",
    "five-star",
    "food safe",
    "free returns",
    "free shipping",
    "full grain",
    "full-grain",
    "genuine leather",
    "gold",
    "guaranteed",
    "hand crafted",
    "hand-made",
    "handcrafted",
    "handmade",
    "hypoallergenic",
    "instant download",
    "leather",
    "lifetime warranty",
    "limited edition",
    "limited stock",
    "linen",
    "made in",
    "machine washable",
    "medical grade",
    "medical-grade",
    "museum quality",
    "museum-quality",
    "natural",
    "non toxic",
    "non-toxic",
    "only a few left",
    "organic",
    "personalized",
    "polyester",
    "recycled",
    "safe for",
    "selling fast",
    "ships fast",
    "ships free",
    "silk",
    "silver",
    "solid gold",
    "sterling",
    "sterling silver",
    "sustainable",
    "tarnish resistant",
    "tarnish-resistant",
    "top grain",
    "top rated",
    "top-grain",
    "top-rated",
    "vegan",
    "viral",
    "water resistant",
    "water-resistant",
    "waterproof",
    "while supplies last",
    "wood",
    "wool",
    "wrinkle resistant",
    "wrinkle-resistant",
    "5 star",
    "5-star",
}

# Neutral connective vocabulary that an LLM may add without asserting a product fact.
LLM_SAFE_GLUE_WORDS = {
    "a",
    "about",
    "additional",
    "and",
    "attribute",
    "attributes",
    "before",
    "by",
    "confirm",
    "description",
    "detail",
    "details",
    "draft",
    "for",
    "from",
    "human",
    "in",
    "information",
    "introducing",
    "is",
    "item",
    "key",
    "listing",
    "of",
    "only",
    "or",
    "product",
    "provided",
    "publishing",
    "requires",
    "review",
    "search",
    "starting",
    "supplied",
    "tag",
    "tags",
    "term",
    "the",
    "this",
    "title",
    "to",
    "use",
    "user",
    "verification",
    "verify",
    "with",
    "you",
    "your",
}


class ListingGenerator:
    def __init__(self, use_llm: bool | None = None):
        self.scorer = SEOScorer()
        available = is_llm_available()
        self.use_llm = available if use_llm is None else bool(use_llm) and available

    @staticmethod
    def _normalize_category(category: str) -> str:
        category = (category or "default").lower().strip()
        mapping = {
            "jewellery": "jewelry",
            "home": "home_decor",
            "decor": "home_decor",
            "clothing": "apparel",
            "print": "art_prints",
            "skincare": "beauty",
            "digital download": "digital",
            "printable": "digital",
        }
        if category in KNOWN_CATEGORIES:
            return category
        for key, value in mapping.items():
            if key in category:
                return value
        return "default"

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", str(text)).strip(" -|")
        return re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE).strip()

    @staticmethod
    def _smart_title(text: str) -> str:
        return " ".join(
            word if any(char.isupper() for char in word[1:]) else word.capitalize()
            for word in text.split()
        )

    @staticmethod
    def _source_blob(**fields: Any) -> str:
        parts: list[str] = []
        for value in fields.values():
            values = value if isinstance(value, list) else [value]
            parts.extend(str(item).lower().strip() for item in values if str(item).strip())
        return "\n".join(parts)

    @staticmethod
    def _term_present(text: str, term: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE))

    def _contains_unsourced_claims(self, text: str, source_blob: str) -> list[str]:
        return sorted(
            term
            for term in PROHIBITED_UNLESS_SUPPLIED
            if self._term_present(text, term) and not self._term_present(source_blob, term)
        )

    @staticmethod
    def _source_words(source_blob: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", source_blob.lower()))

    def _validate_llm_result(
        self, result: dict[str, Any], source_blob: str, platform: str
    ) -> list[str]:
        fields = [result.get("best_title"), result.get("description")]
        fields.extend(result.get("titles") or [])
        fields.extend(result.get("tags") or [])
        if not all(isinstance(value, str) and value.strip() for value in fields):
            return ["invalid LLM response structure"]
        combined = " ".join(fields)
        failures = self._contains_unsourced_claims(combined, source_blob)

        source_words = self._source_words(source_blob)
        candidate_words = set(re.findall(r"[a-z0-9]+", combined.lower()))
        unsourced_words = candidate_words - source_words - LLM_SAFE_GLUE_WORDS
        if unsourced_words:
            failures.append("unsourced vocabulary: " + ", ".join(sorted(unsourced_words)[:12]))

        source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source_blob))
        candidate_numbers = set(re.findall(r"\d+(?:\.\d+)?", combined))
        if candidate_numbers - source_numbers:
            failures.append("unsourced numeric claim")

        title_limit = PLATFORM_TITLE_LIMITS.get(platform, 70)
        candidate_titles = [result.get("best_title"), *(result.get("titles") or [])]
        if any(len(str(title)) > title_limit for title in candidate_titles):
            failures.append("title exceeds platform limit")
        if platform == "etsy" and any(len(tag) > 20 for tag in result.get("tags") or []):
            failures.append("Etsy tag exceeds 20 characters")
        return failures

    def generate_title(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        audience: str = "",
        material: str = "",
        platform: str = "etsy",
        extra_keywords: list[str] | None = None,
    ) -> list[str]:
        del category
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        extras = extra_keywords or []
        variants = [keyword, product]
        if material:
            variants.append(f"{keyword} | {material}")
        if audience:
            variants.append(f"{keyword} for {audience}")
        if material and audience:
            variants.append(f"{keyword} | {material} | for {audience}")
        variants.extend(f"{keyword} | {extra}" for extra in extras[:2])
        if keyword.lower() not in product.lower():
            variants.append(f"{keyword} | {product}")

        maximum = PLATFORM_TITLE_LIMITS.get(platform, 70)
        cleaned: list[str] = []
        for variant in variants:
            value = self._smart_title(self._clean_text(variant))
            if len(value) > maximum:
                value = value[:maximum].rsplit(" ", 1)[0].rstrip(" -|")
            if value and value.lower() not in {existing.lower() for existing in cleaned}:
                cleaned.append(value)
        return cleaned[:5] or [self._smart_title(keyword)]

    def generate_description(
        self,
        product_name: str,
        primary_keyword: str = "",
        features: list[str] | None = None,
        category: str = "default",
        material: str = "",
        audience: str = "",
        include_emoji: bool = True,
    ) -> str:
        del category
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        features = [feature.strip() for feature in (features or []) if feature.strip()]
        lines = [f"DRAFT — Introducing the {product}."]
        if keyword.lower() != product.lower():
            lines.append(f'User-supplied search term: "{keyword}".')
        lines.append("")
        if features:
            lines.append("Details you provided:")
            prefix = "•" if not include_emoji else "•"
            lines.extend(f"{prefix} {feature}" for feature in features[:8])
        else:
            lines.append(
                "Details you provided: none. Add product-specific facts before publishing."
            )
        if material or audience:
            lines.extend(["", "Additional information you provided:"])
            if material:
                lines.append(f"• Material / attribute: {material}")
            if audience:
                lines.append(f"• Audience: {audience}")
        lines.extend(
            [
                "",
                "Verify every material, claim, and product detail against the actual item before publishing.",
                "",
                "— TrueDraft starting draft; human review required.",
            ]
        )
        return "\n".join(lines).strip()

    @staticmethod
    def _fit_tag(tag: str, platform: str) -> str:
        value = re.sub(r"\s+", " ", tag.lower()).strip(" -'")
        if platform == "etsy" and len(value) > 20:
            value = value[:20].rsplit(" ", 1)[0].strip(" -'")
        return value

    def generate_tags(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        material: str = "",
        audience: str = "",
        extra_keywords: list[str] | None = None,
        platform: str = "etsy",
        max_tags: int = 13,
    ) -> list[str]:
        del category
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        candidates = [keyword]
        if product.lower() != keyword.lower():
            candidates.append(product)
        if material:
            candidates.extend([material, f"{material} {keyword}"])
        if audience:
            candidates.append(f"{keyword} for {audience}")
        candidates.extend(extra_keywords or [])

        # Source-grounded subphrases help fill available slots without inventing attributes.
        for phrase in [product, keyword, *(extra_keywords or [])]:
            words = phrase.split()
            candidates.extend(" ".join(words[index : index + 2]) for index in range(len(words) - 1))
            candidates.extend(words)

        final: list[str] = []
        for candidate in candidates:
            tag = self._fit_tag(candidate, platform)
            if len(tag) >= 2 and tag not in final:
                final.append(tag)
            if len(final) >= max_tags:
                break
        return final

    def generate_full_listing(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        material: str = "",
        audience: str = "",
        features: list[str] | None = None,
        extra_keywords: list[str] | None = None,
        platform: str = "etsy",
        tone: str = "professional",
        force_template: bool = False,
    ) -> dict[str, Any]:
        del tone
        features = features or []
        extra_keywords = extra_keywords or []
        source_blob = self._source_blob(
            product_name=product_name,
            primary_keyword=primary_keyword,
            material=material,
            audience=audience,
            features=features,
            extra_keywords=extra_keywords,
        )
        llm_result = None
        fact_lock_rejections: list[str] = []
        if self.use_llm and not force_template:
            candidate = generate_with_llm(
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                material=material,
                audience=audience,
                features=features,
                extra_keywords=extra_keywords,
                platform=platform,
            )
            if candidate:
                fact_lock_rejections = self._validate_llm_result(candidate, source_blob, platform)
                if not fact_lock_rejections:
                    llm_result = candidate

        if llm_result:
            titles = llm_result.get("titles") or [llm_result["best_title"]]
            description = llm_result["description"]
            tags = llm_result["tags"]
            best_title = llm_result["best_title"]
            source = "llm"
            model = llm_result.get("meta", {}).get("model")
        else:
            titles = self.generate_title(
                product_name,
                primary_keyword,
                category,
                audience,
                material,
                platform,
                extra_keywords,
            )
            description = self.generate_description(
                product_name,
                primary_keyword,
                features,
                category,
                material,
                audience,
            )
            tags = self.generate_tags(
                product_name,
                primary_keyword,
                category,
                material,
                audience,
                extra_keywords,
                platform,
            )
            best_title = titles[0]
            source = "template"
            model = None

        combined = f"{' '.join(titles)} {description} {' '.join(tags)}"
        warnings = self._contains_unsourced_claims(combined, source_blob)
        if warnings:
            raise RuntimeError("Fact-lock invariant failed; output was not returned.")

        title_score = self.scorer.score_title(best_title, primary_keyword or product_name, platform)
        description_score = self.scorer.score_description(
            description, primary_keyword or product_name, extra_keywords
        )
        tags_score = self.scorer.score_tags(tags, primary_keyword or product_name, platform)
        overall = self.scorer.overall_score(title_score, description_score, tags_score)
        return {
            "titles": titles,
            "best_title": best_title,
            "description": description,
            "tags": tags,
            "platform": platform,
            "scores": {
                "title": title_score,
                "description": description_score,
                "tags": tags_score,
                "overall": overall,
            },
            "meta": {
                "product_name": product_name,
                "primary_keyword": primary_keyword or product_name,
                "category": self._normalize_category(category),
                "material": material,
                "audience": audience,
                "source": source,
                "model": model,
                "is_draft": True,
                "claim_warnings": [],
                "llm_fact_lock_fallback": bool(fact_lock_rejections),
                "llm_rejection_reasons": fact_lock_rejections,
            },
            "disclaimer": (
                "DRAFT — verify before publishing. Confirm every material, claim, rating, "
                "shipping statement, and product attribute against your actual product."
            ),
        }
