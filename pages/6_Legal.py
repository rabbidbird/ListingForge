"""Public v1 legal and trust pages with launch-blocking operator placeholders."""

from __future__ import annotations

import streamlit as st

from core.auth import streamlit_current_user
from core.ui import configure_page, render_public_footer, render_sidebar

configure_page("Legal", "📜")
render_sidebar(streamlit_current_user())

st.title("Legal and trust")
st.write(
    "TrueDraft creates starting drafts from facts you supply. You are responsible for "
    "every claim you publish. These pages still contain operator-identity placeholders "
    "that must be replaced before paid public traffic."
)
st.error(
    "Launch blocker: replace {{OPERATOR_LEGAL_NAME}}, {{CONTACT_EMAIL}}, and "
    "{{JURISDICTION}} everywhere on this page before accepting public customers."
)
terms_tab, privacy_tab, use_tab = st.tabs(["Terms of Service", "Privacy Policy", "Acceptable Use"])

with terms_tab:
    st.markdown(
        """
## Terms of Service

**Effective date:** August 15, 2026

**Operator:** {{OPERATOR_LEGAL_NAME}}
**Contact:** {{CONTACT_EMAIL}}

These Terms govern access to TrueDraft. By creating an account, you accept these Terms and the Privacy Policy. If you use TrueDraft for an organization, you confirm that you can bind that organization.

### 1. Service and accounts

TrueDraft creates starting drafts of product listing text from information a user supplies. You must provide accurate registration information, protect your credentials, and promptly report suspected account misuse. You may not share an account to evade plan limits.

### 2. Draft output and user responsibility

Every title, description, tag, and export is a **DRAFT — verify before publishing**. You are solely responsible for checking product facts, materials, dimensions, ratings, certifications, origin, intellectual-property rights, shipping statements, prices, marketplace eligibility, and all other claims before publication. TrueDraft does not publish to marketplaces for you.

### 3. Heuristic checklists

Scores and grades are mechanical checklists only. They do not predict or guarantee search placement, policy compliance, conversion, revenue, or sales. Marketplace rules and category limits can change, and you must confirm the rules that apply when you publish.

### 4. Optional LLM processing

When the operator enables an LLM integration, supplied prompts and product facts may be sent to the configured LLM provider for processing. Source-lock checks can reject an LLM response and use deterministic template output instead, but you must still review the final draft.

### 5. Plans, payments, and cancellation

Plan quotas are enforced per account. Paid subscriptions are processed by Stripe and renew until cancelled. Prices, billing intervals, and any taxes are shown at Checkout. You can manage or cancel through the Stripe Customer Portal. Except where required by law or expressly stated at Checkout, payments already made are non-refundable; cancellation stops future renewal and access remains governed by the status Stripe reports.

### 6. Your content and license

You retain rights in information you submit and resulting drafts to the extent allowed by law. You grant {{OPERATOR_LEGAL_NAME}} a limited license to host, process, transmit, and back up that content only as needed to operate, secure, and support TrueDraft.

### 7. Prohibited conduct

You must follow the Acceptable Use Policy. We may suspend or terminate access for material violations, fraud, security risk, nonpayment, or conduct that threatens the service or other users.

### 8. Service changes and availability

We may change or discontinue features and limits with reasonable notice where practicable. The service is provided on an “as available” basis. No uptime, marketplace compatibility, or error-free operation is guaranteed unless a separate written agreement says otherwise.

### 9. Disclaimers and liability

To the maximum extent permitted by law, TrueDraft is provided without implied warranties. {{OPERATOR_LEGAL_NAME}} is not responsible for marketplace rejection, account action, inaccurate user input, content you publish, lost profits, or indirect or consequential loss. Any aggregate liability is limited to the amount you paid for TrueDraft during the three months before the event giving rise to the claim, unless applicable law requires a different result.

### 10. Governing law and disputes

These Terms are governed by the laws of {{JURISDICTION}}, without regard to conflict-of-law rules. Courts located in {{JURISDICTION}} have exclusive jurisdiction except where consumer law requires otherwise.

### 11. Changes and contact

Material updates will be posted with a new effective date. Questions or legal notices may be sent to {{CONTACT_EMAIL}}.
"""
    )

with privacy_tab:
    st.markdown(
        """
## Privacy Policy

**Effective date:** August 15, 2026

**Data controller/operator:** {{OPERATOR_LEGAL_NAME}}
**Privacy contact:** {{CONTACT_EMAIL}}

### 1. Information collected

- Account data: email address, name, password hash, Terms acceptance, verification status, and session records.
- Product content: facts, keywords, CSV inputs, generated drafts, and checklist results.
- Usage and security data: generation events, plan enforcement records, approximate request source such as IP address on authentication routes, timestamps, and operational logs.
- Billing metadata: Stripe customer, subscription, Price, and status identifiers. TrueDraft does not store full payment-card numbers.

### 2. Why information is used

Information is used to authenticate users, provide private draft history, generate requested content, enforce quotas, prevent abuse, process subscription state, troubleshoot failures, secure the service, comply with law, and communicate about an account.

### 3. Service providers

- **Stripe** processes Checkout, subscription billing, and the Customer Portal under Stripe's own privacy terms.
- **Hosting and PostgreSQL providers** store and process application data and backups for service operation.
- **LLM providers** may process prompts and supplied product facts only when the operator enables LLM mode. The provider and its retention/training settings depend on the API account configured by the operator.

Providers receive only information reasonably needed for their role. Data may be processed in countries different from yours, subject to the safeguards required by applicable law.

### 4. Cookies

TrueDraft uses an essential, HttpOnly session cookie to keep users signed in and a short-lived anti-forgery cookie on authentication forms. These are required for account security; no advertising cookie is included in v1.

### 5. Retention

Account, subscription, and saved-draft data is retained while the account is active or as needed to provide the service. Revoked sessions and security/usage records may be retained for a limited period for fraud prevention, plan enforcement, legal obligations, and incident investigation. Billing records may be retained as required by tax and accounting law. Verified deletion requests are handled subject to applicable legal, security, backup, and recordkeeping requirements.

### 6. Security and isolation

Passwords are hashed with Argon2. Session tokens are random, stored as keyed hashes, and sent in secure cookies. Listing reads, updates, deletes, and exports require the owning user ID. PostgreSQL transactions enforce generation entitlements. No security control eliminates all risk.

### 7. Choices and rights

Depending on your location, you may have rights to access, correct, export, delete, restrict, or object to processing of personal data, and to complain to a regulator. Send requests to {{CONTACT_EMAIL}}. Identity verification may be required. Some records can be retained where law or legitimate security needs require it.

### 8. Children

TrueDraft is not directed to children under 13, or a higher minimum age required by local law. Do not create an account if you cannot legally consent to these terms.

### 9. Changes and contact

Material changes will be posted with a revised effective date. Contact {{OPERATOR_LEGAL_NAME}} at {{CONTACT_EMAIL}}. The operator is established in {{JURISDICTION}}.
"""
    )

with use_tab:
    st.markdown(
        """
## Acceptable Use Policy

**Effective date:** August 15, 2026

You may not use TrueDraft to:

- create or publish a claim you know is false, deceptive, unverified, or likely to mislead a buyer;
- invent ratings, reviews, sales status, scarcity, certifications, origin, health claims, materials, shipping promises, or intellectual-property ownership;
- list illegal, regulated, recalled, unsafe, counterfeit, stolen, or marketplace-prohibited goods;
- infringe copyright, trademark, patent, privacy, publicity, or other rights;
- submit personal, confidential, payment-card, health, or authentication information that is unnecessary for a product draft;
- access or attempt to access another user's account, drafts, subscription, sessions, or usage records;
- evade quotas, share credentials for quota avoidance, automate abusive signups, or bypass rate and upload limits;
- probe, scrape, overload, reverse engineer, disrupt, or introduce malicious code into the service;
- use output as evidence of marketplace compliance, ranking likelihood, guaranteed sales, or professional legal/regulatory advice.

{{OPERATOR_LEGAL_NAME}} may investigate suspected violations and suspend access where reasonably necessary to protect users, providers, or the service. Report abuse to {{CONTACT_EMAIL}}. Enforcement is subject to applicable law in {{JURISDICTION}}.
"""
    )

render_public_footer()
