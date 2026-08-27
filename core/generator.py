"""Fact-locked draft listing generator.

Only user-supplied product attributes may appear. The optional LLM may order
opaque IDs for complete supplied phrases; deterministic code renders the text,
and every free-form or invalid response falls back to templates.
"""

from __future__ import annotations

import re
from typing import Any

from .llm import generate_with_llm, is_llm_available, source_phrase_catalog
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
    "ethically sourced",
    "exclusive",
    "fade resistant",
    "fade-resistant",
    "fair trade",
    "fair-trade",
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
    "lead free",
    "lead-free",
    "leather",
    "lifetime warranty",
    "limited edition",
    "limited stock",
    "linen",
    "locally made",
    "locally-made",
    "made in",
    "machine washable",
    "medical grade",
    "medical-grade",
    "museum quality",
    "museum-quality",
    "natural",
    "nickel free",
    "nickel-free",
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
    "small batch",
    "small-batch",
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

# A prohibited term in a negative statement is not an affirmative product fact.
# Keep the complete negative phrase, but never extract the term into a positive
# title/tag/LLM claim (for example, "not waterproof" must not yield
# "waterproof"). Punctuation starts a new clause so a negation does not leak
# into an unrelated supplied fact.
NEGATION_WORDS = frozenset(
    {
        "ain't",
        "aint",
        "aren't",
        "arent",
        "can't",
        "cannot",
        "cant",
        "didn't",
        "didnt",
        "doesn't",
        "doesnt",
        "don't",
        "dont",
        "isn't",
        "isnt",
        "neither",
        "never",
        "no",
        "non",
        "nor",
        "not",
        "wasn't",
        "wasnt",
        "weren't",
        "werent",
        "without",
        "won't",
        "wont",
    }
)
NEGATION_EXCEPTIONS = frozenset({"just", "merely", "only"})

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
        # Whitespace normalization is safe; punctuation trimming or repeated-word
        # removal is not. For example, `-5` and `1 1/2` are supplied facts.
        return re.sub(r"\s+", " ", str(text)).strip()

    @staticmethod
    def _smart_title(text: str) -> str:
        return " ".join(
            word
            if not word.isalpha() or any(char.isupper() for char in word[1:])
            else word.capitalize()
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
    def _term_present_affirmatively(text: str, term: str) -> bool:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 120) : match.start()].lower()
            # Negation applies only inside the current clause.
            clause_prefix = re.split(r"[\n.!?;,:]", prefix)[-1]
            words = re.findall(r"[a-z]+(?:'[a-z]+)?", clause_prefix)[-6:]
            negated = False
            for index, word in enumerate(words):
                if word not in NEGATION_WORDS:
                    continue
                following = words[index + 1 :]
                if following and following[0] in NEGATION_EXCEPTIONS:
                    continue
                negated = True
            suffix = text[match.end() : match.end() + 24].lower()
            if re.match(r"^\s*(?:(?:[:=\-–—])\s*|\(\s*)?(?:false|no|none|not|0)\b", suffix):
                negated = True
            if not negated:
                return True
        return False

    def _contains_unsourced_claims(self, text: str, source_blob: str) -> list[str]:
        return sorted(
            term
            for term in PROHIBITED_UNLESS_SUPPLIED
            if self._term_present_affirmatively(text, term)
            and not self._term_present_affirmatively(source_blob, term)
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

    def _render_llm_phrase_plan(
        self,
        result: dict[str, Any],
        *,
        product_name: str,
        primary_keyword: str,
        material: str,
        audience: str,
        features: list[str],
        extra_keywords: list[str],
        platform: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Render only complete allowlisted phrases selected by opaque model IDs."""

        catalog = source_phrase_catalog(
            product_name=product_name,
            primary_keyword=primary_keyword,
            material=material,
            audience=audience,
            features=features,
            extra_keywords=extra_keywords,
        )
        title_groups = result.get("title_phrase_ids")
        tag_ids = result.get("tag_phrase_ids")
        feature_ids = result.get("description_feature_ids", [])
        failures: list[str] = []
        if not isinstance(title_groups, list) or not title_groups:
            failures.append("LLM phrase plan has no title arrangements")
            title_groups = []
        if not isinstance(tag_ids, list):
            failures.append("LLM phrase plan tags are invalid")
            tag_ids = []
        if not isinstance(feature_ids, list):
            failures.append("LLM phrase plan feature order is invalid")
            feature_ids = []

        allowed_ids = set(catalog)

        def valid_ids(values: Any, *, maximum: int) -> list[str] | None:
            if not isinstance(values, list) or not 1 <= len(values) <= maximum:
                return None
            if not all(isinstance(value, str) and value in allowed_ids for value in values):
                return None
            return list(dict.fromkeys(values))

        title_limit = PLATFORM_TITLE_LIMITS.get(platform, 70)
        titles: list[str] = []
        for group in title_groups[:5]:
            ids = valid_ids(group, maximum=4)
            if ids is None or not ({"product", "keyword"} & set(ids)):
                failures.append("LLM title arrangement contains invalid or incomplete phrase IDs")
                continue
            # Keep selected source phrases byte-for-byte apart from safe
            # whitespace normalization and the fixed neutral separator.
            title = self._clean_text(" | ".join(catalog[value] for value in ids))
            if len(title) > title_limit:
                failures.append("LLM phrase title exceeds platform limit")
                continue
            if title and title.casefold() not in {value.casefold() for value in titles}:
                titles.append(title)

        clean_tag_ids = valid_ids(tag_ids[:13], maximum=13) if tag_ids else []
        if clean_tag_ids is None:
            failures.append("LLM tag selection contains an unknown phrase ID")
            clean_tag_ids = []
        tags: list[str] = []
        for phrase_id in clean_tag_ids:
            tag = self._fit_tag(catalog[phrase_id], platform)
            if tag and tag not in tags:
                tags.append(tag)

        ordered_features: list[str] = []
        for phrase_id in feature_ids:
            if not isinstance(phrase_id, str) or not phrase_id.startswith("feature_"):
                failures.append("LLM feature order contains a non-feature phrase ID")
                continue
            if phrase_id not in catalog:
                failures.append("LLM feature order contains an unknown phrase ID")
                continue
            value = catalog[phrase_id]
            if value not in ordered_features:
                ordered_features.append(value)
        ordered_features.extend(value for value in features if value not in ordered_features)

        if not titles:
            failures.append("LLM phrase plan produced no valid title")
        if failures:
            return None, sorted(set(failures))
        description = self.generate_description(
            product_name,
            primary_keyword,
            ordered_features,
            material=material,
            audience=audience,
        )
        result_meta = result.get("meta")
        return {
            "titles": titles,
            "best_title": titles[0],
            "description": description,
            "tags": tags,
            "meta": result_meta if isinstance(result_meta, dict) else {},
        }, []

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
                continue
            if value and value.lower() not in {existing.lower() for existing in cleaned}:
                cleaned.append(value)
        return cleaned[:5] or ["DRAFT Product Listing"]

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
                "— SellerDrafts starting draft; human review required.",
            ]
        )
        return "\n".join(lines).strip()

    @staticmethod
    def _fit_tag(tag: str, platform: str) -> str:
        value = re.sub(r"\s+", " ", tag.lower()).strip()
        if platform == "etsy" and len(value) > 20:
            return ""
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

        source_blob = self._source_blob(
            product_name=product_name,
            primary_keyword=primary_keyword,
            material=material,
            audience=audience,
            extra_keywords=extra_keywords or [],
        )

        # Source-grounded subphrases help fill available slots. Never extract a
        # shorter affirmative phrase from a supplied negative statement.
        for phrase in [product, keyword, *(extra_keywords or [])]:
            phrase_words = {
                word.casefold()
                for word in re.findall(r"[a-z]+(?:'[a-z]+)?", phrase, flags=re.IGNORECASE)
            }
            if phrase_words & NEGATION_WORDS or re.search(
                r"(?:[:=\-–—]\s*|\(\s*)(?:false|no|none|not|0)\b", phrase, flags=re.IGNORECASE
            ):
                continue
            words = phrase.split()
            candidates.extend(" ".join(words[index : index + 2]) for index in range(len(words) - 1))
            candidates.extend(words)

        final: list[str] = []
        for candidate in candidates:
            tag = self._fit_tag(candidate, platform)
            if self._contains_unsourced_claims(tag, source_blob):
                continue
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
                if "title_phrase_ids" in candidate:
                    llm_result, fact_lock_rejections = self._render_llm_phrase_plan(
                        candidate,
                        product_name=product_name,
                        primary_keyword=primary_keyword,
                        material=material,
                        audience=audience,
                        features=features,
                        extra_keywords=extra_keywords,
                        platform=platform,
                    )
                else:
                    fact_lock_rejections = self._validate_llm_result(
                        candidate, source_blob, platform
                    )
                    fact_lock_rejections.append(
                        "free-form LLM output is not accepted; source phrase IDs are required"
                    )

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
