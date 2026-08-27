# Historical merge record: paid SellerDrafts vs retired local demo

Status: completed on 2026-08-23. PR #1 landed the paid SellerDrafts v1 tree on
`main` in merge commit `df1aef80743d20b42ce53581034056394158476d`.

The repository had diverged after merge-base `99198bc`:

- `agent/prepare-truedraft-v1` implemented PostgreSQL users, Argon2 passwords,
  HttpOnly sessions, Terms acceptance, Alembic migrations, fail-closed quotas,
  and signed/idempotent Stripe subscription webhooks.
- the old `main` line added a local SQLite / guest-identity demo using YAML
  credentials and a less restrictive Stripe skeleton.

To preserve the paid tree while joining both histories, the paid branch merged
the old `main` history with Git's `ours` strategy and PR #1 was then merged.
The resulting `main` tree was verified to match the paid branch exactly, and
both hosted test and container-smoke jobs passed.

## Retired behavior must not return

Do not reintroduce `LISTINGFORGE_SKIP_AUTH`, `TRUEDRAFT_SKIP_AUTH`,
`LISTINGFORGE_REQUIRE_AUTH`, `LISTINGFORGE_USER_ID`, guest user IDs,
`data/listings.db`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, or fail-open
Stripe Price mapping. Those behaviors could bypass Terms, mix user history, or
grant paid entitlements from untrusted Checkout metadata.

Any future local-demo adapter must be explicitly development-only and must not
replace the production identity, authorization, PostgreSQL, or entitlement
path. Continue with the operator-only [ship checklist](../SHIP_CHECKLIST.md).
