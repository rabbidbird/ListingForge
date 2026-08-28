"""Canonical SellerDrafts legal copy and Terms acceptance version."""

from __future__ import annotations

import html
import re

TERMS_VERSION = "2026-08-27-v1"
TERMS_EFFECTIVE_DATE = "August 27, 2026"
OPERATOR_NAME = "Johnson Solutions LLC, doing business as SellerDrafts"
CONTACT_EMAIL = "jaylen.johnson0@gmail.com"
JURISDICTION = "Ohio, United States"

TERMS_MARKDOWN = f"""
## Terms of Service

**Effective date:** {TERMS_EFFECTIVE_DATE}

**Operator:** {OPERATOR_NAME}
**Contact:** {CONTACT_EMAIL}

These Terms govern access to SellerDrafts. By creating an account or accepting an updated version, you accept these Terms and the Privacy Policy. If you use SellerDrafts for an organization, you confirm that you can bind that organization.

### 1. Service and accounts

SellerDrafts creates starting drafts of product listing text from information a user supplies. You must provide accurate account information, protect your credentials, and promptly report suspected account misuse. You may not share an account to evade plan limits.

### 2. Draft output and user responsibility

Every title, description, tag, and export is a **DRAFT — verify before publishing**. You are solely responsible for checking product facts, materials, dimensions, ratings, certifications, origin, intellectual-property rights, shipping statements, prices, marketplace eligibility, and all other claims before publication. SellerDrafts does not publish to marketplaces for you.

### 3. Informational checklists

Checklist statuses are mechanical, informational prompts only. They do not predict or guarantee search placement, policy compliance, conversion, revenue, or sales. Marketplace rules and category limits can change, and you must confirm the rules that apply when you publish.

### 4. Optional LLM processing

When the operator enables an LLM integration, supplied prompts and product facts may be sent to the configured LLM provider for processing. Source-lock checks can reject an LLM response and use deterministic template output instead, but you must still review the final draft.

LLM mode is unavailable at launch.

### 5. Plans, payments, and cancellation

Plan quotas are enforced per account. Paid subscriptions are processed by Stripe and renew until cancelled. Prices, billing intervals, and any taxes are shown at Checkout. You can manage or cancel through the Stripe Customer Portal. Except where required by law or expressly stated at Checkout, payments already made are non-refundable; cancellation stops future renewal and access remains governed by the status Stripe reports.

### 6. Your content and license

You retain rights in information you submit and resulting drafts to the extent allowed by law. You grant {OPERATOR_NAME}, a limited license to host, process, transmit, and back up that content only as needed to operate, secure, and support SellerDrafts.

### 7. Prohibited conduct

You must follow the Acceptable Use Policy. We may suspend or terminate access for material violations, fraud, security risk, nonpayment, or conduct that threatens the service or other users.

### 8. Service changes and availability

We may change or discontinue features and limits with reasonable notice where practicable. The service is provided on an “as available” basis. No uptime, marketplace compatibility, or error-free operation is guaranteed unless a separate written agreement says otherwise.

### 9. Disclaimers and liability

To the maximum extent permitted by law, SellerDrafts is provided without implied warranties. {OPERATOR_NAME}, is not responsible for marketplace rejection, account action, inaccurate user input, content you publish, lost profits, or indirect or consequential loss. Any aggregate liability is limited to the amount you paid for SellerDrafts during the three months before the event giving rise to the claim, unless applicable law requires a different result.

### 10. Governing law and disputes

These Terms are governed by the laws of {JURISDICTION}, without regard to conflict-of-law rules. Courts located in {JURISDICTION} have exclusive jurisdiction except where consumer law requires otherwise.

### 11. Changes and contact

Material updates will be posted with a new effective date and version. Questions or legal notices may be sent to {CONTACT_EMAIL}.
""".strip()

PRIVACY_MARKDOWN = f"""
## Privacy Policy

**Effective date:** {TERMS_EFFECTIVE_DATE}

**Data controller/operator:** {OPERATOR_NAME}
**Privacy contact:** {CONTACT_EMAIL}

### 1. Information collected

- Account data: email address, name, password hash, linked Google identity identifiers, Terms acceptance, verification status, and session records.
- Product content: facts, keywords, CSV inputs, generated drafts, and checklist results.
- Usage and security data: generation events, plan enforcement records, approximate request source such as IP address on authentication routes, timestamps, and operational logs.
- Billing metadata: Stripe customer, subscription, Price, and status identifiers. SellerDrafts does not store full payment-card numbers.

### 2. Why information is used

Information is used to authenticate users, provide private draft history, generate requested content, enforce quotas, prevent abuse, process subscription state, troubleshoot failures, secure the service, comply with law, and communicate about an account.

### 3. Service providers

- **Stripe** processes Checkout, subscription billing, and the Customer Portal under Stripe's own privacy terms.
- **Hosting and PostgreSQL providers** store and process application data and backups for service operation.
- **Google** processes account identity information when a user chooses Google sign-in.
- **LLM providers** may process prompts and supplied product facts only when the operator enables LLM mode. The provider and its retention or training settings depend on the API account configured by the operator.

Providers receive only information reasonably needed for their role. Data may be processed in countries different from yours, subject to the safeguards required by applicable law.

### 4. Cookies and campaign attribution

SellerDrafts uses an essential, HttpOnly session cookie to keep users signed in and short-lived anti-forgery cookies for authentication and account actions. When someone first arrives through a tagged campaign link, SellerDrafts may also store a signed, first-party attribution cookie for up to 30 days. It contains limited campaign source, medium, campaign, creative, search-term, and landing-path labels. If the visitor creates an account, those labels may be attached to the account for aggregate measurement of signups, first drafts, and currently active paid users. SellerDrafts does not install a TikTok or X advertising pixel in v1 and does not use this cookie for cross-site tracking.

### 5. Retention

Account, subscription, and saved-draft data is retained while the account is active or as needed to provide the service. Revoked sessions and security or usage records may be retained for a limited period for fraud prevention, plan enforcement, legal obligations, and incident investigation. Billing records may be retained as required by tax and accounting law. Verified deletion requests are handled subject to applicable legal, security, backup, and recordkeeping requirements.

### 6. Security and isolation

Passwords are hashed with Argon2. Session tokens are random, stored as keyed hashes, and sent in secure cookies. Listing reads, updates, deletes, and exports require the owning user ID. PostgreSQL transactions enforce generation entitlements. No security control eliminates all risk.

### 7. Choices and rights

Depending on your location, you may have rights to access, correct, export, delete, restrict, or object to processing of personal data, and to complain to a regulator. Send requests to {CONTACT_EMAIL}. Identity verification may be required. Some records can be retained where law or legitimate security needs require it.

### 8. Children

SellerDrafts is not directed to children under 13, or a higher minimum age required by local law. Do not create an account if you cannot legally consent to these terms.

### 9. Changes and contact

Material changes will be posted with a revised effective date. Contact {OPERATOR_NAME} at {CONTACT_EMAIL}. The operator is established in {JURISDICTION}.
""".strip()

ACCEPTABLE_USE_MARKDOWN = f"""
## Acceptable Use Policy

**Effective date:** {TERMS_EFFECTIVE_DATE}

You may not use SellerDrafts to:

- create or publish a claim you know is false, deceptive, unverified, or likely to mislead a buyer;
- invent ratings, reviews, sales status, scarcity, certifications, origin, health claims, materials, shipping promises, or intellectual-property ownership;
- list illegal, regulated, recalled, unsafe, counterfeit, stolen, or marketplace-prohibited goods;
- infringe copyright, trademark, patent, privacy, publicity, or other rights;
- submit personal, confidential, payment-card, health, or authentication information that is unnecessary for a product draft;
- access or attempt to access another user's account, drafts, subscription, sessions, or usage records;
- evade quotas, share credentials for quota avoidance, automate abusive signups, or bypass rate and upload limits;
- probe, scrape, overload, reverse engineer, disrupt, or introduce malicious code into the service; or
- use output as evidence of marketplace compliance, ranking likelihood, a sales guarantee, or professional legal or regulatory advice.

{OPERATOR_NAME}, may investigate suspected violations and suspend access where reasonably necessary to protect users, providers, or the service. Report abuse to {CONTACT_EMAIL}. Enforcement is subject to applicable law in {JURISDICTION}.
""".strip()


def legal_markdown_sections() -> tuple[str, str, str]:
    """Return the canonical text used by both public and signed-in legal pages."""

    return TERMS_MARKDOWN, PRIVACY_MARKDOWN, ACCEPTABLE_USE_MARKDOWN


def markdown_to_safe_html(markdown: str) -> str:
    """Render the small, fixed Markdown subset used by the canonical legal copy."""

    lines = markdown.splitlines()
    rendered: list[str] = []
    in_list = False

    def inline(value: str) -> str:
        escaped = html.escape(value.strip())
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        return escaped.replace("  ", "<br>")

    for raw in lines:
        line = raw.strip()
        if line.startswith("- "):
            if not in_list:
                rendered.append("<ul>")
                in_list = True
            rendered.append(f"<li>{inline(line[2:])}</li>")
            continue
        if in_list:
            rendered.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("### "):
            rendered.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            rendered.append(f"<h2>{inline(line[3:])}</h2>")
        else:
            rendered.append(f"<p>{inline(line)}</p>")
    if in_list:
        rendered.append("</ul>")
    return "".join(rendered)
