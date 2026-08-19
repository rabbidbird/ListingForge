# Merge strategy: paid SaaS path vs `main`

This branch (`agent/prepare-truedraft-v1`, PR #1) is the **paid TrueDraft v1
path**. `main` later grew a **local SQLite / guest-identity** pass that is a
different product model. Those commits must not be mixed into this branch.

## What each line is

| Line | Identity | Auth | Data | Billing |
|---|---|---|---|---|
| `agent/prepare-truedraft-v1` | TrueDraft | PostgreSQL users, Argon2, HttpOnly sessions, Terms | Alembic + Postgres (SQLite only in `development`/`test`) | Price-mapped Checkout, portal, signed idempotent webhooks, fail-closed entitlements |
| current `main` (`70735b1`) | ListingForge | YAML `streamlit-authenticator`, `LISTINGFORGE_SKIP_AUTH`, `guest-*` session IDs | `data/listings.db` SQLite, optional `usage.json` | Trusts `metadata.plan`, unknown Price → Pro, "unlimited" Pro/Agency copy |

Merge-base is `99198bc`. Unique `main` commits after that:

1. `d8fd1f6` — guest identity + SQLite usage/history isolation for local demo
2. `b86b506` — Checkout buttons and `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL` on the old stack
3. `70735b1` — handoff notes only (`project-notes/chat-handoff-2026-08-18.md`)

## Do not

- Click **Update branch** on PR #1 if that rebases or merges current `main`.
- Rebase this branch onto current `main` and accept theirs.
- Cherry-pick `d8fd1f6` or `b86b506`.
- Reintroduce `LISTINGFORGE_SKIP_AUTH`, `TRUEDRAFT_SKIP_AUTH`,
  `LISTINGFORGE_REQUIRE_AUTH`, `LISTINGFORGE_USER_ID`, `guest-*` IDs,
  `data/listings.db`, `STRIPE_SUCCESS_URL`, or fail-open Price mapping.

Those behaviors would let unauthenticated traffic use the product, mix history,
bypass Terms, claim unlimited paid plans, or grant entitlements from
attacker-controlled Checkout metadata.

## Recommended landing sequence

1. Keep PR #1 as the integration vehicle. Leave it draft until
   [SHIP_CHECKLIST.md](../SHIP_CHECKLIST.md) is understood; the four remaining
   items are operator-owned and are not solved by merging `main`.
2. Merge **this branch into `main`**, not the reverse. Preferred options, in
   order:
   - GitHub merge (create a merge commit or squash) **after** changing the PR
     base is unnecessary if GitHub is set to merge the paid branch onto `main`
     with this branch winning every conflict.
   - Operator admin reset: once reviewed, point `main` at this branch tip.
   - If GitHub reports the PR dirty: update by merging with `-X ours` for
     product files, or recreate the PR against the old merge-base tag and land
     it, then fast-forward `main`.
3. After landing, treat `d8fd1f6` / `b86b506` as abandoned local-demo history.
   Optionally keep `70735b1`'s handoff file as an archive note that says the
   guest/SQLite path is superseded — do not restore its recommendations.
4. Checkout UX from `b86b506` is already superseded by
   `pages/5_About_Pricing.py` on this branch (plan buttons, portal, webhook
   return copy). Do not take main's button code.
5. Launch only after `ENV=production python -m scripts.launch_check` exits 0
   on the production environment. That check also flags leftover
   `LISTINGFORGE_*` / skip-auth variables.

## If a future local-demo mode is wanted

Add it as a **new, explicitly non-production** adapter behind `ENV=development`
only. Do not reuse guest IDs, YAML credentials, or SQLite listing tables as the
paid identity model. Production must keep failing closed on SQLite, documented
secrets, and localhost public URLs.
