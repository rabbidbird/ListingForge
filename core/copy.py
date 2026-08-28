"""Public product copy and trust strings.

This is the single source for landing, pricing, and disclaimer language so
user-visible pages cannot drift into false claims or mixed naming.
"""

from __future__ import annotations

from .plans import PLANS

PRODUCT_NAME = "SellerDrafts"
TAGLINE = "Fact-locked product listing drafts from facts you supply"
PROMISE = (
    "Etsy sellers can turn verified product facts into a structured title, description, and tags. "
    "SellerDrafts uses only what you enter, so missing attributes stay missing."
)
HERO_SUPPORT = (
    "Turn verified product facts into an Etsy title, description, and tags; Shopify and "
    "Amazon-style drafts are available too. SellerDrafts uses only what you enter, leaves "
    "missing attributes missing, and never publishes for you."
)
DRAFT_BANNER = (
    "DRAFT — verify before publishing. Confirm every material, claim, rating, "
    "shipping statement, and product attribute against the actual product."
)
HEURISTIC_NOTICE = (
    "Checklist statuses are transparent heuristics only. They do not predict search "
    "ranking, conversion, or sales. Marketplace rules can change."
)
EXPORT_REMINDER = (
    "Copied or downloaded text is still a draft. Verify every claim before you publish."
)
COPY_SUCCESS = "Copied — still a draft"
AUTH_PROMISE = (
    "Fact-locked drafts from facts you supply. SellerDrafts does not publish to "
    "marketplaces or promise ranking."
)
FOOTER_CAPTION = (
    "SellerDrafts v1 · Output is always a starting draft · See Legal for Terms and Privacy"
)

POSITIONING = (
    (
        "Not an autopublisher",
        "You export a draft and publish it yourself. SellerDrafts never sends listings "
        "to Etsy, Shopify, or Amazon.",
    ),
    (
        "Not a ranking promise",
        "Checklist statuses describe visible structure only. They do not guarantee "
        "search placement, clicks, or sales.",
    ),
    (
        "Not unlimited",
        "Every plan has documented daily, monthly, and bulk caps. Limits are enforced "
        "per account. LLM-assisted generation is unavailable at launch.",
    ),
)

HOW_IT_WORKS = (
    (
        "1. Supply facts",
        "Enter the product name and only attributes you can verify — material, "
        "audience, details, and phrases you actually want used.",
    ),
    (
        "2. Generate a draft",
        "SellerDrafts rearranges supplied wording into a title draft, description, and tags. "
        "It will not invent a metal, certification, origin, or shipping claim.",
    ),
    (
        "3. Review and edit",
        "Read the draft against the physical product and current marketplace rules. "
        "The checklist is a structure aid, not a compliance certificate.",
    ),
    (
        "4. Export when ready",
        "Downloads stay locked behind a three-point confirmation. You remain "
        "responsible for what you publish.",
    ),
)

FEATURES = (
    (
        "Single draft",
        "One product at a time, with a title draft, description, tags, and a "
        "transparent checklist.",
    ),
    (
        "Bulk CSV",
        "Upload a UTF-8 CSV. Invalid rows are reported; each successful row uses "
        "one generation against your plan cap.",
    ),
    (
        "Listing checklist",
        "Paste existing listing text to review structure. It cannot judge truth or "
        "marketplace eligibility.",
    ),
    (
        "Private history",
        "Saved drafts are keyed to your account and authorized on every read, "
        "update, delete, and export.",
    ),
    (
        "Honest plans",
        "Free, Starter, Pro, and Agency raise documented quotas only. No plan is "
        "marketed as unlimited.",
    ),
)

TRUST_POINTS = (
    (
        "No silent product facts",
        "Materials, construction, ratings, certifications, shipping claims, and "
        "social proof must come from your input.",
    ),
    (
        "One account, one history",
        "Listings and usage are keyed to your immutable user ID. Other accounts "
        "cannot read your drafts.",
    ),
    (
        "Review stays mandatory",
        "Exports remain behind a confirmation checklist. SellerDrafts does not publish "
        "to a marketplace for you.",
    ),
    (
        "Limits are real",
        "Daily and monthly generation caps, bulk-row caps, and rate limits are "
        "enforced in the database. Failed generations do not consume a credit.",
    ),
)

CLAIM_CATEGORIES = (
    (
        "Materials and metals",
        "gold, sterling, silver, brass, leather, cotton, silk, wood, wool, and similar substances",
    ),
    (
        "Certifications and ethics",
        "organic, certified, fair trade, ethically sourced, sustainable, eco-friendly, vegan, cruelty-free",
    ),
    (
        "Health and safety",
        "nickel-free, lead-free, hypoallergenic, food-safe, non-toxic, medical-grade",
    ),
    (
        "Origin and process",
        "handmade, handcrafted, locally made, small-batch, made in, artisan",
    ),
    (
        "Shipping and policy",
        "free shipping, fast shipping, free returns, instant download, lifetime warranty",
    ),
    (
        "Social proof and scarcity",
        "bestseller, five-star, top-rated, limited stock, selling fast, only a few left",
    ),
)


def audit_unverified_claims(
    listing_text: str, verified_source_text: str = ""
) -> list[dict[str, str]]:
    """Compatibility wrapper around the shared polarity-aware claim audit."""

    from .claims import audit_unverified_claims as shared_audit

    return shared_audit(listing_text, verified_source_text)


PLAN_BLURBS = {
    "free": "Same generator. Documented Free caps so you can try a real draft.",
    "starter": "Higher daily and monthly caps for regular single-item listing work.",
    "pro": "More drafts per day and larger CSV jobs for higher listing volume.",
    "agency": "Highest documented caps. Every draft still requires human review.",
}

# Phrases that must never appear as marketing claims on public pages.
FORBIDDEN_PUBLIC_CLAIMS = (
    "testimonial",
    "customers love",
    "join 10,000",
    "join 1000",
    "as seen on",
    "official partner",
    "etsy partner",
    "shopify partner",
    "amazon partner",
    "we publish to",
    "we autopublish",
    "auto-publish your",
    "guaranteed ranking",
    "guaranteed sales",
    "guaranteed #1",
    "unlimited drafts",
    "unlimited generations",
    "loved by sellers",
    "#1 listing tool",
    "will rank on etsy",
    "will rank on amazon",
)


def plan_limit_lines(plan_key: str) -> list[str]:
    policy = PLANS[plan_key]
    return [
        f"{policy.daily_generations:,} drafts / UTC day",
        f"{policy.monthly_generations:,} drafts / UTC month",
        f"{policy.bulk_rows_per_job:,} rows / bulk job",
        "LLM-assisted generation unavailable at launch",
    ]


def public_text_blob(*parts: str) -> str:
    return "\n".join(parts).lower()


def forbidden_claims_in(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in FORBIDDEN_PUBLIC_CLAIMS if phrase in lowered]
