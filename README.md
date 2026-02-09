# VantagePoint — Supply Chain Intelligence Engine

Predicting tomorrow through supply chains. VantagePoint tracks global supply chain signals (construction materials, disruptions, shortages) and uses **Google Gemini** to turn raw events into risk scores, timeline predictions, and actionable intelligence.

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

- **No API key needed** for the full demo: use **Mock** data in the sidebar. The map, dashboard, and event table all work.
- **Gemini analysis:** Set `GEMINI_API_KEY` in your environment (or paste in sidebar) and click **"Analyze with Gemini"** on any event to get AI-powered risk analysis.

---

## Tech stack

- **Google Gemini API** — event analysis and structured JSON output (Gemini 3 Pro model)
- **Streamlit** — UI and dashboard
- **Live data** — GDELT (primary), NewsAPI (fallback), RSS (fallback); see [Data sources](#data-sources) below
- **Pydeck** — 3D map (free Carto tiles; no Mapbox)
- **Plotly** — charts and health gauge

---

## Data sources

When you select **Live** in the sidebar, the app pulls supply-chain-related **news signals** from up to three sources in order:

| Source | What it is | Key required? | Role |
|--------|------------|----------------|------|
| **GDELT** | Global news from the last **48 hours** matching keywords (port strike, cement, shortage, supply chain, etc.) | No | Primary; free but can return 429 (rate limit). |
| **NewsAPI.org** | Search over recent articles (same keywords). | Yes (`NEWSAPI_API_KEY`) | Fallback when GDELT is empty or rate-limited. [Get a key](https://newsapi.org/register). |
| **RSS** | Curated logistics/supply chain feeds (e.g. Logistics Management, The Loadstar). | No | Fallback when GDELT and NewsAPI yield nothing. |

**“Live” means:** recent news (roughly 48h for GDELT/NewsAPI, latest items for RSS). We use these as **signals** (headlines/snippets); **Gemini** then interprets them into risk scores, categories, and implications. This is not real-time vessel or trade data—it’s news-based early warning.

**Optional:** Set `NEWSAPI_API_KEY` in your environment (or in Streamlit Cloud secrets) so that when GDELT is unavailable, Live mode can use NewsAPI. Without it, Live still tries GDELT then RSS.

---

## Third-party integrations

This project uses the following third-party tools and data, in accordance with their respective terms and licensing:

- **Google Gemini API** — [Google AI / Gemini terms](https://ai.google.dev/terms)
- **GDELT** — [GDELT Project](https://www.gdeltproject.org/) news/events API (no key; rate limits apply)
- **NewsAPI.org** — [NewsAPI](https://newsapi.org/) (optional fallback; key required; terms on site)
- **RSS feeds** — Logistics Management, The Loadstar (public feeds; no key)
- **Streamlit** — [Apache 2.0](https://github.com/streamlit/streamlit)
- **Plotly** — [MIT](https://github.com/plotly/plotly.py)
- **Pydeck / Carto** — map tiles from [Carto](https://carto.com/) (free tier; no API key required)

All are used with authorization and in compliance with their terms. This disclosure should be included in your hackathon submission description where third-party integrations are requested.

---

## Gemini integration (for submission write-up)

**Brief description (~200 words) for the contest form.** Aligns with [Gemini 3 Hackathon](https://gemini3.devpost.com/rules) requirements:

> VantagePoint uses the **Gemini API** as the core intelligence layer for supply chain risk analysis (Gemini 3 Hackathon). When a user selects an event from the Signal Intelligence Feed and clicks **"Analyze with Gemini,"** the app sends the event’s headline, location, and summary to the Gemini API via the Google Generative AI SDK.
>
> **Gemini features used:** **(1) Per-event structured output** — we request JSON-only responses using `response_mime_type="application/json"`, so the model returns a parseable schema with risk_score, category, affected_industries, geographic_ripple, timeline predictions (short-, medium-, and long-term), reasoning, actionable_intelligence, and construction-related flags. **(2) Multi-event synthesis** — The **AI Executive Brief** sends the full visible event list to Gemini for an executive summary and top 3 risks. **(3) Conversational QA** — **Ask Gemini about this data** lets users ask questions in plain English; Gemini answers from the current event context. **(4) Domain reasoning** — Gemini acts as a logistics expert, interpreting each event in context and producing risk scores (1–10), downstream implications, and what to monitor next.
>
> Gemini is **central**: the dashboard surfaces signals; the API delivers structured analysis, executive-level synthesis, and on-demand Q&A. Mock mode works without a key; with a Gemini API key, judges can use all features.

---

**Testing:** The project is made available free of charge and without restriction for testing, evaluation, and use by judges until the Judging Period ends (per contest rules).

---
