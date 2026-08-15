"""
Optional real LLM backend for ListingForge.
Supports OpenAI-compatible APIs (OpenAI, Grok/xAI, Anthropic via proxy, local, etc.)
Activated only when OPENAI_API_KEY (or compatible) is set in environment / secrets.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any

# Optional import – app still works without the package
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def is_llm_available() -> bool:
    """Return True if a usable API key is present and the openai package is installed."""
    key = os.getenv("OPENAI_API_KEY") or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
    return bool(key) and HAS_OPENAI


def get_client():
    """Create an OpenAI-compatible client. Supports xAI/Grok by changing base_url."""
    if not HAS_OPENAI:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
    if not api_key:
        raise RuntimeError("No API key found. Set OPENAI_API_KEY or XAI_API_KEY")

    # Default to OpenAI; switch to xAI if XAI/GROK key is used
    base_url = None
    if os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY") or "xai" in (os.getenv("OPENAI_BASE_URL") or "").lower():
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.x.ai/v1")
    elif os.getenv("OPENAI_BASE_URL"):
        base_url = os.getenv("OPENAI_BASE_URL")

    return OpenAI(api_key=api_key, base_url=base_url)


SYSTEM_PROMPT = """You are an expert e-commerce copywriter and SEO specialist who creates high-converting product listings for Etsy, Shopify, and Amazon.

Rules:
- Write natural, benefit-focused, emotionally engaging copy.
- Front-load primary keywords in titles.
- Never keyword stuff.
- Use power words and sensory language appropriate to the category.
- Descriptions should follow: Hook → Features/Benefits → Social proof / Why choose → Perfect for → Details → Clear CTA.
- For Etsy tags: exactly 13 tags, each ≤20 characters, prefer long-tail, include material, audience, occasion where relevant.
- Return ONLY valid JSON with the exact keys requested. No markdown, no explanation.
"""


def generate_with_llm(
    product_name: str,
    primary_keyword: str = "",
    category: str = "default",
    material: str = "",
    audience: str = "",
    features: List[str] = None,
    extra_keywords: List[str] = None,
    platform: str = "etsy",
    model: str = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate a full listing using a real LLM.
    Returns the same structure as ListingGenerator.generate_full_listing or None on failure.
    """
    if not is_llm_available():
        return None

    features = features or []
    extra_keywords = extra_keywords or []
    model = model or os.getenv("LISTINGFORGE_MODEL", "gpt-4o-mini")

    # For xAI/Grok default to a sensible model if not set
    if "x.ai" in (os.getenv("OPENAI_BASE_URL") or "") or os.getenv("XAI_API_KEY"):
        model = model if model != "gpt-4o-mini" else "grok-3"

    user_prompt = f"""Create an optimized product listing.

Product name: {product_name}
Primary keyword: {primary_keyword or product_name}
Category: {category}
Material / key attribute: {material or "not specified"}
Target audience: {audience or "general"}
Key features: {', '.join(features) if features else "not specified"}
Extra keywords: {', '.join(extra_keywords) if extra_keywords else "none"}
Platform: {platform}

Return a JSON object with exactly these keys:
{{
  "titles": ["title1", "title2", "title3", "title4", "title5"],
  "best_title": "the single best title",
  "description": "full multi-paragraph description with line breaks as \\n",
  "tags": ["tag1", "tag2", ... ]  // exactly 13 for etsy, 8-12 for others, each <=20 chars for etsy
}}
"""

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1800,
            response_format={"type": "json_object"} if "gpt" in model or "grok" in model else None,
        )
        content = response.choices[0].message.content.strip()
        # Clean possible markdown fences
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        data = json.loads(content)

        # Minimal validation
        if not data.get("best_title") or not data.get("description") or not data.get("tags"):
            return None

        # Ensure tags list
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        tags = [t.strip()[:20] if platform == "etsy" else t.strip() for t in tags if t.strip()]
        if platform == "etsy":
            tags = tags[:13]
            while len(tags) < 13:
                tags.append(f"{(primary_keyword or product_name)} gift"[:20])

        return {
            "titles": data.get("titles", [data["best_title"]])[:5],
            "best_title": data["best_title"],
            "description": data["description"].replace("\\n", "\n"),
            "tags": tags,
            "platform": platform,
            "meta": {
                "product_name": product_name,
                "primary_keyword": primary_keyword or product_name,
                "category": category,
                "material": material,
                "audience": audience,
                "source": "llm",
                "model": model,
            },
        }
    except Exception as e:
        print(f"[ListingForge LLM] Error: {e}")
        return None
