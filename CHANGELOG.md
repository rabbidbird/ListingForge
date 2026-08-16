# Changelog

## v1.0.0 release candidate — 2026-08-15

- Replaced YAML/demo authentication with PostgreSQL users, Argon2 passwords, Terms acceptance, opaque hashed sessions, HttpOnly cookies, login, logout, and signup.
- Added SQLAlchemy models and an Alembic migration for users, sessions, listings, usage events, subscriptions, and idempotent webhook events; production now rejects SQLite.
- Enforced user ownership on listing read, update, delete, history, and export.
- Centralized Free/Starter/Pro/Agency quotas, transactional reservations, per-minute limits, LLM caps, and bulk row caps.
- Implemented Stripe-hosted subscription Checkout, Customer Portal, signature verification, Price-based entitlements, idempotency, deletion downgrade, and out-of-order event protection.
- Hardened fact-locking, expanded prohibited claims, removed unsafe claim suggestion banks, and made unsourced LLM vocabulary or numbers fail closed to deterministic templates.
- Added CSV upload ceilings, empty-file handling, `nan` cleanup, and row-isolated validation failures.
- Reworked all UI copy around TrueDraft, mandatory draft review, real clipboard controls, honest heuristic checklists, and confirmation-before-export.
- Expanded Terms, Privacy, and Acceptable Use with launch-blocking operator placeholders and LLM-provider disclosure.
- Added a fully pinned dependency lock, non-root nginx/FastAPI/Streamlit container, PostgreSQL Compose smoke path, Railway config, GitHub Actions CI, and release documentation.
