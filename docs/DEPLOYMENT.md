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

## 4. Adding Authentication (recommended before charging)

1. Install already in requirements: `streamlit-authenticator`
2. Create `config/credentials.yaml` from the example.
3. In `app.py` or a new `auth.py`, initialize the authenticator and gate the pages.
4. Example snippet is provided in the codebase comments / future `core/auth.py`.

## 5. Adding Stripe (for paid plans)

Recommended flow:
- Free tier: 5 generations / day (track in SQLite or Redis)
- Paid: Stripe Checkout → webhook updates user plan in DB
- Use `stripe` Python package + a simple `users` table.

High-level steps:
1. Create products/prices in Stripe dashboard.
2. Add Checkout button on the Pricing page.
3. Webhook endpoint (can be a separate FastAPI/Flask micro-service or Streamlit + ngrok for testing).
4. Store `stripe_customer_id` and `plan` on the user.

This keeps the current pure-Streamlit architecture simple while allowing real monetization.
