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

- Click **Update branch** on PR #1. GitHub reports the PR dirty because `main`
  moved after the PR base; that is expected. The Merge button stays blocked.
  Updating the branch is how the guest/SQLite model gets mixed in.
- Rebase this branch onto current `main` and accept theirs.
- Cherry-pick `d8fd1f6` or `b86b506`.
- Reintroduce `LISTINGFORGE_SKIP_AUTH`, `TRUEDRAFT_SKIP_AUTH`,
  `LISTINGFORGE_REQUIRE_AUTH`, `LISTINGFORGE_USER_ID`, `guest-*` IDs,
  `data/listings.db`, `STRIPE_SUCCESS_URL`, or fail-open Price mapping.
- Run `git merge -s ours` while checked out on `main`. That keeps the
  guest/SQLite tree. `-s ours` keeps *the branch you are on*.

Those behaviors would let unauthenticated traffic use the product, mix history,
bypass Terms, claim unlimited paid plans, or grant entitlements from
attacker-controlled Checkout metadata.

## Land this branch as `main`

Pick **one**. Do not click Update branch first.

### Option A — preferred: point `main` at this tip

Requires permission to force-push `main`. The guest/SQLite commits remain in
git history but are no longer on `main`.

```bash
git fetch origin
git checkout main
git reset --hard origin/agent/prepare-truedraft-v1
git push --force-with-lease origin main
```

GitHub usually closes PR #1 as merged once `main` contains those commits.

### Option B — keep GitHub Merge, discard `main`'s tree

Use this if `main` is protected against force-push. Merge `main` with
strategy **ours while on the paid branch** so history links and the tree stays
TrueDraft. Then the PR is no longer dirty and GitHub Merge is safe.

```bash
git fetch origin
git checkout agent/prepare-truedraft-v1
git merge -s ours origin/main -m "Keep paid TrueDraft v1; discard guest/SQLite main line"
git push origin agent/prepare-truedraft-v1
```

Then merge PR #1 in the GitHub UI (merge commit or squash). Confirm the
resulting `main` tree still has `core/auth.py`, Alembic, and
`pages/5_About_Pricing.py`, and does **not** have `data/listings.db` or
`LISTINGFORGE_SKIP_AUTH`.

### After landing

1. Treat `d8fd1f6` / `b86b506` as abandoned local-demo history. Optionally
   keep `70735b1`'s handoff file as an archive note that says the guest/SQLite
   path is superseded — do not restore its recommendations.
2. Checkout UX from `b86b506` is already superseded by
   `pages/5_About_Pricing.py` on this branch. Do not take main's button code.
3. Continue [SHIP_CHECKLIST.md](../SHIP_CHECKLIST.md) from step 2 (Railway).
   Do not accept paid public traffic until
   `ENV=production python -m scripts.launch_check` prints
   `public-traffic gate: pass` against the live variable set.

## If a future local-demo mode is wanted

Add it as a **new, explicitly non-production** adapter behind `ENV=development`
only. Do not reuse guest IDs, YAML credentials, or SQLite listing tables as the
paid identity model. Production must keep failing closed on SQLite, documented
secrets, and localhost public URLs.
