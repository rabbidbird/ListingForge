# ListingForge ⚡

**AI-powered product listing optimizer for Etsy, Shopify & Amazon sellers.**

Turn basic product information into high-converting, SEO-optimized titles, descriptions, and tags in seconds. Complete with realistic scoring, bulk processing, history, and a clear monetization path.

This is a full micro-SaaS MVP — not a demo.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)

## Features

- **Smart Title Generation** — Multiple conversion-tested structures, keyword front-loading, platform-specific length limits (Etsy 140 / Shopify 70)
- **High-Converting Descriptions** — Hook → Features → Benefits → CTA framework used by top sellers
- **Platform-Perfect Tags** — Long-tail focused, fills all 13 Etsy slots, respects character limits
- **Realistic SEO Scoring** — Title / Description / Tags scored independently + overall grade (A+ to D)
- **Bulk CSV Processor** — Upload dozens of products, download fully optimized results
- **SEO Analyzer** — Audit any existing listing and get actionable feedback
- **Local History** — Every generation is saved to SQLite for later review/export
- **Beautiful dark UI** — Professional Streamlit interface ready for customers

## Quick Start

```bash
# Clone
git clone https://github.com/rabbidbird/ListingForge.git
cd ListingForge

# Install
pip install -r requirements.txt

# Run
streamlit run app.py
```

Open http://localhost:8501

## Project Structure

```
ListingForge/
├── app.py                  # Home / marketing page
├── pages/
│   ├── 1_Optimizer.py      # Single listing generator
│   ├── 2_Bulk_Processor.py # CSV bulk mode
│   ├── 3_SEO_Analyzer.py   # Audit existing listings
│   ├── 4_History.py        # Saved generations
│   └── 5_About_Pricing.py  # Monetization guide
├── core/
│   ├── generator.py        # Core generation engine
│   ├── seo_scorer.py       # Scoring logic
│   ├── templates.py        # Power words, category language, structures
│   └── utils.py            # DB, export helpers
├── data/                   # SQLite DB + samples
├── requirements.txt
├── Dockerfile
└── README.md
```

## Monetization (Built-in Guide)

See the in-app **About & Pricing** page or the summary below:

| Plan       | Suggested Price | Notes                          |
|------------|-----------------|--------------------------------|
| Free       | $0              | 5 listings/month (lead magnet) |
| Starter    | $9–12/mo        | 50 listings + bulk             |
| Pro        | $19–29/mo       | Unlimited                      |
| Agency     | $49–79/mo       | Multi-user / white-label       |
| Lifetime   | $97–147         | AppSumo-style                  |

**Recommended launch path:**
1. Deploy to Streamlit Cloud or Railway
2. Add simple auth + Stripe
3. Post in Etsy seller groups / Reddit
4. Optional: AppSumo lifetime deal for initial capital + users

The generation engine is currently high-quality rule + template based (no API costs). You can later swap in OpenAI/Claude/Grok for even stronger output while keeping the same interface.

## Adding Real AI (Optional)

The generator methods in `core/generator.py` have clean input/output contracts.  
To upgrade any method to a real LLM:

```python
# Pseudo-code
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user", "content": user_prompt}]
)
return parse_response(response)
```

Keep the SEO scorer — it remains valuable even with LLM output.

## Deployment

### Streamlit Community Cloud
1. Push this repo to GitHub
2. Go to share.streamlit.io
3. Deploy `app.py`

### Docker
```bash
docker build -t listingforge .
docker run -p 8501:8501 listingforge
```

### Railway / Render / Fly.io
Works out of the box with the included `requirements.txt` and `Dockerfile`.

## Tech Notes

- Pure Python + Streamlit
- SQLite for history (swap to Postgres for multi-user)
- No external API keys required for core functionality
- Category-aware language banks for jewelry, home decor, apparel, art, beauty, digital products

## Roadmap Ideas (High ROI)

- [ ] Stripe + usage limits
- [ ] User accounts / teams
- [ ] Real LLM backend (feature flag)
- [ ] Etsy / Shopify API one-click publish
- [ ] Competitor listing analyzer
- [ ] Image SEO suggestions

## License

MIT — do whatever you want with it. Sell it, rebrand it, open-source it, keep it private.

---

Built as a complete, sellable product.  
Now go ship it and make money.
