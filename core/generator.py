"""
ListingForge Core Generator — Fact-locked version.

Rules (non-negotiable):
- Never invent materials, construction methods, ratings, stock status,
  shipping claims, certifications, or social-proof statements the user
  did not supply.
- Missing fields stay missing. No random completion of factual attributes.
- Output is always presented as a DRAFT that requires human review.
"""

import random
import re
from typing import Dict, List, Optional, Any
from .templates import POWER_WORDS, CATEGORY_LANGUAGE
from .seo_scorer import SEOScorer
from .llm import is_llm_available, generate_with_llm


# Claims that must NEVER appear unless the user explicitly provided them
PROHIBITED_UNLESS_SUPPLIED = {
    "bestseller", "best-seller", "best seller", "5-star", "five-star", "5 star",
    "customer favorite", "top-rated", "top rated", "as seen on", "viral",
    "limited stock", "only a few left", "selling fast", "while supplies last",
    "ships fast", "free shipping", "ships free",
    "handmade", "hand-made", "hand crafted", "handcrafted", "artisan",
    "organic", "hypoallergenic", "tarnish-resistant", "tarnish resistant",
    "cruelty-free", "cruelty free", "vegan", "clinical-grade", "clinical grade",
    "museum-quality", "museum quality", "commercial use", "commercial-use",
    "solid gold", "14k", "18k", "sterling silver", "sterling",
    "genuine leather", "full-grain", "top-grain",
}


class ListingGenerator:
    def __init__(self, use_llm: bool = None):
        self.scorer = SEOScorer()
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
            "print": "art_prints", "prints": "art_prints", "wall art": "art_prints",
            "skincare": "beauty", "makeup": "beauty", "cosmetics": "beauty",
            "digital download": "digital", "printable": "digital", "template": "digital",
        }
        for key, val in mapping.items():
            if key in cat:
                return val
        return cat if cat in CATEGORY_LANGUAGE else "default"

    def _smart_title(self, text: str) -> str:
        if not text:
            return text
        words = text.split()
        result = []
        for w in words:
            if "'s" in w.lower() and len(w) > 2:
                base, _, rest = w.partition("'")
                result.append(base.capitalize() + "'" + rest.lower())
            elif "'" in w:
                parts = w.split("'")
                result.append("'" .join(p.capitalize() if p else "" for p in parts))
            else:
                result.append(w.capitalize())
        return " ".join(result)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip(" -|")
        text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
        return text.strip()

    def _contains_prohibited(self, text: str, user_supplied: set) -> List[str]:
        found = []
        lower = text.lower()
        for term in PROHIBITED_UNLESS_SUPPLIED:
            if term in lower and term not in user_supplied:
                found.append(term)
        return found

    def _user_supplied_terms(self, **fields) -> set:
        supplied = set()
        for v in fields.values():
            if not v:
                continue
            items = v if isinstance(v, list) else [v]
            for item in items:
                text = str(item).lower().strip()
                if not text:
                    continue
                supplied.add(text)
                supplied.update(re.findall(r"[a-z0-9\-]+", text))
        return supplied

    def generate_title(self, product_name: str, primary_keyword: str = "", category: str = "default", audience: str = "", material: str = "", platform: str = "etsy", extra_keywords: List[str] = None) -> List[str]:
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        audience = audience.strip()
        material = material.strip()
        extras = extra_keywords or []

        variants = []
        t1 = self._smart_title(keyword)
        if material and material.lower() not in keyword.lower():
            t1 += f" - {self._smart_title(material)}"
        if audience:
            t1 += f" for {self._smart_title(audience)}"
        variants.append(t1)

        t2 = self._smart_title(product)
        if keyword.lower() not in product.lower():
            t2 = f"{self._smart_title(keyword)} | {self._smart_title(product)}"
        variants.append(t2)

        if audience:
            t3 = f"{self._smart_title(keyword)} for {self._smart_title(audience)}"
            if material:
                t3 += f" | {self._smart_title(material)}"
            variants.append(t3)
        else:
            variants.append(f"{self._smart_title(keyword)} | {self._smart_title(product)}")

        t4 = f"{self._smart_title(keyword)} - Quality {self._smart_title(material) if material else 'Design'}"
        variants.append(self._clean_text(t4))

        if extras:
            variants.append(f"{self._smart_title(keyword)} | {self._smart_title(extras[0])}")
        else:
            variants.append(f"{self._smart_title(product)} | {self._smart_title(keyword)}")

        max_len = 140 if platform == "etsy" else 70
        cleaned = []
        seen = set()
        for v in variants:
            v = self._clean_text(v)
            if len(v) > max_len:
                v = v[: max_len - 3].rsplit(" ", 1)[0] + "..."
            key = v.lower()[:50]
            if v and len(v) > 10 and key not in seen:
                cleaned.append(v)
                seen.add(key)

        return cleaned[:5] if cleaned else [self._smart_title(keyword)]

    def generate_description(self, product_name: str, primary_keyword: str = "", features: List[str] = None, category: str = "default", material: str = "", audience: str = "", include_emoji: bool = True) -> str:
        product = product_name.strip()
        keyword = (primary_keyword or product).strip()
        features = [f.strip() for f in (features or []) if f.strip()]
        material = material.strip()
        audience = audience.strip()

        lines = []
        lines.append(f"Introducing the {product}.")
        if keyword.lower() != product.lower():
            lines.append(f'Optimized around the search term "{keyword}".')
        lines.append("")

        if features:
            lines.append("Key details you provided:")
            prefix = "• " if not include_emoji else "✨ "
            for f in features[:8]:
                lines.append(f"{prefix}{f}")
            lines.append("")
        else:
            lines.append("Key details: (none supplied — add specific features before publishing)")
            lines.append("")

        facts = []
        if material:
            facts.append(f"Material / attribute: {material}")
        if audience:
            facts.append(f"Intended for: {audience}")
        if facts:
            lines.append("Additional details:")
            for f in facts:
                lines.append(f"• {f}")
            lines.append("")

        lines.append("Review this draft carefully. Confirm every material, claim, and detail matches your actual product before publishing.")
        lines.append("")
        lines.append("— Generated as a starting draft by ListingForge. Human verification required.")

        description = "\n".join(lines)
        description = re.sub(r"\n{3,}", "\n\n", description).strip()
        return description

    def generate_tags(self, product_name: str, primary_keyword: str = "", category: str = "default", material: str = "", audience: str = "", extra_keywords: List[str] = None, platform: str = "etsy", max_tags: int = 13) -> List[str]:
        product = product_name.lower().strip()
        keyword = (primary_keyword or product).lower().strip()
        material = material.lower().strip()
        audience = audience.lower().strip()
        extra = [k.lower().strip() for k in (extra_keywords or []) if k.strip()]

        candidates = []
        candidates.append(keyword)
        if product != keyword:
            candidates.append(product)

        if material:
            candidates.append(material)
            candidates.append(f"{material} {keyword}".strip())
            candidates.append(f"{keyword} {material}".strip())

        if audience:
            candidates.append(f"{keyword} for {audience}")
            candidates.append(f"gift for {audience}")

        for ek in extra:
            candidates.append(ek)
            if keyword not in ek:
                candidates.append(f"{ek} {keyword}")

        safe = [f"{keyword} gift", f"gift {keyword}", "unique gift", "thoughtful gift"]
        for s in safe:
            candidates.append(s)

        def _fit(tag: str) -> str:
            tag = re.sub(r"\s+", " ", tag).strip()
            tag = re.sub(r"\b(\w+)\s+\1\b", r"\1", tag, flags=re.IGNORECASE)
            if platform == "etsy" and len(tag) > 20:
                tag = tag[:20].rsplit(" ", 1)[0].strip()
            return tag

        cleaned = []
        for tag in candidates:
            tag = _fit(tag)
            if tag and len(tag) >= 3 and tag not in cleaned:
                cleaned.append(tag)

        final = []
        primary_tag = _fit(keyword)
        if primary_tag:
            final.append(primary_tag)

        for t in cleaned:
            if len(final) >= max_tags:
                break
            if t.lower() not in [x.lower() for x in final]:
                final.append(t)

        while len(final) < max_tags:
            pad = _fit(f"{keyword} idea") if keyword else "gift idea"
            if pad and pad.lower() not in [x.lower() for x in final]:
                final.append(pad)
            else:
                break

        return final[:max_tags]

    def validate_output(self, text: str, user_supplied: set) -> List[str]:
        return self._contains_prohibited(text, user_supplied)

    def generate_full_listing(self, product_name: str, primary_keyword: str = "", category: str = "default", material: str = "", audience: str = "", features: List[str] = None, extra_keywords: List[str] = None, platform: str = "etsy", tone: str = "professional", force_template: bool = False) -> Dict:
        features = features or []
        extra_keywords = extra_keywords or []
        user_supplied = self._user_supplied_terms(
            product_name=product_name,
            primary_keyword=primary_keyword,
            material=material,
            audience=audience,
            features=features,
            extra_keywords=extra_keywords,
        )

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
            model = llm_result.get("meta", {}).get("model")
        else:
            titles = self.generate_title(product_name=product_name, primary_keyword=primary_keyword, category=category, audience=audience, material=material, platform=platform, extra_keywords=extra_keywords)
            description = self.generate_description(product_name=product_name, primary_keyword=primary_keyword, features=features, category=category, material=material, audience=audience)
            tags = self.generate_tags(product_name=product_name, primary_keyword=primary_keyword, category=category, material=material, audience=audience, extra_keywords=extra_keywords, platform=platform)
            best_title = titles[0] if titles else product_name
            source = "template"
            model = None

        combined = best_title + " " + description + " " + " ".join(tags)
        warnings = self.validate_output(combined, user_supplied)

        title_score = self.scorer.score_title(best_title, primary_keyword or product_name, platform)
        desc_score = self.scorer.score_description(description, primary_keyword or product_name, extra_keywords)
        tags_score = self.scorer.score_tags(tags, primary_keyword or product_name, platform)
        overall = self.scorer.overall_score(title_score, desc_score, tags_score)

        return {
            "titles": titles,
            "best_title": best_title,
            "description": description,
            "tags": tags,
            "platform": platform,
            "scores": {"title": title_score, "description": desc_score, "tags": tags_score, "overall": overall},
            "meta": {
                "product_name": product_name,
                "primary_keyword": primary_keyword or product_name,
                "category": self._normalize_category(category),
                "material": material,
                "audience": audience,
                "source": source,
                "model": model,
                "is_draft": True,
                "claim_warnings": warnings,
            },
            "disclaimer": (
                "DRAFT ONLY — Verify every material, claim, rating, shipping statement, "
                "and product attribute against your actual product before publishing. "
                "ListingForge does not invent facts; any remaining claims must be confirmed by you."
            ),
        }
