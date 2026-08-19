# Deployment Guide – ListingForge

## 1. Streamlit Community Cloud (easiest, free)

1. Push this repo to GitHub (already done).
2. Go to https://share.streamlit.io
3. New app → select `rabbidbird/ListingForge` → Main file `app.py`
4. (Optional) Add secrets in the dashboard:
   ```
   OPENAI_API_KEY = "sk-..."
   # or
   XAI_API_KEY = "xai-..."
   OPENAI_BASE_URL = "https://api.x.ai/v1"
   ```
5. Deploy. Your app is live in ~2 minutes.

## 2. Railway / Render / Fly.io

- Connect the GitHub repo.
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Add environment variables for any API keys.

## 3. Docker

```bash
docker build -t listingforge .
docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... listingforge
```

## 4. Adding Authentication for launch

1. Create `config/credentials.yaml` from `config/credentials.yaml.example`.
2. Set `LISTINGFORGE_REQUIRE_AUTH=true`.
3. Keep `LISTINGFORGE_SKIP_AUTH` or `TRUEDRAFT_SKIP_AUTH=true` only for local/dev flows.
4. Route your pages through `core.auth` helpers for per-user onboarding.
   - In non-auth mode, users are assigned a per-session `guest-*` ID by default unless `LISTINGFORGE_USER_ID` is set.
5. Replace the local file-based session model with your production identity provider when ready.

## 6. Adding Stripe (for paid plans)

Recommended flow:
- Free tier: 5 generations / day (track in SQLite or Redis)
- Paid: Stripe Checkout → webhook updates user plan in DB
- Use `stripe` Python package + a simple `users` table.
  - Set: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_AGENCY`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`.

High-level steps:
1. Create products/prices in Stripe dashboard.
2. Enable checkout/session creation from your billing flow.
3. Add webhook endpoint to `/webhook/stripe` in a production service and pass `user_id` in metadata.
4. Store `stripe_customer_id`, `plan`, and last invoice metadata on the user.

This keeps the current pure-Streamlit architecture simple while allowing real monetization.
