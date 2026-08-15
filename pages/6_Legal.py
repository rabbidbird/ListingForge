"""
Legal pages for TrueDraft
"""

import streamlit as st

st.set_page_config(page_title="Legal | TrueDraft", page_icon="📜", layout="wide")

st.title("Legal")

tab1, tab2, tab3 = st.tabs(["Terms of Service", "Privacy Policy", "Acceptable Use"])

with tab1:
    st.markdown("""
## Terms of Service

**Last updated:** August 2026

TrueDraft provides draft product listing text based on information you supply.

### 1. Draft nature of output
All titles, descriptions, tags, and scores are **drafts**. You are solely responsible for verifying every claim, material, rating, shipping statement, and attribute against your actual product before publishing anywhere.

### 2. No ranking or sales guarantees
Heuristic scores are checklists, not predictions of search ranking, conversion rate, or sales.

### 3. Accounts and plans
Free and paid plan limits are enforced per account. Abuse, sharing of credentials, or attempts to circumvent limits may result in suspension.

### 4. Payments
Paid plans are billed via Stripe. Refunds are handled according to our refund policy (typically pro-rata within 14 days of first charge unless otherwise stated at checkout).

### 5. Limitation of liability
TrueDraft is provided “as is.” We are not liable for marketplace penalties, rejected listings, or losses arising from content you publish.

### 6. Changes
We may update these terms. Continued use after changes constitutes acceptance.
""")

with tab2:
    st.markdown("""
## Privacy Policy

**Last updated:** August 2026

### Data we collect
- Account information (email, name) when you register
- Listing drafts you generate (stored per account)
- Usage counts for plan enforcement
- Payment metadata via Stripe (we do not store full card numbers)

### How we use data
- To provide and improve the service
- To enforce plan limits
- To communicate about your account

### Third parties
- Stripe for payments
- Optional LLM providers (OpenAI, xAI, etc.) when you or the operator enable an API key

### Retention
- Account and listing data retained while your account is active
- You may request deletion of your account and associated listings

### Contact
Operator contact details should be filled in before public launch.
""")

with tab3:
    st.markdown("""
## Acceptable Use

You agree not to:
- Submit content you do not have rights to
- Use the service to generate knowingly false or deceptive product claims
- Attempt to access other users’ data
- Abuse free tiers, scrape the service, or overload infrastructure
- Use the service for illegal products or prohibited marketplace categories

Violations may result in immediate suspension without refund.
""")
