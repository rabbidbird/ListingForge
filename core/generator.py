"""
ListingForge Core Generator
Sophisticated rule-based + template system that produces high-converting
Etsy / Shopify listings. Designed to feel intelligent and professional.
"""

import random
import re
from typing import Dict, List, Optional, Tuple
from .templates import (
    POWER_WORDS, CATEGORY_LANGUAGE, TITLE_STRUCTURES,
    DESCRIPTION_SECTIONS, ETSY_TAG_STRATEGIES
)
from .seo_scorer import SEOScorer
from .llm import is_llm_available, generate_with_llm


class ListingGenerator:
    def __init__(self, use_llm: bool = None):
        self.scorer = SEOScorer()
        # Auto-detect unless explicitly forced
        if use_llm is None:
            self.use_llm = is_llm_available()
        else:
            self.use_llm = bool(use_llm) and is_llm_available()

    def _normalize_category(self, category: str) -> str:
        cat = (category or "default").lower().strip()
        mapping = {
            "jewellery": "jewelry", "jewellry": "jewelry",
            "home": "home_decor", "decor": "home_decor", "home decor": "home_decor",
            "clothing": "apparel", "clothes": "apparel", "fashion": "apparel",
            "print": "art_prints", "prints": "art_prints", "wall art": "art_prints", "poster": "art_prints",
            "skincare": "beauty", "makeup": "beauty", "cosmetics": "beauty",
            "digital download": "digital", "printable": "digital", "template": "digital",
        }
        for key, val in mapping.items():
            if key in cat:
                return val
        return cat if cat in CATEGORY_LANGUAGE else "default"

    def _pick_power(self, category: str = "quality", count: int = 1) -> List[str]:
        pool = POWER_WORDS.get(category, POWER_WORDS["quality"])
        return random.sample(pool, min(count, len(pool)))

    def _get_cat_data(self, category: str) -> Dict:
        return CATEGORY_LANGUAGE.get(self._normalize_category(category), CATEGORY_LANGUAGE["default"])

    def generate_title(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        audience: str = "",
        material: str = "",
        platform: str = "etsy",
        style: str = "balanced",
    ) -> List[str]:
        """Generate 3-5 high-quality title variants."""
        cat_data = self._get_cat_data(category)
        product = product_name.strip()
        keyword = primary_keyword.strip() or product
        audience = audience.strip() or "you"
        material = material.strip() or random.choice(cat_data["materials"])
        benefit = random.choice(cat_data["benefits"])
        emotion = random.choice(cat_data["emotions"])
        occasion = random.choice(cat_data["occasions"])
        power = self._pick_power(random.choice(["quality", "benefit", "social_proof"]))[0]

        variants = []

        # Structure-based
        for structure in random.sample(TITLE_STRUCTURES, min(4, len(TITLE_STRUCTURES))):
            try:
                title = structure.format(
                    power=power,
                    product=product.title() if len(product) < 40 else product,
                    benefit=benefit.title(),
                    material=material.title(),
                    audience=audience.title(),
                    occasion=occasion.title(),
                    emotion=emotion.title(),
                )
                # Clean up
                title = re.sub(r'\s+', ' ', title).strip()
                title = title.replace(" |  |", " |").replace(" -  -", " -")
                variants.append(title)
            except Exception:
                continue

        # Keyword-front loaded strong variant – keep clean, avoid repetition
        material_part = material.title()
        if material.lower() in keyword.lower() or material.lower() in product.lower():
            material_part = ""
        strong = f"{keyword.title()} - {power}"
        if material_part:
            strong += f" {material_part}"
        strong += f" | {benefit.title()}"
        strong = re.sub(r'\s+', ' ', strong).strip(" -|")
        variants.insert(0, strong)

        # Platform length control + dedupe similar
        max_len = 140 if platform == "etsy" else 70
        cleaned = []
        seen_normalized = set()
        for v in variants:
            v = re.sub(r'\s+', ' ', v).strip(" -|")
            if len(v) > max_len:
                v = v[:max_len-3].rsplit(' ', 1)[0] + "..."
            # Simple dedupe by first 40 chars
            key = v.lower()[:40]
            if v and key not in seen_normalized:
                cleaned.append(v)
                seen_normalized.add(key)

        return cleaned[:5] if cleaned else [product_name.title()]

    def generate_description(
        self,
        product_name: str,
        primary_keyword: str = "",
        features: List[str] = None,
        category: str = "default",
        material: str = "",
        audience: str = "",
        tone: str = "professional",
        include_emoji: bool = True,
    ) -> str:
        cat_data = self._get_cat_data(category)
        product = product_name.strip()
        keyword = primary_keyword.strip() or product
        features = features or []
        material = material or random.choice(cat_data["materials"])
        audience = audience or "discerning customers"

        # Build feature list
        if not features:
            features = [
                f"Crafted with {material}",
                random.choice(cat_data["benefits"]).capitalize(),
                f"Designed for {random.choice(cat_data['occasions'])}",
                random.choice(cat_data["emotions"]).capitalize() + " aesthetic",
            ]

        # Ensure we have at least 4
        while len(features) < 4:
            features.append(random.choice(cat_data["benefits"]).capitalize())

        benefit = random.choice(cat_data["benefits"])
        clean_phrases = [
            f"brings {benefit} to your everyday",
            f"makes {benefit} effortless",
            f"is designed for {benefit}",
            f"elevates your space with {benefit}",
            f"gives you {benefit} without compromise",
        ]
        benefit_phrase = random.choice(clean_phrases)
        power = self._pick_power("quality")[0]

        # Hook
        hook_template = random.choice(DESCRIPTION_SECTIONS["hook"])
        try:
            hook = hook_template.format(
                product=product,
                benefit_phrase=benefit_phrase,
                power=power.lower(),
            )
        except KeyError:
            hook = f"Discover the {product} that {benefit_phrase}."

        # Features block
        emoji_prefix = "✨ " if include_emoji else "• "
        feature_lines = "\n".join(f"{emoji_prefix}{f}" for f in features[:6])

        # Why choose
        reasons = [
            f"Premium {material} construction",
            f"Thoughtfully designed for real life",
            f"Makes a meaningful gift",
            f"Backed by excellent customer feedback patterns",
        ]
        reasons_text = "\n".join(f"→ {r}" for r in reasons)

        # Perfect for
        occasions = cat_data["occasions"] + ["treating yourself", "thoughtful gifting"]
        occ_text = "\n".join(f"• {o.title()}" for o in random.sample(occasions, min(4, len(occasions))))

        # Details
        details = [
            f"Material: {material.title()}",
            f"Style: {random.choice(cat_data['emotions']).title()}",
            "Care: Easy to maintain",
            "Origin: Designed with intention",
        ]
        details_text = "\n".join(f"• {d}" for d in details)

        # CTA
        cta = random.choice(DESCRIPTION_SECTIONS["cta"])

        # Assemble with keyword weaving
        description = f"""{hook}

{feature_lines}

Why customers choose this {keyword}:
{reasons_text}

Perfect for:
{occ_text}

Product details:
{details_text}

{cta}

Search-friendly note: This {keyword} is crafted to stand out with {random.choice(cat_data['benefits'])} and lasting quality.
"""
        # Clean extra whitespace
        description = re.sub(r'\n{3,}', '\n\n', description).strip()
        return description

    def generate_tags(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        material: str = "",
        audience: str = "",
        extra_keywords: List[str] = None,
        platform: str = "etsy",
        max_tags: int = 13,
    ) -> List[str]:
        cat_data = self._get_cat_data(category)
        product = product_name.lower().strip()
        keyword = (primary_keyword or product).lower().strip()
        material = (material or random.choice(cat_data["materials"])).lower()
        audience = (audience or "").lower()
        extra = [k.lower().strip() for k in (extra_keywords or []) if k.strip()]

        candidates = set()

        # Core
        candidates.add(keyword)
        if product != keyword:
            candidates.add(product)

        # Material combinations
        candidates.add(f"{material} {keyword}")
        candidates.add(f"{material} {product}")
        candidates.add(material)

        # Benefit / style
        for b in random.sample(cat_data["benefits"], min(3, len(cat_data["benefits"]))):
            candidates.add(f"{b} {keyword}")
            candidates.add(b)

        # Occasion
        for o in random.sample(cat_data["occasions"], min(3, len(cat_data["occasions"]))):
            candidates.add(f"{o} gift")
            candidates.add(o)

        # Audience
        if audience:
            candidates.add(f"{keyword} for {audience}")
            candidates.add(f"gift for {audience}")

        # Emotion / style
        for e in random.sample(cat_data["emotions"], min(2, len(cat_data["emotions"]))):
            candidates.add(f"{e} {keyword}")

        # Extra user keywords
        for ek in extra:
            candidates.add(ek)
            candidates.add(f"{ek} {keyword}")

        # Long-tail expansions
        candidates.add(f"handmade {keyword}")
        candidates.add(f"unique {keyword}")
        candidates.add(f"custom {product}")
        candidates.add(f"best {keyword}")

        # Clean and filter
        cleaned = []
        for tag in candidates:
            tag = re.sub(r'\s+', ' ', tag).strip()
            # Remove accidental double words
            tag = re.sub(r'\b(\w+)\s+\1\b', r'\1', tag)
            if not tag or len(tag) < 3:
                continue
            if platform == "etsy" and len(tag) > 20:
                # Truncate smartly
                tag = tag[:20].rsplit(' ', 1)[0].strip()
            if tag and tag not in cleaned and len(tag) >= 3:
                cleaned.append(tag)

        # Prioritize longer / more specific
        cleaned.sort(key=lambda t: (len(t.split()), len(t)), reverse=True)

        # Ensure primary is included
        final = []
        if keyword not in [t.lower() for t in cleaned[:max_tags]]:
            final.append(keyword[:20] if platform == "etsy" else keyword)

        for t in cleaned:
            if len(final) >= max_tags:
                break
            if t.lower() not in [x.lower() for x in final]:
                final.append(t)

        # Pad if needed with high-quality fillers
        fillers = [
            f"gift {keyword}", f"{keyword} gift", "handmade gift",
            "unique gift", "personalized", "artisan", "premium quality"
        ]
        for f in fillers:
            if len(final) >= max_tags:
                break
            f = f[:20] if platform == "etsy" else f
            if f.lower() not in [x.lower() for x in final]:
                final.append(f)

        return final[:max_tags]

    def generate_full_listing(
        self,
        product_name: str,
        primary_keyword: str = "",
        category: str = "default",
        material: str = "",
        audience: str = "",
        features: List[str] = None,
        extra_keywords: List[str] = None,
        platform: str = "etsy",
        tone: str = "professional",
        force_template: bool = False,
    ) -> Dict:
        """Generate a complete optimized listing with scores.
        Tries real LLM first (if available and not force_template), falls back to high-quality templates.
        """
        llm_result = None
        if self.use_llm and not force_template:
            llm_result = generate_with_llm(
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                material=material,
                audience=audience,
                features=features,
                extra_keywords=extra_keywords,
                platform=platform,
            )

        if llm_result:
            titles = llm_result.get("titles") or [llm_result["best_title"]]
            description = llm_result["description"]
            tags = llm_result["tags"]
            best_title = llm_result["best_title"]
            source = "llm"
            model = llm_result.get("meta", {}).get("model", "unknown")
        else:
            titles = self.generate_title(
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                audience=audience,
                material=material,
                platform=platform,
            )
            description = self.generate_description(
                product_name=product_name,
                primary_keyword=primary_keyword,
                features=features,
                category=category,
                material=material,
                audience=audience,
                tone=tone,
            )
            tags = self.generate_tags(
                product_name=product_name,
                primary_keyword=primary_keyword,
                category=category,
                material=material,
                audience=audience,
                extra_keywords=extra_keywords,
                platform=platform,
            )
            best_title = titles[0] if titles else product_name
            source = "template"
            model = None

        # Always score (works for both LLM and template output)
        title_score = self.scorer.score_title(best_title, primary_keyword or product_name, platform)
        desc_score = self.scorer.score_description(description, primary_keyword or product_name, extra_keywords or [])
        tags_score = self.scorer.score_tags(tags, primary_keyword or product_name, platform)
        overall = self.scorer.overall_score(title_score, desc_score, tags_score)

        return {
            "titles": titles,
            "best_title": best_title,
            "description": description,
            "tags": tags,
            "platform": platform,
            "scores": {
                "title": title_score,
                "description": desc_score,
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
            },
        }
