"""
ListingForge - High-performance copy templates, power words, and category intelligence.
These are carefully curated patterns used by top Etsy/Shopify sellers and conversion copywriters.
"""

from typing import Dict, List

# Power words by emotional trigger / intent
POWER_WORDS = {
    "urgency": ["Limited", "Exclusive", "Only a few left", "Selling fast", "While supplies last", "Hot seller", "Trending now"],
    "quality": ["Premium", "Handcrafted", "Artisan", "Luxury", "Professional-grade", "Museum-quality", "Heirloom", "Boutique"],
    "benefit": ["Effortless", "Time-saving", "Transform your", "Elevate", "Instant", "All-day comfort", "Worry-free", "Results-driven"],
    "emotion": ["Heartwarming", "Joyful", "Serene", "Empowering", "Cozy", "Inspiring", "Romantic", "Nostalgic"],
    "social_proof": ["Bestseller", "Customer favorite", "5-star rated", "Viral", "Editor's pick", "As seen on", "Top-rated"],
    "sensory": ["Soft", "Luxurious", "Crisp", "Vibrant", "Aromatic", "Smooth", "Rich", "Delicate"],
}

# Category-specific language banks
CATEGORY_LANGUAGE: Dict[str, Dict] = {
    "jewelry": {
        "materials": ["sterling silver", "14k gold filled", "solid gold", "rose gold", "gemstone", "pearl", "diamond accent"],
        "benefits": ["hypoallergenic", "tarnish-resistant", "everyday elegant", "statement piece", "layerable", "gift-ready"],
        "emotions": ["timeless", "romantic", "empowered", "celebratory", "meaningful"],
        "occasions": ["anniversary", "birthday", "bridal", "mother's day", "self-love gift"],
    },
    "home_decor": {
        "materials": ["sustainable wood", "ceramic", "linen", "brass", "rattan", "marble", "recycled glass"],
        "benefits": ["instant ambiance", "conversation starter", "space-transforming", "minimalist", "boho chic", "farmhouse"],
        "emotions": ["cozy", "serene", "elevated", "welcoming", "inspired"],
        "occasions": ["housewarming", "new home", "seasonal refresh", "holiday hosting"],
    },
    "apparel": {
        "materials": ["organic cotton", "bamboo", "merino wool", "linen blend", "recycled polyester", "silk"],
        "benefits": ["all-day comfort", "breathable", "wrinkle-resistant", "flattering fit", "versatile styling", "travel-friendly"],
        "emotions": ["confident", "effortless", "empowered", "relaxed", "polished"],
        "occasions": ["everyday essential", "work-from-home", "weekend adventure", "date night"],
    },
    "art_prints": {
        "materials": ["museum-quality paper", "giclée print", "archival ink", "canvas", "matte finish", "gallery wrapped"],
        "benefits": ["fade-resistant", "ready to frame", "statement wall art", "gallery-worthy", "affordable original"],
        "emotions": ["inspiring", "calming", "bold", "nostalgic", "modern"],
        "occasions": ["gallery wall", "office inspiration", "nursery", "gift for art lover"],
    },
    "beauty": {
        "materials": ["clean ingredients", "organic", "vegan", "cruelty-free", "natural botanicals", "clinical-grade"],
        "benefits": ["glow-enhancing", "long-lasting", "sensitive-skin friendly", "results you can see", "multi-benefit"],
        "emotions": ["radiant", "confident", "self-care", "pampered", "fresh"],
        "occasions": ["self-care ritual", "gift set", "travel essentials", "daily routine"],
    },
    "digital": {
        "materials": ["instant download", "high-resolution", "print-ready", "editable template", "commercial use"],
        "benefits": ["ready in seconds", "unlimited prints", "customize yourself", "professional results", "budget-friendly"],
        "emotions": ["empowered", "creative", "organized", "inspired", "productive"],
        "occasions": ["wedding planning", "small business", "content creation", "home organization"],
    },
    "default": {
        "materials": ["premium quality", "carefully selected", "durable", "thoughtfully designed"],
        "benefits": ["everyday essential", "thoughtful gift", "long-lasting", "versatile", "high-value"],
        "emotions": ["delighted", "satisfied", "proud", "happy"],
        "occasions": ["perfect gift", "treat yourself", "special occasion"],
    },
}

# Proven title structures (Etsy/Shopify conversion patterns)
TITLE_STRUCTURES = [
    "{power} {product} - {benefit} | {material} {audience}",
    "{product} for {audience} | {benefit} {power}",
    "{power} {material} {product} - Perfect for {occasion}",
    "{benefit} {product} | {emotion} Gift for {audience}",
    "{product} - {power} {material} | {benefit}",
    "Handmade {product} | {benefit} & {emotion} Design",
    "{audience}'s Favorite {product} - {power} Quality",
]

# Description section templates
DESCRIPTION_SECTIONS = {
    "hook": [
        "Discover the {product} that {benefit_phrase}.",
        "Meet your new favorite {product} — designed to {benefit_phrase}.",
        "Elevate your everyday with this {power} {product}.",
        "Looking for a {product} that actually delivers? This is it.",
    ],
    "features": [
        "✨ {feature1}\n✨ {feature2}\n✨ {feature3}",
        "• {feature1}\n• {feature2}\n• {feature3}\n• {feature4}",
    ],
    "why_choose": [
        "Why sellers and customers love this:\n{reasons}",
        "What makes this special:\n{reasons}",
    ],
    "perfect_for": [
        "Perfect for:\n{occasions}",
        "Ideal gift for:\n{occasions}",
    ],
    "details": [
        "Product details:\n{details}",
        "Specifications:\n{details}",
    ],
    "cta": [
        "Add to cart now and experience the difference.",
        "Ready to elevate your collection? Order today.",
        "Limited stock — secure yours before it’s gone.",
        "Treat yourself or someone special. Ships fast.",
    ],
}

# Etsy-optimized tag strategies
ETSY_TAG_STRATEGIES = {
    "long_tail": True,
    "max_tags": 13,
    "max_chars_per_tag": 20,
    "include_material": True,
    "include_audience": True,
    "include_occasion": True,
    "include_style": True,
}

# Shopify / general SEO patterns
SHOPIFY_TITLE_MAX = 70
ETSY_TITLE_MAX = 140
DESCRIPTION_TARGET_MIN = 300
DESCRIPTION_TARGET_MAX = 2000
