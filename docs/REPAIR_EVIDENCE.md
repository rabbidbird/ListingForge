# SellerDrafts bounded repair evidence — September 8, 2026 UTC

Source baseline: `d5116320051670519a29bd5f19cb5989d1b473e2`, freshly fetched
`origin/main`. Initial working tree clean; no repository AGENTS.md. Work is on
`codex/sellerdrafts-bounded-repair`. The repair PR's head is the delivery revision;
older successful CI is not used as its verification.

## Implemented behavior

- The actual Google signup anchor includes a valid query separator and allowlisted
  plan intent. Existing password login and explicit Google linking remain intact.
- Titles and tags retain complete supplied factual spans. Repeated dimensions,
  decimals/fractions, units, and negations are preserved. Oversized optional phrases
  are omitted whole with visible review notes; factual phrases are never sliced to
  reach a word-count style target. The phrase-ID LLM path and disabled default remain.
- Generation, editing, history reads, and exports share validation. Invalid Etsy
  tag characters/count/length have visible states. Legacy scores are recomputed in
  memory; stored data is not rewritten. Literal fact-span changes and identifiable
  legacy damaged titles require review. This is not semantic or real-world truth
  certification. Shopify's 70-character target remains advisory.
- Every public sample output comes from one actual generator result, including
  its review notes. The paper workbench remains; bundled fonts load under a narrow
  same-origin policy and a content-versioned stylesheet prevents stale layout.
- History uses `(created_at, id)` keysets, 50-row UI pages (server maximum 100),
  search and platform filtering, previous/next navigation, and page-scoped exports.
  Older records retain inspect/edit/delete/export and server-owned user filtering.
- Content-free outcome measurement and explicit fixture/unclassified handling are
  documented in [MEASUREMENT.md](MEASUREMENT.md).

## Verification

Windows virtual environment: Python 3.12.13. Supported container: pinned Python
3.11.13 and PostgreSQL 17.6 from the repository Docker/Compose configuration.

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --tb=short
```

The final regression run passed 219 tests on Windows; the preceding pinned Linux
container run passed all 215 tests then present. The final signup refinement adds callback coverage for every plan and
uses `AppTest.from_file("app.py").switch_page(...)` for new Google signup → draft →
History; its focused run passed 14 tests. Final CI must verify the complete PR head.
Windows reported 12 SQLite datetime-adapter deprecation warnings; the Python 3.11
container run had none. No test or permission was weakened to obtain a pass.

Docker was available through WSL Ubuntu. Task-only Compose projects were used;
unrelated running containers were left alone. Commands from the repository:

```sh
docker compose -p sellerdraftsrepairfinal up --build
docker compose -p sellerdraftsrepairfinal exec -T app python -m alembic check
docker compose -p sellerdraftsrepairfinal exec -T app python -m scripts.container_smoke
docker compose -p sellerdraftsrepairfinal exec -T -e ENV=test -e DATABASE_URL=sqlite:////tmp/repair-ci.db app python -m pytest --tb=short
```

The PostgreSQL schema check found no pending operations. The edge smoke passed
health, environment-appropriate signup, existing-account login/logout, session
handling, Streamlit WebSocket upgrade, and signed/idempotent Stripe fixture delivery.
No real provider account or live payment was created. Populated migration tests
preserve a legacy user, draft, and duplicate event rows while backfilling a unique
milestone; day-7 eligibility excludes unobserved historical windows.

Browser verification used `@playwright/cli` through the local nginx routes.
Artifacts are local in `output/playwright/` (not public repository attachments):

- `live-signup-before.png`: public signup rendered the malformed Google href.
- `home-desktop.png`, `home-mobile.png`, `home-mobile-large-text.png`: desktop,
  390-pixel mobile, and 200% root text. A mobile header overflow was found, fixed,
  and rechecked at `scrollWidth == innerWidth == 390`.
- Local fixture signup → draft → copy acknowledgment (`POST /events/product` 204)
  → confirmed CSV download → History was exercised. The title `5 X 5 Inch Print`
  and complete `20 cm chain with 10 cm extension` survived the workflow.
- Keyboard Tab reached the public skip link. Product form controls, confirmation
  labels, and navigation were exercised. Browser warnings concerned Streamlit's
  iframe sandbox combination; no public font CSP errors remained after the fix.

OAuth tests follow the HTML anchor for no plan and all supported plans, then test
the token-exchange and Google ID-token-verification library boundaries with
fixtures. They cover signed state, browser-state mismatch, nonce rejection, plan
intent, existing Google subjects, password-account non-auto-linking, and explicit
same-email linking. A real Google consent flow remains a production release check.

## Release gaps and rollback

Public `https://sellerdrafts.com/auth/signup` returned 200 with the faulty link at
the start of work. GitHub listed no deployment records for this repository.
`npx @railway/cli status --json` returned `Unauthorized`; the stored Railway login
must be renewed by its owner. No production credentials or customer analytics were
read, and no merge/deployment/payment mutation was performed. Once access and the
release are authorized, the engineer can verify the deployed SHA, run the read-only
production launch check, and check rendered plan links and existing-account access.
The owner need not debug OAuth or run the development test suite.

Mailbox delivery/reply ownership, legal review, genuine payment lifecycle, and
support effort remain unverified. No mail was sent, users contacted, ads bought,
or expansion implemented. **Hold expansion and paid acquisition**: activation,
repeat-use, payment, and support evidence is unknown.

Deploy both additive migrations with the application. Take the normal production
database backup before release. For an application regression, build a rollback
from the previous application source while **retaining both new Alembic revision
files and the migrated schema**. The old unmodified image expects the old head and
will fail the exact-head health check against the new schema. Do not blindly deploy
that old image or run `alembic downgrade`: dropping the milestone table discards
measurement history. Verify the compatibility rollback in a restored staging copy
before deploying it; that production rollback rehearsal was not available here.

The local SQLite migration/import smoke also passed. `scripts.launch_check` exited
0 in test mode and correctly reported `public-traffic gate: blocked` because the
local HTTP/SQLite environment has no production session/Stripe configuration.
That expected test-mode report is not a production readiness pass.
