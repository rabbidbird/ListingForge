"""Fact-locked draft listing generator.

Only user-supplied product attributes may appear. The optional LLM may order
opaque IDs for complete supplied phrases; deterministic code renders the text,
and every free-form or invalid response falls back to templates.
"""

from __future__ import annotations

import re
from typing import Any

from .claims import NEGATION_WORDS, term_present_affirmatively
from .llm import generate_with_llm, is_llm_available, source_phrase_catalog
from .seo_scorer import SEOScorer

PLATFORM_TITLE_LIMITS = {"etsy": 140, "shopify": 70, "amazon": 75}
ETSY_TITLE_WORD_TARGET = 12
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
        minor_words = {"and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "to", "with"}
        rendered: list[str] = []
        for index, word in enumerate(text.split()):
            if not word.isalpha() or any(char.isupper() for char in word[1:]):
                rendered.append(word)
            elif index and word.casefold() in minor_words:
                rendered.append(word.lower())
            else:
                rendered.append(word.capitalize())
        return " ".join(rendered)

    @staticmethod
    def _unique_source_tokens(phrases: list[str]) -> list[str]:
        """Keep supplied tokens in order while removing case-insensitive repeats."""

        tokens: list[str] = []
        seen: set[str] = set()
        for phrase in phrases:
            for token in ListingGenerator._clean_text(phrase).split():
                key = re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold()
                key = key or token.casefold()
                if key in seen:
                    continue
                seen.add(key)
                tokens.append(token)
        return tokens

    @classmethod
    def _etsy_noun_led_title(
        cls,
        *,
        product_name: str,
        primary_phrase: str,
        item_noun: str,
        descriptors: list[str],
        maximum: int,
    ) -> str:
        product_keys = {
            re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold() or token.casefold()
            for token in cls._clean_text(product_name).split()
        }
        noun_keys = {
            re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold() or token.casefold()
            for token in cls._clean_text(item_noun).split()
        }
        primary = cls._clean_text(primary_phrase)
        primary_words = primary.split()
        primary_fits = bool(primary) and len(primary_words) < 15 and len(primary) <= maximum
        if primary_fits:
            # Keep the seller's selected phrase contiguous. Additional supplied words
            # may follow it, but are never inserted into or substituted inside it.
            base_phrases = [primary, item_noun, product_name]
        else:
            # Sellers commonly repeat the noun inside the product name. Preserve their
            # phrase order instead of producing "Necklace Teardrop Pendant".
            noun_already_in_product = bool(noun_keys) and noun_keys <= product_keys
            base_phrases = (
                [product_name]
                if noun_already_in_product or not item_noun
                else [item_noun, product_name]
            )
        tokens = cls._unique_source_tokens(base_phrases)
        if len(tokens) > 14:
            tokens = tokens[:14]
        used = {
            re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold() or token.casefold()
            for token in tokens
        }
        descriptors_added = 0
        descriptor_word_limit = (
            ETSY_TITLE_WORD_TARGET if len(tokens) <= ETSY_TITLE_WORD_TARGET else 14
        )
        for descriptor in descriptors:
            descriptor_tokens = []
            for token in cls._unique_source_tokens([descriptor]):
                key = re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold()
                key = key or token.casefold()
                if key not in used:
                    descriptor_tokens.append((token, key))
            if (
                not descriptor_tokens
                or len(tokens) + len(descriptor_tokens) > descriptor_word_limit
            ):
                continue
            candidate_tokens = tokens + [token for token, _key in descriptor_tokens]
            candidate = cls._smart_title(" ".join(candidate_tokens))
            if len(candidate) > maximum:
                continue
            tokens = candidate_tokens
            used.update(key for _token, key in descriptor_tokens)
            descriptors_added += 1
            if descriptors_added >= 3:
                break
        title = cls._smart_title(" ".join(tokens))
        return title if title and len(title) <= maximum else "DRAFT Product Listing"

    @classmethod
    def _phrase_used_in_title(cls, phrase: str, title: str) -> bool:
        phrase_keys = {
            re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold() or token.casefold()
            for token in cls._clean_text(phrase).split()
        }
        title_keys = {
            re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold() or token.casefold()
            for token in cls._clean_text(title).split()
        }
        return bool(phrase_keys) and phrase_keys <= title_keys

    @staticmethod
    def _source_blob(**fields: Any) -> str:
        parts: list[str] = []
        for value in fields.values():
            values = value if isinstance(value, list) else [value]
            parts.extend(str(item).lower().strip() for item in values if str(item).strip())
        return "\n".join(parts)

    @staticmethod
    def _term_present_affirmatively(text: str, term: str) -> bool:
        return term_present_affirmatively(text, term)

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
        item_noun: str = "",
        color: str = "",
        size: str = "",
        features: list[str] | None = None,
    ) -> list[str]:
        del category
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        extras = extra_keywords or []
        if platform == "etsy":
            title = self._etsy_noun_led_title(
                product_name=product,
                primary_phrase=primary_keyword.strip(),
                item_noun=item_noun.strip(),
                descriptors=[color, material, size],
                maximum=PLATFORM_TITLE_LIMITS["etsy"],
            )
            return [title]
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
        item_noun: str = "",
        color: str = "",
        size: str = "",
        occasion_or_recipient: str = "",
    ) -> str:
        del category
        del include_emoji
        product = self._clean_text(product_name)
        features = [feature.strip() for feature in (features or []) if feature.strip()]
        sentence_end = "" if product.endswith((".", "!", "?")) else "."
        lines = ["About this item", "", f"{product}{sentence_end}"]
        supplied_details: list[tuple[str, str]] = [
            ("Item type", item_noun),
            ("Color", color),
            ("Material", material),
            ("Size", size),
        ]
        supplied_details.extend(
            [
                ("Occasion or recipient", occasion_or_recipient),
                ("Audience", audience),
            ]
        )
        visible_details = [(label, value) for label, value in supplied_details if value.strip()]
        if visible_details or features:
            lines.extend(["", "Product details"])
            lines.extend(f"• {label}: {value}" for label, value in visible_details)
            lines.extend(f"• {feature}" for feature in features[:8])
        return "\n".join(lines).strip()

    @staticmethod
    def _fit_tag(tag: str, platform: str) -> str:
        value = re.sub(r"\s+", " ", tag.lower()).strip()
        if platform == "etsy" and len(value) > 20:
            return ""
        return value

    @classmethod
    def _source_tag_phrases(cls, phrase: str, platform: str) -> list[str]:
        """Return only complete or contiguous source phrases that fit the platform."""

        value = cls._clean_text(phrase)
        if not value:
            return []
        fitted = cls._fit_tag(value, platform)
        if fitted:
            return [fitted]
        if platform != "etsy":
            return []
        words = value.split()
        polarity_words = {
            word.casefold()
            for word in re.findall(r"[a-z]+(?:'[a-z]+)?", value, flags=re.IGNORECASE)
        }
        if polarity_words & NEGATION_WORDS or re.search(
            r"(?:[:=\-–—]\s*|\(\s*)(?:false|no|none|not|0)\b", value, flags=re.IGNORECASE
        ):
            return []

        # Break an overlong supplied phrase into a small number of readable,
        # contiguous source phrases. Connector-only edges such as "gift for" are
        # deliberately excluded; no synonym or new product word is introduced.
        connectors = {"and", "for", "or", "with"}
        results: list[str] = []

        def add_candidate(candidate_words: list[str]) -> None:
            if len(candidate_words) < 2:
                return
            if (
                candidate_words[0].casefold() in connectors
                or candidate_words[-1].casefold() in connectors
            ):
                return
            candidate = cls._fit_tag(" ".join(candidate_words), platform)
            if candidate and candidate not in results:
                results.append(candidate)

        selected_ranges: list[tuple[int, int]] = []
        index = 0
        while index < len(words):
            if not re.search(r"\d", words[index]):
                index += 1
                continue
            end = index + 1
            while end < len(words) and re.search(r"\d", words[end]):
                end += 1
            if end < len(words) and words[end].casefold() not in connectors:
                end += 1
            before = len(results)
            add_candidate(words[index:end])
            if len(results) > before:
                selected_ranges.append((index, end))
            index = end

        connector_indexes = [
            index for index, word in enumerate(words) if word.casefold() in connectors
        ]
        if connector_indexes:
            start = 0
            for index in connector_indexes:
                add_candidate(words[start:index])
                if words[index].casefold() == "for" and index > 0:
                    add_candidate(words[index - 1 :])
                start = index + 1
            add_candidate(words[start:])
            if results:
                return results[:3]

        # With no useful clause boundary, select at most two long, non-overlapping
        # spans. Every output remains an exact contiguous slice of the supplied phrase.
        for width in range(len(words) - 1, 1, -1):
            for start in range(0, len(words) - width + 1):
                end = start + width
                if any(
                    start < existing_end and end > existing_start
                    for existing_start, existing_end in selected_ranges
                ):
                    continue
                before = len(results)
                add_candidate(words[start:end])
                if len(results) > before:
                    selected_ranges.append((start, end))
                if len(results) >= 2:
                    return results
        return results

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
        item_noun: str = "",
        color: str = "",
        size: str = "",
        features: list[str] | None = None,
        occasion_or_recipient: str = "",
        title_text: str = "",
    ) -> list[str]:
        del category
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        candidates = [keyword]
        if product.lower() != keyword.lower():
            candidates.append(product)
        candidates.extend(extra_keywords or [])
        if occasion_or_recipient:
            candidates.append(occasion_or_recipient)
        if audience:
            candidates.append(audience)
        if item_noun and item_noun.casefold() not in {value.casefold() for value in candidates}:
            candidates.append(item_noun)
        for descriptor in [color, material, size, *(features or [])]:
            if descriptor and not self._phrase_used_in_title(descriptor, title_text):
                candidates.append(descriptor)

        source_blob = self._source_blob(
            product_name=product_name,
            primary_keyword=primary_keyword,
            material=material,
            audience=audience,
            item_noun=item_noun,
            color=color,
            size=size,
            features=features or [],
            occasion_or_recipient=occasion_or_recipient,
            extra_keywords=extra_keywords or [],
        )

        final: list[str] = []
        for candidate in candidates:
            for tag in self._source_tag_phrases(candidate, platform):
                if self._contains_unsourced_claims(tag, source_blob):
                    continue
                if len(tag) >= 2 and tag not in final:
                    final.append(tag)
                if len(final) >= max_tags:
                    return final
        return final

    @classmethod
    def _missing_fact_prompts(
        cls,
        *,
        category: str,
        item_noun: str,
        color: str,
        material: str,
        size: str,
        features: list[str],
    ) -> list[str]:
        normalized = cls._normalize_category(category)
        prompts: dict[str, list[tuple[bool, str]]] = {
            "jewelry": [
                (not item_noun, "What type of jewelry is it? Add the item type only if verified."),
                (not material, "Which material or metal can you verify for this exact item?"),
                (not size, "Is there a verified length, fit, or measurement buyers need?"),
            ],
            "home_decor": [
                (not item_noun, "What home décor item is the buyer receiving?"),
                (not material, "Which material can you verify for this item?"),
                (not size, "Which verified dimensions would help the buyer place it?"),
            ],
            "apparel": [
                (not item_noun, "What garment or accessory is the buyer receiving?"),
                (not material, "Which fabric or material can you verify?"),
                (not size, "Which verified size or measurements apply?"),
                (not color, "Is there a verified color or variation to include?"),
            ],
            "art_prints": [
                (not item_noun, "What kind of artwork or print is the buyer receiving?"),
                (not size, "Are verified dimensions available for this format?"),
                (not features, "Can you verify the format, medium, or included files/items?"),
            ],
            "beauty": [
                (not item_noun, "What beauty item is the buyer receiving?"),
                (not features, "Which ingredients, amount, or usage details can you verify?"),
            ],
            "digital": [
                (not item_noun, "What type of digital product is the buyer receiving?"),
                (not features, "Which file types and included files can you verify?"),
            ],
            "default": [
                (not item_noun, "What exactly is the item? Add a plain item type if useful."),
                (not features, "Which additional buyer-relevant details can you verify?"),
            ],
        }
        return [message for missing, message in prompts[normalized] if missing]

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
        item_noun: str = "",
        color: str = "",
        size: str = "",
        occasion_or_recipient: str = "",
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
            item_noun=item_noun,
            color=color,
            size=size,
            occasion_or_recipient=occasion_or_recipient,
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
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                audience=audience,
                material=material,
                platform=platform,
                extra_keywords=extra_keywords,
                item_noun=item_noun,
                color=color,
                size=size,
                features=features,
            )
            description = self.generate_description(
                product_name=product_name,
                primary_keyword=primary_keyword,
                features=features,
                category=category,
                material=material,
                audience=audience,
                item_noun=item_noun,
                color=color,
                size=size,
                occasion_or_recipient=occasion_or_recipient,
            )
            tags = self.generate_tags(
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                material=material,
                audience=audience,
                extra_keywords=extra_keywords,
                platform=platform,
                item_noun=item_noun,
                color=color,
                size=size,
                features=features,
                occasion_or_recipient=occasion_or_recipient,
                title_text=titles[0],
            )
            best_title = titles[0]
            source = "template"
            model = None

        combined = f"{' '.join(titles)} {description} {' '.join(tags)}"
        warnings = self._contains_unsourced_claims(combined, source_blob)
        if warnings:
            raise RuntimeError("Fact-lock invariant failed; output was not returned.")

        title_phrase_for_score = (
            primary_keyword if self._phrase_used_in_title(primary_keyword, best_title) else ""
        )
        title_score = self.scorer.score_title(best_title, title_phrase_for_score, platform)
        description_score = self.scorer.score_description(
            description, "", extra_keywords, require_draft_notice=False
        )
        tag_phrase_for_score = primary_keyword if primary_keyword else product_name
        if not any(tag_phrase_for_score.casefold() in tag.casefold() for tag in tags):
            tag_phrase_for_score = ""
        tags_score = self.scorer.score_tags(tags, tag_phrase_for_score, platform)
        overall = self.scorer.overall_score(title_score, description_score, tags_score)
        review_notes = list(overall.get("feedback") or [])
        if not review_notes:
            review_notes.append(
                "No structural warning was found; verify every factual claim and current marketplace rule."
            )
        missing_fact_prompts = self._missing_fact_prompts(
            category=category,
            item_noun=item_noun,
            color=color,
            material=material,
            size=size,
            features=features,
        )
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
                "item_noun": item_noun,
                "color": color,
                "size": size,
                "occasion_or_recipient": occasion_or_recipient,
                "source_facts": {
                    "product_name": product_name,
                    "primary_keyword": primary_keyword,
                    "category": self._normalize_category(category),
                    "material": material,
                    "audience": audience,
                    "features": features,
                    "extra_keywords": extra_keywords,
                    "platform": platform,
                    "item_noun": item_noun,
                    "color": color,
                    "size": size,
                    "occasion_or_recipient": occasion_or_recipient,
                    "force_template": force_template,
                },
                "source": source,
                "model": model,
                "is_draft": True,
                "claim_warnings": [],
                "llm_fact_lock_fallback": bool(fact_lock_rejections),
                "llm_rejection_reasons": fact_lock_rejections,
            },
            "review_notes": review_notes,
            "missing_fact_prompts": missing_fact_prompts,
            "disclaimer": (
                "DRAFT — verify before publishing. Confirm every material, claim, rating, "
                "shipping statement, and product attribute against your actual product."
            ),
        }
