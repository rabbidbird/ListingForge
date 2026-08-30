"""Server-rendered public pages for crawlability and trustworthy product discovery."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass

from .config import get_settings
from .copy import PLAN_BLURBS, PRODUCT_NAME, plan_limit_lines
from .generator import ListingGenerator
from .legal import (
    ACCEPTABLE_USE_MARKDOWN,
    CONTACT_EMAIL,
    OPERATOR_NAME,
    PRIVACY_MARKDOWN,
    TERMS_MARKDOWN,
    markdown_to_safe_html,
)
from .plans import PLANS

PUBLIC_PATHS = (
    "/",
    "/pricing",
    "/legal",
    "/guides",
    "/guides/etsy-listing-draft-checklist",
    "/guides/write-etsy-listings-without-inventing-facts",
    "/guides/etsy-title-description-and-tags-checklist",
)


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    description: str
    eyebrow: str
    body: str


GUIDES = {
    guide.slug: guide
    for guide in (
        Guide(
            slug="etsy-listing-draft-checklist",
            title="Etsy listing draft checklist before you publish",
            description=(
                "A practical Etsy listing checklist for reviewing product facts, titles, "
                "descriptions, tags, photos, policies, and buyer-facing claims."
            ),
            eyebrow="Etsy seller checklist",
            body="""
<p class="lede">A draft is useful only when it helps you notice what still needs verification. Work through this checklist against the physical product and your current shop policies before publishing.</p>
<div class="draft-warning"><strong>DRAFT — verify before publishing.</strong> A checklist cannot establish that a claim is true or that an item is eligible for a marketplace.</div>
<h2>1. Confirm the item itself</h2>
<ul class="checklist">
  <li>Name the item plainly so a buyer can tell what is being sold.</li>
  <li>Verify every stated material, component, measurement, color, variation, and included item.</li>
  <li>Remove any certification, safety, health, origin, or process claim you cannot document.</li>
  <li>Do not add “handmade,” “organic,” “hypoallergenic,” or similar claims just to make the copy sound complete.</li>
</ul>
<h2>2. Review the title and search language</h2>
<ul class="checklist">
  <li>Lead with a clear item name and the most useful verified traits.</li>
  <li>Keep the title readable instead of repeating near-identical keywords.</li>
  <li>Use only occasions, recipients, or styles that actually apply to the product.</li>
</ul>
<h2>3. Review the description</h2>
<ul class="checklist">
  <li>Explain what the buyer receives before adding background or promotional language.</li>
  <li>Check size, personalization, care, processing, shipping, and digital-delivery wording against the real offer.</li>
  <li>Make sure photos and variations do not contradict the written description.</li>
</ul>
<h2>4. Check marketplace and shop details</h2>
<ul class="checklist">
  <li>Use the most specific accurate category and attributes available in Etsy.</li>
  <li>Review intellectual-property, prohibited-item, labeling, and disclosure obligations.</li>
  <li>Confirm your current Etsy settings and policies directly before publishing.</li>
</ul>
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Sources: <a href="https://help.etsy.com/hc/en-us/articles/115015628707-How-to-Create-a-Listing">Etsy Help: Create a listing</a> and <a href="https://help.etsy.com/hc/en-gb/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search">Etsy Help: Tags</a>. Marketplace guidance can change; SellerDrafts is not affiliated with Etsy.</p>
""",
        ),
        Guide(
            slug="write-etsy-listings-without-inventing-facts",
            title="How to write an Etsy listing without inventing product facts",
            description=(
                "A fact-first method for drafting Etsy titles, descriptions, and tags without "
                "adding unsupported materials, claims, shipping promises, or social proof."
            ),
            eyebrow="Fact-first Etsy drafting",
            body="""
<p class="lede">Good listing copy can be specific without guessing. The safest workflow is to separate what you know about the product from language you merely wish were true.</p>
<div class="draft-warning"><strong>DRAFT — verify before publishing.</strong> You remain responsible for every claim placed in a marketplace listing.</div>
<h2>Start with a fact inventory</h2>
<p>Before writing, list only details you can verify: the item name, materials, measurements, colors, variations, included pieces, care information, personalization choices, and relevant search phrases. Leave unknown fields blank.</p>
<h2>Turn facts into structure, not new facts</h2>
<p>A title can combine the item name with verified traits. A description can arrange the same information into a clear opening, details, and buyer instructions. Tags can reuse accurate concepts in concise phrases. None of those steps requires inventing a material, manufacturing process, certification, audience, occasion, rating, or shipping promise.</p>
<h2>Watch for claims that sound harmless</h2>
<p>Words such as “handmade,” “sustainable,” “nickel-free,” “bestseller,” and “fast shipping” communicate factual promises. Use them only when they came from your records and apply to the exact product and offer.</p>
<h2>Use missing information as a review signal</h2>
<p>An incomplete draft is safer than confident misinformation. If a buyer needs a missing measurement or material, stop and verify it. SellerDrafts deliberately leaves missing attributes missing so the gap remains visible during review.</p>
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Start with <a href="https://help.etsy.com/hc/en-us/articles/115015628707-How-to-Create-a-Listing">Etsy Help: Create a listing</a>, then check the current rules and category requirements for your exact item.</p>
""",
        ),
        Guide(
            slug="etsy-title-description-and-tags-checklist",
            title="Etsy title, description, and tags checklist",
            description=(
                "Review an Etsy title, description, and tags for clarity, accurate product "
                "details, readable search phrases, and current marketplace constraints."
            ),
            eyebrow="Listing structure",
            body="""
<p class="lede">Etsy looks at more than one field when matching listings. Treat the title, tags, description, category, attributes, photos, and shop record as one accurate representation of the item.</p>
<div class="draft-warning"><strong>DRAFT — verify before publishing.</strong> Structure checks do not predict search placement, conversion, or sales.</div>
<h2>Title</h2>
<ul class="checklist">
  <li>State the item clearly and once.</li>
  <li>Place the most useful verified traits near the beginning.</li>
  <li>Prefer readable wording over repeated keyword strings.</li>
  <li>Do not add materials, sizes, recipients, or occasions that were not supplied.</li>
</ul>
<h2>Description</h2>
<ul class="checklist">
  <li>Open with what the buyer is getting.</li>
  <li>Group verified details so they are easy to scan.</li>
  <li>Call out information that still needs confirmation instead of filling the gap with a guess.</li>
  <li>Compare all claims with photos, variations, processing settings, and shop policies.</li>
</ul>
<h2>Tags and attributes</h2>
<ul class="checklist">
  <li>Etsy currently permits up to 13 tags, with up to 20 characters per tag.</li>
  <li>Use relevant multi-word phrases and avoid wasting several tags on the same wording.</li>
  <li>Select accurate categories and attributes; they also help Etsy understand the listing.</li>
  <li>Re-check limits in Etsy before publishing because marketplace rules change.</li>
</ul>
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Sources: <a href="https://help.etsy.com/hc/en-us/articles/115015628707-How-to-Create-a-Listing">Etsy Help: Create a listing</a> and <a href="https://help.etsy.com/hc/en-gb/articles/360000336307-How-to-Use-Tags-to-Get-Found-in-Search">Etsy Help: Tags</a>. SellerDrafts is not affiliated with Etsy.</p>
""",
        ),
    )
}


def _url(path: str) -> str:
    return f"{get_settings().public_base_url}{path}"


def _schema_json(nodes: list[dict[str, object]]) -> str:
    payload = json.dumps({"@context": "https://schema.org", "@graph": nodes}, ensure_ascii=False)
    return payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _page(
    *,
    title: str,
    description: str,
    canonical_path: str,
    body: str,
    schema_nodes: list[dict[str, object]],
) -> str:
    canonical = _url(canonical_path)
    full_title = f"{title} | {PRODUCT_NAME}" if title != PRODUCT_NAME else title
    safe_title = html.escape(full_title)
    safe_description = html.escape(description, quote=True)
    safe_canonical = html.escape(canonical, quote=True)
    schema = _schema_json(schema_nodes)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title>
<meta name="description" content="{safe_description}">
<link rel="canonical" href="{safe_canonical}">
<meta property="og:type" content="website"><meta property="og:site_name" content="SellerDrafts">
<meta property="og:title" content="{safe_title}"><meta property="og:description" content="{safe_description}">
<meta property="og:url" content="{safe_canonical}"><meta property="og:image" content="{html.escape(_url("/assets/og.png"), quote=True)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_description}"><meta name="twitter:image" content="{html.escape(_url("/assets/og.png"), quote=True)}">
<link rel="icon" href="/assets/favicon.ico" sizes="any">
<link rel="stylesheet" href="/assets/public.css">
<style>pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media(max-width:600px){{.site-header .wordmark b{{display:none}}.site-header nav{{gap:.5rem}}.nav-links{{gap:.55rem}}.nav-links a:first-child{{display:inline}}.nav-links a:nth-child(3){{display:none}}}}</style>
<script type="application/ld+json">{schema}</script>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><nav aria-label="SellerDrafts">
<a class="wordmark" href="/" aria-label="SellerDrafts home"><span>S</span><b>SellerDrafts</b></a>
<div class="nav-links"><a href="/pricing">Plans</a><a href="/guides">Guides</a><a href="/legal">Legal</a><a class="signin" href="/auth/login">Sign in</a></div>
</nav></header>
<main id="main">{body}</main>
<footer><div><a class="wordmark footer-mark" href="/"><span>S</span>SellerDrafts</a><p>Fact-locked starting drafts from facts you supply.</p></div><nav aria-label="Footer"><a href="/guides">Guides</a><a href="/pricing">Plans</a><a href="/legal">Legal</a><a href="/auth/signup">Create a free Etsy draft</a></nav><p class="fine-print">SellerDrafts is operated by Johnson Solutions LLC and is not affiliated with Etsy, Shopify, or Amazon.</p></footer>
</body></html>"""


def home_page() -> str:
    description = (
        "Create a free Etsy draft from product facts you supply. Generate a title, description, "
        "and tags without invented materials, claims, ratings, or shipping promises."
    )
    example = ListingGenerator(use_llm=False).generate_full_listing(
        product_name="Pressed flower teardrop pendant necklace",
        primary_keyword="pressed flower necklace",
        category="jewelry",
        item_noun="pendant necklace",
        color="blue and white",
        material="stainless steel chain",
        size="18-inch chain",
        features=["Pendant: 1.25 inches"],
        platform="etsy",
        force_template=True,
    )
    example_tags = ", ".join(example["tags"])
    example_reviews = example["scores"]["overall"].get("feedback") or [
        "No structural warning in this fixture; the seller must still verify every fact."
    ]
    review_items = "".join(f"<li>{html.escape(item)}</li>" for item in example_reviews)
    body = f"""
<section class="hero hero-proof">
  <div class="hero-copy"><p class="eyebrow">Etsy-first listing workflow</p>
  <h1>Turn your real product details into Etsy copy you can review in minutes.</h1>
  <p class="lede">Get an editable title, description, and tags from facts you supply. Missing materials, shipping promises, and claims stay out.</p>
  <div class="draft-warning compact"><strong>Draft only:</strong> verify every claim before publishing.</div>
  <div class="actions"><a class="button primary" href="/auth/signup">Create a free Etsy draft — no card</a><a class="button secondary" href="#example">See the example</a></div>
  <p class="pilot-note">Free account creation uses Google. Existing password accounts can still sign in.</p></div>
  <aside class="hero-example" aria-label="Example of supplied jewelry facts becoming a draft"><p class="step">SUPPLIED FACTS</p><dl class="source-map"><div><dt>Product</dt><dd>Pressed flower teardrop pendant necklace</dd></div><div><dt>Material</dt><dd>stainless steel chain</dd></div><div><dt>Size</dt><dd>18-inch chain</dd></div><div><dt>Detail</dt><dd>Pendant: 1.25 inches</dd></div><div><dt>Handmade claim</dt><dd>not supplied → not included</dd></div></dl><p class="step">EDITABLE DRAFT</p><p class="example-title">{html.escape(example["best_title"])}</p><p class="example-tags"><strong>Tags:</strong> {html.escape(example_tags)}</p></aside>
</section>
<section><p class="eyebrow">How it works</p><h2>Structure the facts. Keep control of the listing.</h2>
<div class="card-grid three"><article><span class="step">01</span><h3>Supply facts</h3><p>Enter the item name and only details you can verify.</p></article><article><span class="step">02</span><h3>Generate a draft</h3><p>SellerDrafts arranges supplied wording into marketplace-style fields.</p></article><article><span class="step">03</span><h3>Review before publishing</h3><p>Compare every claim with the real product and current marketplace rules.</p></article></div></section>
<section class="split"><div><p class="eyebrow">Honesty is the feature</p><h2>No silent product facts</h2><p>Materials, certifications, origin, ratings, scarcity, and shipping promises appear only when you supply them. An incomplete draft is safer than confident misinformation.</p></div><div class="panel"><h3>What every draft includes</h3><ul><li>A title built from supplied wording</li><li>A structured description and tags</li><li>A transparent heuristic checklist</li><li>A visible verification warning</li><li>Private account history</li></ul></div></section>
<section id="example"><p class="eyebrow">Generated example</p><h2>Supplied facts become editable fields—nothing extra.</h2><div class="panel example-panel"><div><h3>Facts supplied</h3><dl class="source-map"><div><dt>Product</dt><dd>Pressed flower teardrop pendant necklace</dd></div><div><dt>Primary phrase</dt><dd>pressed flower necklace</dd></div><div><dt>Color</dt><dd>blue and white</dd></div><div><dt>Material</dt><dd>stainless steel chain</dd></div><div><dt>Size</dt><dd>18-inch chain</dd></div><div><dt>Verified detail</dt><dd>Pendant: 1.25 inches</dd></div><div><dt>Shipping promise</dt><dd>not supplied → not included</dd></div><div><dt>Handmade claim</dt><dd>not supplied → not included</dd></div></dl></div><div><h3>Generated draft</h3><p><strong>Title</strong></p><p>{html.escape(example["best_title"])}</p><p><strong>Description</strong></p><pre>{html.escape(example["description"])}</pre><p><strong>Tags</strong></p><p>{html.escape(example_tags)}</p></div></div><div class="panel review-panel"><h3>Review items</h3><ul>{review_items}</ul><p class="fine-print">This fixture is rendered by the deterministic generator from only the facts shown above. It is not a real listing or a performance claim.</p></div></section>
<section><p class="eyebrow">Learn before you publish</p><h2>Practical Etsy listing guides</h2><div class="card-grid three">
<a class="guide-card" href="/guides/etsy-listing-draft-checklist"><h3>Draft checklist</h3><p>Review facts, claims, photos, and shop settings.</p><span>Read guide →</span></a>
<a class="guide-card" href="/guides/write-etsy-listings-without-inventing-facts"><h3>Write without guessing</h3><p>Turn verified details into structure without adding promises.</p><span>Read guide →</span></a>
<a class="guide-card" href="/guides/etsy-title-description-and-tags-checklist"><h3>Title, description, and tags</h3><p>Check clarity, accurate details, and current constraints.</p><span>Read guide →</span></a>
</div></section>
<section class="closing"><p class="eyebrow">Start Free</p><h2>Create one careful draft before choosing a plan.</h2><p>Free includes 8 drafts per UTC day and 40 per UTC month. Every plan uses the same fact-locked template generator.</p><div class="actions center"><a class="button primary" href="/auth/signup">Create a free Etsy draft</a><a class="text-link" href="/pricing">Compare plans</a></div></section>
"""
    base = get_settings().public_base_url
    return _page(
        title="Etsy Listing Draft Generator",
        description=description,
        canonical_path="/",
        body=body,
        schema_nodes=[
            {
                "@type": "WebSite",
                "@id": f"{base}/#website",
                "name": PRODUCT_NAME,
                "url": f"{base}/",
            },
            {
                "@type": "Organization",
                "@id": f"{base}/#organization",
                "name": "Johnson Solutions LLC",
                "alternateName": PRODUCT_NAME,
                "url": f"{base}/",
                "email": CONTACT_EMAIL,
            },
            {
                "@type": "SoftwareApplication",
                "@id": f"{base}/#application",
                "name": PRODUCT_NAME,
                "applicationCategory": "BusinessApplication",
                "operatingSystem": "Web",
                "url": f"{base}/",
                "description": description,
                "offers": [
                    {
                        "@type": "Offer",
                        "name": PLANS[key].name,
                        "price": {"free": "0", "starter": "12", "pro": "29", "agency": "79"}[key],
                        "priceCurrency": "USD",
                    }
                    for key in ("free", "starter", "pro", "agency")
                ],
            },
        ],
    )


def pricing_page() -> str:
    cards: list[str] = []
    for key in ("free", "starter", "pro", "agency"):
        plan = PLANS[key]
        limits = "".join(f"<li>{html.escape(line)}</li>" for line in plan_limit_lines(key)[:3])
        featured = key == "starter"
        featured_label = (
            f' aria-label="Featured plan: {html.escape(plan.name, quote=True)}"' if featured else ""
        )
        action_label = {
            "free": "Create a free account",
            "starter": "Choose Starter — $12/month",
            "pro": "Choose Pro — $29/month",
            "agency": "Choose Agency — $79/month",
        }[key]
        use_case = {
            "free": "Try it first",
            "starter": "Recommended for regular shops",
            "pro": "Higher-volume work",
            "agency": "Highest-volume work",
        }[key]
        cards.append(
            f'<article class="price-card{" featured" if featured else ""}"'
            f"{featured_label}"
            f'><p class="plan-kicker">{use_case}</p><h2>{html.escape(plan.name)}</h2>'
            f'<p class="price">{html.escape(plan.display_price)}</p>'
            f"<p>{html.escape(PLAN_BLURBS[key])}</p><ul>{limits}</ul>"
            f'<a class="button {"primary" if featured else "secondary"}" href="/auth/signup?plan={key}">{action_label}</a></article>'
        )
    body = f"""
<section class="page-hero pricing-hero"><p class="eyebrow">Simple, documented quotas</p><h1>Choose the draft volume that fits your shop.</h1><p class="lede">Every plan creates the same fact-locked Etsy draft. Choose Free to try it, Starter for regular listing work, or a higher volume plan for larger catalogs.</p></section>
<section class="pricing-grid">{"".join(cards)}</section>
<section class="panel billing-note"><h2>Clear billing, no surprises</h2><ul><li>Free requires no payment method.</li><li>Paid plans are charged monthly through Stripe Checkout after you choose a plan.</li><li>Manage payment details or cancel in the Stripe Customer Portal.</li></ul><p>Every draft remains editable and requires your review before publishing.</p></section>
"""
    return _page(
        title="Plans and pricing",
        description="Compare SellerDrafts Free, Starter $12, Pro $29, and Agency $79 monthly plans and their documented draft limits.",
        canonical_path="/pricing",
        body=body,
        schema_nodes=[
            {"@type": "WebPage", "name": "SellerDrafts plans and pricing", "url": _url("/pricing")}
        ],
    )


def legal_page() -> str:
    body = f"""
<section class="page-hero"><p class="eyebrow">Legal and trust</p><h1>Terms, privacy, and acceptable use</h1><p class="lede">SellerDrafts is operated by {html.escape(OPERATOR_NAME)}. The current contact is shown in each policy below. Legal review remains an operator launch action.</p></section>
<nav class="legal-index" aria-label="Legal sections"><a href="#terms">Terms</a><a href="#privacy">Privacy</a><a href="#acceptable-use">Acceptable Use</a></nav>
<article class="legal-copy" id="terms">{markdown_to_safe_html(TERMS_MARKDOWN)}</article>
<article class="legal-copy" id="privacy">{markdown_to_safe_html(PRIVACY_MARKDOWN)}</article>
<article class="legal-copy" id="acceptable-use">{markdown_to_safe_html(ACCEPTABLE_USE_MARKDOWN)}</article>
"""
    return _page(
        title="Legal and trust",
        description="Read the SellerDrafts Terms of Service, Privacy Policy, Acceptable Use Policy, operator identity, and draft-review responsibilities.",
        canonical_path="/legal",
        body=body,
        schema_nodes=[
            {"@type": "WebPage", "name": "SellerDrafts legal and trust", "url": _url("/legal")}
        ],
    )


def guides_page() -> str:
    cards = "".join(
        '<a class="guide-card" href="/guides/'
        + html.escape(guide.slug, quote=True)
        + '"><p class="eyebrow">'
        + html.escape(guide.eyebrow)
        + "</p><h2>"
        + html.escape(guide.title)
        + "</h2><p>"
        + html.escape(guide.description)
        + "</p><span>Read guide →</span></a>"
        for guide in GUIDES.values()
    )
    body = f"""
<section class="page-hero"><p class="eyebrow">SellerDrafts guides</p><h1>Fact-first Etsy listing guides</h1><p class="lede">Practical checks for turning verified product details into a review-ready draft. Always confirm the current marketplace rules for your item and location.</p></section>
<section class="guide-index card-grid three">{cards}</section>
"""
    return _page(
        title="Etsy listing guides",
        description=(
            "Fact-first Etsy listing guides for accurate titles, descriptions, tags, and "
            "claim review before publishing."
        ),
        canonical_path="/guides",
        body=body,
        schema_nodes=[
            {
                "@type": "CollectionPage",
                "name": "SellerDrafts Etsy listing guides",
                "url": _url("/guides"),
            }
        ],
    )


def guide_page(slug: str) -> str | None:
    guide = GUIDES.get(slug)
    if guide is None:
        return None
    body = f"""
<article class="guide"><header class="page-hero"><p class="eyebrow">{html.escape(guide.eyebrow)}</p><h1>{html.escape(guide.title)}</h1><p class="article-meta">SellerDrafts guide · Reviewed August 27, 2026 · 5 minute read</p></header>{guide.body}
<section class="guide-cta"><p class="eyebrow">Put the checklist into practice</p><h2>Start with facts you can verify.</h2><p>SellerDrafts turns supplied details into a starting draft and keeps missing facts visible.</p><div class="actions"><a class="button primary" href="/auth/signup">Create a Free account</a><a class="text-link" href="/pricing">Compare plans</a></div></section></article>
"""
    return _page(
        title=guide.title,
        description=guide.description,
        canonical_path=f"/guides/{guide.slug}",
        body=body,
        schema_nodes=[
            {
                "@type": "Article",
                "headline": guide.title,
                "description": guide.description,
                "datePublished": "2026-08-27",
                "dateModified": "2026-08-27",
                "mainEntityOfPage": _url(f"/guides/{guide.slug}"),
                "author": {"@type": "Organization", "name": "SellerDrafts"},
                "publisher": {"@type": "Organization", "name": "Johnson Solutions LLC"},
            }
        ],
    )
