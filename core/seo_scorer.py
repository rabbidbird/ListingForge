"""
ListingForge SEO Scoring Engine
Realistic scoring based on actual Etsy, Shopify, and Google ranking signals
used by professional listing optimizers.
"""

from typing import Dict, List, Tuple
import re
from collections import Counter

class SEOScorer:
    def __init__(self):
        self.weights = {
            "title": 0.30,
            "description": 0.25,
            "tags": 0.20,
            "keywords": 0.15,
            "readability": 0.10,
        }

    def score_title(self, title: str, primary_keyword: str, platform: str = "etsy") -> Dict:
        score = 0
        max_score = 100
        feedback = []

        title_lower = title.lower().strip()
        keyword_lower = primary_keyword.lower().strip() if primary_keyword else ""

        # Length optimization
        length = len(title)
        if platform == "etsy":
            if 60 <= length <= 140:
                score += 25
            elif 40 <= length < 60 or 140 < length <= 160:
                score += 15
                feedback.append("Title length is acceptable but not ideal (aim 60-140 chars for Etsy).")
            else:
                feedback.append("Title length is suboptimal. Etsy prefers 60-140 characters.")
        else:  # shopify / general
            if 40 <= length <= 70:
                score += 25
            elif 30 <= length < 40 or 70 < length <= 90:
                score += 15
            else:
                feedback.append("Title length not optimal for Shopify/Google (aim 40-70 chars).")

        # Keyword presence and position
        if keyword_lower and keyword_lower in title_lower:
            score += 30
            if title_lower.startswith(keyword_lower) or title_lower.find(keyword_lower) < 30:
                score += 15  # Front-loaded keyword bonus
            else:
                feedback.append("Primary keyword is present but not near the front of the title.")
        elif keyword_lower:
            feedback.append("Primary keyword is missing from the title — this is critical.")
            score += 0
        else:
            score += 10  # No keyword provided, partial credit

        # Power words / emotional language
        power_indicators = ["premium", "handmade", "custom", "unique", "best", "luxury", "organic", 
                           "personalized", "limited", "exclusive", "artisan", "gift"]
        power_count = sum(1 for w in power_indicators if w in title_lower)
        if power_count >= 2:
            score += 15
        elif power_count == 1:
            score += 8
        else:
            feedback.append("Consider adding 1-2 strong power words (premium, handmade, custom, etc.).")

        # Avoid keyword stuffing
        words = re.findall(r'\b\w+\b', title_lower)
        if words:
            word_counts = Counter(words)
            max_repeat = max(word_counts.values()) if word_counts else 1
            if max_repeat >= 3:
                score -= 15
                feedback.append("Possible keyword stuffing detected. Avoid repeating the same word 3+ times.")
            else:
                score += 10

        # Special characters / readability
        if re.search(r'[|•–—]', title):
            score += 5  # Good separators

        final = max(0, min(100, score))
        return {
            "score": final,
            "feedback": feedback,
            "length": length,
            "keyword_present": bool(keyword_lower and keyword_lower in title_lower),
        }

    def score_description(self, description: str, primary_keyword: str, secondary_keywords: List[str] = None) -> Dict:
        score = 0
        feedback = []
        secondary_keywords = secondary_keywords or []

        desc_lower = description.lower()
        length = len(description)
        word_count = len(re.findall(r'\b\w+\b', description))

        # Length
        if 400 <= length <= 1800:
            score += 25
        elif 250 <= length < 400 or 1800 < length <= 2500:
            score += 15
            feedback.append("Description length is okay but can be optimized (target 400-1800 characters).")
        else:
            feedback.append("Description is too short or excessively long for optimal engagement.")

        # Keyword usage
        primary = primary_keyword.lower() if primary_keyword else ""
        if primary and primary in desc_lower:
            count = desc_lower.count(primary)
            if 2 <= count <= 6:
                score += 25
            elif count == 1:
                score += 15
                feedback.append("Primary keyword appears only once. Aim for 2-5 natural mentions.")
            else:
                score += 5
                feedback.append("Primary keyword may be overused.")
        elif primary:
            feedback.append("Primary keyword is missing from the description.")

        # Secondary keywords
        secondary_hits = sum(1 for kw in secondary_keywords if kw.lower() in desc_lower)
        if secondary_keywords:
            coverage = secondary_hits / len(secondary_keywords)
            score += int(20 * coverage)
            if coverage < 0.4:
                feedback.append("Few secondary keywords are present. Weave in more related terms naturally.")

        # Structure signals (bullet points, paragraphs, emojis that improve scannability)
        has_bullets = bool(re.search(r'[•\-\*]|^\d+\.', description, re.MULTILINE))
        has_paragraphs = description.count('\n\n') >= 1 or description.count('\n') >= 3
        if has_bullets:
            score += 10
        if has_paragraphs:
            score += 10
        if not has_bullets and not has_paragraphs:
            feedback.append("Add bullet points or clear paragraph breaks for better readability.")

        # Call to action
        cta_phrases = ["add to cart", "order now", "buy now", "shop now", "get yours", "limited", "ships"]
        if any(p in desc_lower for p in cta_phrases):
            score += 10
        else:
            feedback.append("Consider adding a clear call-to-action near the end.")

        final = max(0, min(100, score))
        return {
            "score": final,
            "feedback": feedback,
            "length": length,
            "word_count": word_count,
            "primary_keyword_count": desc_lower.count(primary) if primary else 0,
        }

    def score_tags(self, tags: List[str], primary_keyword: str, platform: str = "etsy") -> Dict:
        score = 0
        feedback = []
        tags = [t.strip().lower() for t in tags if t.strip()]

        if platform == "etsy":
            ideal_count = 13
            if len(tags) == 13:
                score += 30
            elif 10 <= len(tags) <= 13:
                score += 20
            else:
                feedback.append(f"Etsy allows up to 13 tags. You have {len(tags)}. Fill all slots.")
        else:
            if 5 <= len(tags) <= 15:
                score += 25
            else:
                feedback.append("Aim for 8-12 strong tags.")

        # Diversity and long-tail
        avg_length = sum(len(t) for t in tags) / max(len(tags), 1)
        if avg_length >= 12:
            score += 20  # Long-tail preference
        elif avg_length >= 8:
            score += 12
        else:
            feedback.append("Many tags are very short. Long-tail tags (3+ words) usually convert better.")

        # Primary keyword in tags
        primary = primary_keyword.lower() if primary_keyword else ""
        if primary and any(primary in t for t in tags):
            score += 20
        elif primary:
            feedback.append("Primary keyword (or close variation) should appear in at least one tag.")

        # Uniqueness
        if len(tags) == len(set(tags)):
            score += 15
        else:
            feedback.append("Duplicate tags detected. Remove duplicates.")

        # Character limits (Etsy 20 chars)
        over_limit = [t for t in tags if len(t) > 20]
        if over_limit and platform == "etsy":
            score -= 10
            feedback.append(f"{len(over_limit)} tag(s) exceed Etsy's 20-character limit.")

        final = max(0, min(100, score))
        return {
            "score": final,
            "feedback": feedback,
            "count": len(tags),
            "avg_length": round(avg_length, 1),
        }

    def overall_score(self, title_result: Dict, desc_result: Dict, tags_result: Dict) -> Dict:
        overall = (
            title_result["score"] * self.weights["title"] +
            desc_result["score"] * self.weights["description"] +
            tags_result["score"] * self.weights["tags"]
        )
        # Simple keyword + readability bonus already partially included
        overall = min(100, overall + 5)  # small base

        grade = "A+" if overall >= 90 else "A" if overall >= 80 else "B+" if overall >= 70 else "B" if overall >= 60 else "C" if overall >= 50 else "D"

        all_feedback = title_result["feedback"] + desc_result["feedback"] + tags_result["feedback"]

        return {
            "overall": round(overall, 1),
            "grade": grade,
            "title_score": title_result["score"],
            "description_score": desc_result["score"],
            "tags_score": tags_result["score"],
            "feedback": all_feedback,
            "summary": self._generate_summary(overall, grade),
        }

    def _generate_summary(self, score: float, grade: str) -> str:
        if score >= 85:
            return "Excellent listing. Strong SEO signals and conversion-focused copy. Ready to publish."
        elif score >= 70:
            return "Solid listing with good foundations. Address the feedback items to push into top-tier performance."
        elif score >= 55:
            return "Average listing. Significant improvements available in keyword usage, structure, and emotional language."
        else:
            return "Needs major work. Focus first on title keyword placement, description length/structure, and filling all tag slots."
