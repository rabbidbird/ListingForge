"""Server-rendered public pages for crawlability and trustworthy product discovery."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass

from .config import get_settings
from .copy import DRAFT_BANNER, PLAN_BLURBS, PRODUCT_NAME, plan_limit_lines
from .plans import PLANS

PUBLIC_PATHS = (
    "/",
    "/pricing",
    "/legal",
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
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Based on Etsy’s current Seller Policy and Seller Handbook. Marketplace guidance can change; SellerDrafts is not affiliated with Etsy.</p>
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
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Etsy’s Seller Policy requires honest, accurate representation of items, including origin, attributes, components, and materials. Always check the current policy for your item.</p>
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
<p class="source-note"><strong>Reviewed August 27, 2026.</strong> Sources: Etsy Help, “How to Use Tags to Get Found in Search,” and the Etsy Seller Handbook’s 2026 title guidance. SellerDrafts is not affiliated with Etsy.</p>
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
<script type="application/ld+json">{schema}</script>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><nav aria-label="SellerDrafts">
<a class="wordmark" href="/"><span>S</span>SellerDrafts</a>
<div class="nav-links"><a href="/guides/etsy-listing-draft-checklist">Guides</a><a href="/pricing">Plans</a><a href="/legal">Legal</a><a class="signin" href="/auth/login">Sign in</a></div>
</nav></header>
<main id="main">{body}</main>
<footer><div><a class="wordmark footer-mark" href="/"><span>S</span>SellerDrafts</a><p>Fact-locked starting drafts from facts you supply.</p></div><nav aria-label="Footer"><a href="/pricing">Plans</a><a href="/legal">Legal</a><a href="/auth/signup">Create account</a></nav><p class="fine-print">SellerDrafts is operated by Johnson Solutions LLC and is not affiliated with Etsy, Shopify, or Amazon.</p></footer>
</body></html>"""


def home_page() -> str:
    description = (
        "Create fact-locked Etsy listing drafts from product details you supply. Draft titles, "
        "descriptions, and tags without invented materials, claims, ratings, or shipping promises."
    )
    body = f"""
<section class="hero">
  <p class="eyebrow">Etsy-first listing workflow</p>
  <h1>Etsy listing drafts that stay inside the facts</h1>
  <p class="lede">Turn verified product facts into an Etsy title, description, and tags; Shopify and Amazon-style drafts are available too. Missing attributes stay missing, and SellerDrafts never publishes for you.</p>
  <div class="draft-warning"><strong>{html.escape(DRAFT_BANNER)}</strong></div>
  <div class="actions"><a class="button primary" href="/auth/signup">Create account</a><a class="button secondary" href="/auth/login">Sign in</a></div>
  <p class="path">Create account <span>→</span> template draft <span>→</span> private History</p>
</section>
<section><p class="eyebrow">How it works</p><h2>Structure the facts. Keep control of the listing.</h2>
<div class="card-grid three"><article><span class="step">01</span><h3>Supply facts</h3><p>Enter the item name and only details you can verify.</p></article><article><span class="step">02</span><h3>Generate a draft</h3><p>SellerDrafts arranges supplied wording into marketplace-style fields.</p></article><article><span class="step">03</span><h3>Review before publishing</h3><p>Compare every claim with the real product and current marketplace rules.</p></article></div></section>
<section class="split"><div><p class="eyebrow">Honesty is the feature</p><h2>No silent product facts</h2><p>Materials, certifications, origin, ratings, scarcity, and shipping promises appear only when you supply them. An incomplete draft is safer than confident misinformation.</p></div><div class="panel"><h3>What every draft includes</h3><ul><li>Title options built from supplied wording</li><li>A structured description and tags</li><li>A transparent heuristic checklist</li><li>A visible verification warning</li><li>Private account history</li></ul></div></section>
<section><p class="eyebrow">Learn before you publish</p><h2>Practical Etsy listing guides</h2><div class="card-grid three">
<a class="guide-card" href="/guides/etsy-listing-draft-checklist"><h3>Draft checklist</h3><p>Review facts, claims, photos, and shop settings.</p><span>Read guide →</span></a>
<a class="guide-card" href="/guides/write-etsy-listings-without-inventing-facts"><h3>Write without guessing</h3><p>Turn verified details into structure without adding promises.</p><span>Read guide →</span></a>
<a class="guide-card" href="/guides/etsy-title-description-and-tags-checklist"><h3>Title, description, and tags</h3><p>Check clarity, accurate details, and current constraints.</p><span>Read guide →</span></a>
</div></section>
<section class="closing"><p class="eyebrow">Start Free</p><h2>Create one careful draft before choosing a plan.</h2><p>Free includes 8 drafts per UTC day and 40 per UTC month. Every plan uses the same fact-locked template generator.</p><div class="actions center"><a class="button primary" href="/auth/signup">Create account</a><a class="text-link" href="/pricing">Compare plans</a></div></section>
"""
    base = get_settings().public_base_url
    return _page(
        title=PRODUCT_NAME,
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
                "email": "jaylen.johnson0@gmail.com",
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
        cards.append(
            f'<article class="price-card"><h2>{html.escape(plan.name)}</h2>'
            f'<p class="price">{html.escape(plan.display_price)}</p>'
            f"<p>{html.escape(PLAN_BLURBS[key])}</p><ul>{limits}</ul>"
            f'<a class="button {"primary" if key == "starter" else "secondary"}" href="/auth/signup">Start {html.escape(plan.name)}</a></article>'
        )
    body = f"""
<section class="page-hero"><p class="eyebrow">Simple, documented quotas</p><h1>Plans for careful listing work</h1><p class="lede">Every plan uses the same fact-locked template generator. Paid plans raise daily, monthly, and bulk limits; no plan changes the review requirement.</p><div class="draft-warning"><strong>{html.escape(DRAFT_BANNER)}</strong></div></section>
<section class="pricing-grid">{"".join(cards)}</section>
<section class="panel billing-note"><h2>Billing stays explicit</h2><ul><li>Free requires no Checkout or payment method.</li><li>Paid plans renew monthly through Stripe-hosted Checkout.</li><li>Signed webhooks apply entitlements; returning from Checkout alone does not change a plan.</li><li>Use the Stripe Customer Portal to update payment details or cancel.</li></ul><p>Checklist scores are heuristics only and do not predict ranking, conversion, or sales.</p></section>
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
    body = """
<section class="page-hero"><p class="eyebrow">Legal and trust</p><h1>Terms, privacy, and acceptable use</h1><p class="lede">SellerDrafts is operated by Johnson Solutions LLC, doing business as SellerDrafts, in Ohio, United States. Contact: <a href="mailto:jaylen.johnson0@gmail.com">jaylen.johnson0@gmail.com</a>.</p></section>
<nav class="legal-index" aria-label="Legal sections"><a href="#terms">Terms</a><a href="#privacy">Privacy</a><a href="#acceptable-use">Acceptable Use</a></nav>
<article class="legal-copy" id="terms"><p class="eyebrow">Effective August 27, 2026</p><h2>Terms of Service</h2>
<p>These Terms govern access to SellerDrafts. By creating an account, you accept these Terms and the Privacy Policy. If you use SellerDrafts for an organization, you confirm that you can bind that organization.</p>
<h3>1. Service and accounts</h3><p>SellerDrafts creates starting drafts of product listing text from information a user supplies. You must provide accurate registration information, protect your credentials, promptly report suspected account misuse, and not share an account to evade plan limits.</p>
<h3>2. Draft output and user responsibility</h3><p>Every title, description, tag, and export is a <strong>DRAFT — verify before publishing</strong>. You are responsible for checking product facts, materials, dimensions, ratings, certifications, origin, intellectual-property rights, shipping statements, prices, marketplace eligibility, and every other claim. SellerDrafts does not publish to marketplaces for you.</p>
<h3>3. Heuristic checklists</h3><p>Scores and grades are mechanical checklists only. They do not predict search placement, policy compliance, conversion, revenue, or sales. Marketplace rules and category limits can change, and you must confirm the rules that apply when you publish.</p>
<h3>4. Optional LLM processing</h3><p>If the operator later enables an LLM integration, supplied prompts and product facts may be sent to the configured provider for processing. Source-lock checks can reject a response and use deterministic template output instead, but you must still review the draft. LLM mode is unavailable at launch.</p>
<h3>5. Plans, payments, and cancellation</h3><p>Plan quotas are enforced per account. Paid subscriptions are processed by Stripe and renew until canceled. Prices, billing intervals, and taxes are shown at Checkout. You can manage or cancel through the Stripe Customer Portal. Except where required by law or expressly stated at Checkout, payments already made are non-refundable; cancellation stops future renewal and access remains governed by the status Stripe reports.</p>
<h3>6. Your content and license</h3><p>You retain rights in submitted information and resulting drafts to the extent allowed by law. You grant Johnson Solutions LLC a limited license to host, process, transmit, and back up that content only as needed to operate, secure, and support SellerDrafts.</p>
<h3>7. Prohibited conduct</h3><p>You must follow the Acceptable Use Policy. We may suspend or terminate access for material violations, fraud, security risk, nonpayment, or conduct that threatens the service or other users.</p>
<h3>8. Service changes and availability</h3><p>We may change or discontinue features and limits with reasonable notice where practicable. The service is provided on an “as available” basis. No uptime, marketplace compatibility, or error-free operation is promised unless a separate written agreement says otherwise.</p>
<h3>9. Disclaimers and liability</h3><p>To the maximum extent permitted by law, SellerDrafts is provided without implied warranties. Johnson Solutions LLC is not responsible for marketplace rejection, account action, inaccurate user input, content you publish, lost profits, or indirect or consequential loss. Aggregate liability is limited to the amount paid during the three months before the event giving rise to a claim, unless applicable law requires otherwise.</p>
<h3>10. Governing law and disputes</h3><p>These Terms are governed by Ohio law, without regard to conflict-of-law rules. Courts located in Ohio, United States have exclusive jurisdiction except where consumer law requires otherwise.</p>
<h3>11. Changes and contact</h3><p>Material updates will be posted with a new effective date. Questions or legal notices may be sent to <a href="mailto:jaylen.johnson0@gmail.com">jaylen.johnson0@gmail.com</a>.</p></article>
<article class="legal-copy" id="privacy"><p class="eyebrow">Effective August 27, 2026</p><h2>Privacy Policy</h2>
<h3>1. Information collected</h3><ul><li>Account data: email, name, password hash, Terms acceptance, verification status, and sessions.</li><li>Product content: facts, keywords, CSV inputs, drafts, and checklist results.</li><li>Usage and security data: generation events, plan enforcement, approximate authentication-route request source, timestamps, and logs.</li><li>Billing metadata: Stripe customer, subscription, Price, and status identifiers. SellerDrafts does not store full payment-card numbers.</li></ul>
<h3>2. Why information is used</h3><p>Information is used to authenticate users, provide private History, generate requested content, enforce quotas, prevent abuse, process subscriptions, troubleshoot, secure the service, comply with law, and communicate about accounts.</p>
<h3>3. Service providers</h3><p>Stripe processes Checkout, subscriptions, and the Customer Portal. Hosting and PostgreSQL providers store application data and backups. If LLM mode is later enabled, the configured provider may process prompts and supplied product facts under its own terms and retention settings. Providers receive only information reasonably needed for their role, and data may be processed in other countries subject to applicable safeguards.</p>
<h3>4. Cookies and campaign attribution</h3><p>Essential HttpOnly cookies maintain sessions and protect authentication forms. When you arrive through a tagged campaign link, SellerDrafts may store a signed, first-party campaign cookie for up to 30 days containing limited source, medium, campaign, creative, search-term, and landing-path labels. If you create an account, those labels may be attached to it to measure aggregate signups, first drafts, and subscriptions. SellerDrafts does not install a TikTok or X advertising pixel in this version and does not use this cookie for cross-site tracking.</p>
<h3>5. Retention</h3><p>Account, subscription, and saved-draft data is retained while needed to provide the service. Revoked sessions and security or usage records may be retained for fraud prevention, plan enforcement, legal obligations, and incident investigation. Billing records may be retained for tax and accounting obligations. Deletion requests remain subject to legal, security, backup, and recordkeeping requirements.</p>
<h3>6. Security and isolation</h3><p>Passwords are hashed with Argon2. Session tokens are random, stored as keyed hashes, and sent in secure cookies. Listing reads, updates, deletes, and exports require the owning user ID. PostgreSQL transactions enforce generation entitlements. No security control eliminates all risk.</p>
<h3>7. Choices and rights</h3><p>Depending on your location, you may have rights to access, correct, export, delete, restrict, or object to processing and to complain to a regulator. Contact <a href="mailto:jaylen.johnson0@gmail.com">jaylen.johnson0@gmail.com</a>. Identity verification may be required, and some records may be retained where law or legitimate security needs require it.</p>
<h3>8. Children</h3><p>SellerDrafts is not directed to children under 13, or a higher minimum age required by local law. Do not create an account if you cannot legally consent to these terms.</p>
<h3>9. Changes and contact</h3><p>Material changes will be posted with a revised effective date. Contact Johnson Solutions LLC at <a href="mailto:jaylen.johnson0@gmail.com">jaylen.johnson0@gmail.com</a>. The operator is established in Ohio, United States.</p></article>
<article class="legal-copy" id="acceptable-use"><p class="eyebrow">Effective August 27, 2026</p><h2>Acceptable Use Policy</h2><p>You may not use SellerDrafts to:</p><ul><li>create or publish a claim you know is false, deceptive, unverified, or likely to mislead a buyer;</li><li>invent ratings, reviews, sales status, scarcity, certifications, origin, health claims, materials, shipping promises, or intellectual-property ownership;</li><li>list illegal, regulated, recalled, unsafe, counterfeit, stolen, or marketplace-prohibited goods;</li><li>infringe copyright, trademark, patent, privacy, publicity, or other rights;</li><li>submit unnecessary personal, confidential, payment-card, health, or authentication information;</li><li>access another user’s account, drafts, subscription, sessions, or usage records;</li><li>evade quotas, share credentials for quota avoidance, automate abusive signups, or bypass rate and upload limits;</li><li>probe, scrape, overload, reverse engineer, disrupt, or introduce malicious code into the service; or</li><li>use output as evidence of marketplace compliance, ranking likelihood, a sales guarantee, or professional legal or regulatory advice.</li></ul><p>Johnson Solutions LLC may investigate suspected violations and suspend access where reasonably necessary to protect users, providers, or the service. Report abuse to <a href="mailto:jaylen.johnson0@gmail.com">jaylen.johnson0@gmail.com</a>. Enforcement is subject to applicable law in Ohio, United States.</p></article>
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
