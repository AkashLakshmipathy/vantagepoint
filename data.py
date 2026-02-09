"""
VantagePoint — data layer: GDELT, NewsAPI, RSS, Gemini API, mock events.
"""

import json
import os
import random
import re
import requests
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
import google.generativeai as genai

try:
    import feedparser
except ImportError:
    feedparser = None

from config import (
    GDELT_URL,
    GDELT_KEYWORDS,
    MAX_GDELT_RECORDS,
    GEMINI_MODEL,
    NEWSAPI_BASE_URL,
    NEWSAPI_PAGE_SIZE,
    NEWSAPI_KEYWORDS,
    NEWSAPI_SORT_BY,
    NEWSAPI_RELEVANCE_KEYWORDS,
    NEWSAPI_MIN_RELEVANCE,
    RSS_FEEDS,
    MAX_RSS_ENTRIES_PER_FEED,
)


def _category_from_title(title: str) -> str:
    """Heuristic: infer supply-chain category from headline."""
    t = (title or "").lower()
    if "cement" in t or "steel" in t or "lumber" in t or "infrastructure" in t:
        return "Construction"
    if "strike" in t or "port" in t or "congestion" in t or "canal" in t or "blockade" in t:
        return "Disruption"
    if "shortage" in t:
        return "Shortage"
    if "factory" in t or "fab" in t or "assembly" in t:
        return "Manufacturing"
    if "sanction" in t or "trade" in t or "export" in t:
        return "Geopolitical"
    return "General"


def _event_row(headline: str, snippet: str, source: str, source_url: str, timestamp: str, risk_score: int = 0) -> dict:
    """Build one event row in our standard schema (with placeholder lat/lon)."""
    return {
        "timestamp": timestamp,
        "headline": (headline or "Unknown Event").strip()[:500],
        "location": "Global Signal (Live)",
        "latitude": random.uniform(-45, 55),
        "longitude": random.uniform(-130, 150),
        "risk_score": risk_score,
        "category": _category_from_title(headline),
        "commodity": "Mixed",
        "reasoning": "",
        "article_snippet": (snippet or headline or "")[:200],
        "source_url": source_url or "#",
        "source": source or "Live",
        "gemini_analysis": None,
    }


def _supply_chain_relevance(text: str) -> int:
    """Count how many supply-chain keywords appear in text (case-insensitive)."""
    if not text:
        return 0
    t = text.lower()
    return sum(1 for kw in (NEWSAPI_RELEVANCE_KEYWORDS or []) if kw.lower() in t)


def _heuristic_risk_from_text(title: str, description: str) -> int:
    """Assign 1-5 risk for NewsAPI articles from keywords (so we avoid showing 0)."""
    t = (title or "") + " " + (description or "")
    t = t.lower()
    if any(w in t for w in ["strike", "shortage", "blockade", "outage", "closure", "crisis"]):
        return min(5, 4)
    if any(w in t for w in ["disruption", "delay", "backlog", "congestion"]):
        return 3
    if any(w in t for w in ["supply chain", "logistics", "shipping", "freight", "port", "cargo"]):
        return 2
    return 1


@st.cache_data(ttl=600, show_spinner=False)
def fetch_gdelt_events(
    query: str = GDELT_KEYWORDS,
    max_records: int = MAX_GDELT_RECORDS,
) -> pd.DataFrame:
    """Fetch global news events from GDELT API (last 48h). Returns structured DataFrame or empty on error."""
    try:
        url = f"{GDELT_URL}?query={query}&mode=artlist&format=json&maxrecords={max_records}&timespan=48h"
        response = requests.get(url, timeout=15)
        if response.status_code == 429:
            st.sidebar.warning(
                "GDELT rate limit (429 Too Many Requests). Use **Mock** data for now, or try again in 10–15 minutes."
            )
            return pd.DataFrame()
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])
        if not articles:
            return pd.DataFrame()

        rows = []
        for art in articles:
            title = (art.get("title") or "Unknown Event").strip()
            snippet = (art.get("snippet") or title)[:200]
            domain = art.get("domain", "GDELT")
            url_link = art.get("url", "#")
            seendate = art.get("seendate", datetime.now().strftime("%Y%m%d"))
            ts = seendate[:8] + " " + (seendate[8:10] + ":" + seendate[10:12] if len(seendate) >= 12 else "00:00")

            rows.append(_event_row(title, snippet, domain, url_link, ts))
        return pd.DataFrame(rows)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            st.sidebar.warning("GDELT rate limit (429). Use **Mock** data or try again later.")
        else:
            st.sidebar.warning(f"GDELT error: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.warning(f"GDELT unreachable: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_newsapi_events(api_key: str, query: str = NEWSAPI_KEYWORDS) -> pd.DataFrame:
    """Fetch supply-chain–focused articles from NewsAPI; filter by relevance and assign heuristic risk."""
    if not api_key or not api_key.strip():
        return pd.DataFrame()
    try:
        url = f"{NEWSAPI_BASE_URL}?q={quote_plus(query)}&pageSize={NEWSAPI_PAGE_SIZE}&sortBy={NEWSAPI_SORT_BY}&language=en&apiKey={api_key.strip()}"
        response = requests.get(url, timeout=12)
        if response.status_code == 429:
            return pd.DataFrame()
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles") or []
        rows = []
        for art in articles:
            if not art.get("title"):
                continue
            title = art.get("title", "")
            desc = art.get("description") or title
            combined = f"{title} {desc}"
            relevance = _supply_chain_relevance(combined)
            if relevance < NEWSAPI_MIN_RELEVANCE:
                continue
            src = (art.get("source") or {}).get("name") or "NewsAPI"
            link = art.get("url") or "#"
            pub = art.get("publishedAt") or ""
            if pub:
                try:
                    pub = re.sub(r"T(\d{2}):(\d{2}).*", r" \1:\2", pub[:16]) if "T" in pub else pub[:16]
                except Exception:
                    pass
            else:
                pub = datetime.now().strftime("%Y-%m-%d %H:%M")
            risk = _heuristic_risk_from_text(title, desc)
            rows.append(_event_row(title, desc, src, link, pub, risk_score=risk))
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def fetch_rss_events() -> pd.DataFrame:
    """Fetch recent entries from configured RSS feeds (logistics/supply chain). No API key."""
    if not feedparser:
        return pd.DataFrame()
    rows = []
    for feed_url in (RSS_FEEDS or []):
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": "VantagePoint/1.0"})
            entries = (feed.get("entries") or [])[:MAX_RSS_ENTRIES_PER_FEED]
            for e in entries:
                title = e.get("title") or ""
                if not title:
                    continue
                raw = e.get("summary") or e.get("description") or title
                if hasattr(raw, "get"):
                    summary = (raw.get("value") if isinstance(raw, dict) else str(raw))[:200]
                else:
                    summary = (str(raw) or "")[:200]
                link = e.get("link") or "#"
                published = e.get("published") or e.get("updated") or ""
                try:
                    if published and hasattr(e, "published_parsed") and e.published_parsed:
                        t = e.published_parsed
                        published = f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}"
                except Exception:
                    published = published[:16] if published else datetime.now().strftime("%Y-%m-%d %H:%M")
                source = (feed.get("feed") or {}).get("title") or feed_url
                rows.append(_event_row(title, summary, source, link, published))
        except Exception:
            continue
    return pd.DataFrame(rows)


def get_live_events() -> pd.DataFrame:
    """
    Try multiple live sources in order: GDELT -> NewsAPI (if key set) -> RSS.
    Returns first non-empty DataFrame, or empty (caller can fall back to Mock).
    """
    df = fetch_gdelt_events()
    if not df.empty:
        return df
    newsapi_key = os.environ.get("NEWSAPI_API_KEY", "").strip()
    if newsapi_key:
        df = fetch_newsapi_events(newsapi_key)
        if not df.empty:
            st.sidebar.info("Using **NewsAPI** (GDELT was empty or rate-limited).")
            return df
    df = fetch_rss_events()
    if not df.empty:
        st.sidebar.info("Using **RSS** feeds (GDELT/NewsAPI unavailable).")
        return df
    return pd.DataFrame()


def analyze_with_gemini(event: dict, api_key: str) -> dict:
    """
    Call Gemini to analyze a supply chain event. Returns enriched event dict with
    risk_score, category, gemini_analysis (full JSON), or original event on error.
    """
    if not api_key or not api_key.strip():
        return event

    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(GEMINI_MODEL)

        title = event.get("headline", event.get("title", ""))
        location = event.get("location", "Unknown")
        snippet = event.get("article_snippet", event.get("snippet", ""))

        prompt = f"""
Analyze this supply chain event:

Headline: {title}
Location: {location}
Summary: {snippet}

Provide structured JSON only, no markdown:
{{
  "risk_score": <integer 1-10>,
  "category": "Disruption" | "Construction" | "Shortage" | "Manufacturing" | "Geopolitical",
  "affected_industries": ["industry1", "industry2", "industry3"],
  "geographic_ripple": ["country1", "country2"],
  "timeline": {{
    "short_term": "1-7 days prediction",
    "medium_term": "1-4 weeks prediction",
    "long_term": "1-6 months prediction"
  }},
  "reasoning": "2-3 sentence explanation",
  "actionable_intelligence": "What to monitor next",
  "is_construction_related": true or false,
  "construction_prediction": "What's being built" or null
}}
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json"),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        analysis = json.loads(text)

        event = event.copy()
        event["risk_score"] = min(10, max(1, int(analysis.get("risk_score", 5))))
        event["category"] = analysis.get("category", event.get("category", "General"))
        event["gemini_analysis"] = analysis
        event["reasoning"] = analysis.get("reasoning", "")
        return event
    except json.JSONDecodeError as e:
        event = event.copy()
        event["gemini_analysis"] = {"error": f"JSON parse failed: {e}", "reasoning": ""}
        return event
    except Exception as e:
        event = event.copy()
        event["gemini_analysis"] = {"error": str(e), "reasoning": ""}
        return event


def _events_context_for_gemini(events_df: pd.DataFrame, max_events: int = 20) -> str:
    """Build a compact text summary of events for Gemini prompts (multi-event reasoning)."""
    if events_df.empty:
        return "No events in the current view."
    subset = events_df.head(max_events)
    lines = []
    for _, row in subset.iterrows():
        h = row.get("headline", "?")
        r = row.get("risk_score", 0)
        c = row.get("category", "?")
        loc = row.get("location", "?")
        lines.append(f"- [{r}/10] {h} | {c} | {loc}")
    return "\n".join(lines)


def get_executive_brief(events_df: pd.DataFrame, api_key: str) -> dict:
    """
    Use Gemini to synthesize all visible events into an executive summary and top 3 risks.
    Returns {"summary": str, "top_risks": list[str]} or {"error": str}.
    """
    if not api_key or not api_key.strip():
        return {"error": "No API key"}
    if events_df.empty:
        return {"summary": "No events to summarize.", "top_risks": []}

    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(GEMINI_MODEL)
        context = _events_context_for_gemini(events_df)

        prompt = f"""You are a supply chain intelligence analyst. Based on these current signals, write a brief executive brief.

CURRENT EVENTS (headline | risk/10 | category | location):
{context}

Respond in this exact format (use the section headers):
EXECUTIVE SUMMARY:
[2-4 sentences: overall supply chain picture and what stands out.]

TOP 3 RISKS TO WATCH:
1. [First risk with one sentence]
2. [Second risk with one sentence]
3. [Third risk with one sentence]
"""

        response = model.generate_content(prompt)
        text = (response.text or "").strip()

        summary = ""
        top_risks = []
        if "EXECUTIVE SUMMARY:" in text and "TOP 3 RISKS" in text:
            parts = text.split("TOP 3 RISKS TO WATCH:")
            summary = parts[0].replace("EXECUTIVE SUMMARY:", "").strip()
            risks_block = parts[1].strip() if len(parts) > 1 else ""
            for line in risks_block.split("\n"):
                line = line.strip()
                if line and line[0].isdigit():
                    top_risks.append(line.lstrip("0123456789.)- ").strip())
        else:
            summary = text
        return {"summary": summary or text, "top_risks": top_risks[:3]}
    except Exception as e:
        return {"error": str(e), "summary": "", "top_risks": []}


def ask_gemini_about_data(events_df: pd.DataFrame, question: str, api_key: str) -> str:
    """
    Let the user ask a natural-language question about the current event data; Gemini answers in context.
    """
    if not api_key or not api_key.strip():
        return "Please set a Gemini API key in the sidebar."
    if not question or not question.strip():
        return "Please enter a question."

    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(GEMINI_MODEL)
        context = _events_context_for_gemini(events_df)

        prompt = f"""You are a supply chain intelligence analyst. Answer the user's question using ONLY the following current events. Be concise (2-5 sentences). If the data doesn't support an answer, say so.

CURRENT EVENTS (risk/10, headline, category, location):
{context}

USER QUESTION: {question.strip()}

ANSWER:"""

        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        return f"Error: {e}"


def _mock_events_template(base_time: datetime) -> list[dict]:
    """Build 25 mock event dicts with timestamps. Used by generate_mock_data."""
    ts = lambda: (base_time - timedelta(hours=random.randint(1, 24))).strftime("%Y-%m-%d %H:%M")
    return [
        {"timestamp": ts(), "headline": "Massive Cement Orders for New Zone in Haiphong", "location": "Haiphong, Vietnam", "latitude": 20.8449, "longitude": 106.6881, "risk_score": 2, "category": "Construction", "commodity": "Cement", "reasoning": "Large cement inflows typically precede major infrastructure or industrial zone development.", "article_snippet": "Vietnamese port data shows a 40% spike in cement imports destined for Haiphong, signaling new development zone.", "source_url": "https://example.com/haiphong-cement", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Steel Shipment Surge to Neom Project", "location": "Tabuk, Saudi Arabia", "latitude": 28.3835, "longitude": 36.5662, "risk_score": 3, "category": "Construction", "commodity": "Steel", "reasoning": "Neom megaproject drives sustained steel demand; supply chain is stable but high volume.", "article_snippet": "Steel deliveries to Red Sea ports for Neom have doubled in Q1, with no immediate disruption risk.", "source_url": "https://example.com/neom-steel", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Lumber Stockpiling Detected in Texas Port", "location": "Houston, USA", "latitude": 29.7604, "longitude": -95.3698, "risk_score": 4, "category": "Construction", "commodity": "Lumber", "reasoning": "Pre-hurricane or pre-development stockpiling; monitor for demand spikes in housing.", "article_snippet": "Houston port logs show unusual lumber inventory build-up, possibly for residential or commercial projects.", "source_url": "https://example.com/houston-lumber", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "New Battery Plant Foundation Laid", "location": "Debrecen, Hungary", "latitude": 47.5316, "longitude": 21.6273, "risk_score": 2, "category": "Construction", "commodity": "Concrete", "reasoning": "EV supply chain expansion in Europe; concrete and steel flows confirm construction phase.", "article_snippet": "Major EV battery facility construction begins in Debrecen with concrete and steel deliveries ramping.", "source_url": "https://example.com/debrecen-battery", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Copper Wiring Imports Spike 400%", "location": "Chennai, India", "latitude": 13.0827, "longitude": 80.2707, "risk_score": 3, "category": "Construction", "commodity": "Copper", "reasoning": "Data center and grid expansion in India driving copper demand; supply adequate.", "article_snippet": "Chennai port reports a 400% increase in copper wiring imports over previous quarter.", "source_url": "https://example.com/chennai-copper", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Infrastructure Expansion: Bridge Materials Arriving", "location": "Lagos, Nigeria", "latitude": 6.5244, "longitude": 3.3792, "risk_score": 5, "category": "Construction", "commodity": "Steel", "reasoning": "Major infrastructure project in Lagos; geopolitical and logistics risks moderate.", "article_snippet": "Steel and concrete shipments for new bridge and road projects are arriving at Lagos port.", "source_url": "https://example.com/lagos-bridge", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Port Strike Threatens West Coast Logistics", "location": "Los Angeles, USA", "latitude": 34.0522, "longitude": -118.2437, "risk_score": 9, "category": "Disruption", "commodity": "General Cargo", "reasoning": "Labor action at major port will delay container flows and increase lead times across sectors.", "article_snippet": "Union vote authorizes strike at LA/Long Beach; shippers brace for delays.", "source_url": "https://example.com/la-strike", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Panama Canal Drought Restricts Draft", "location": "Panama City, Panama", "latitude": 8.9824, "longitude": -79.5199, "risk_score": 8, "category": "Disruption", "commodity": "All", "reasoning": "Draft restrictions reduce capacity and increase transit times for Asia–US East routes.", "article_snippet": "Canal authority limits vessel draft due to drought; some cargo must reroute.", "source_url": "https://example.com/panama-canal", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Typhoon Warnings Halt Shipping Lanes", "location": "Manila, Philippines", "latitude": 14.5995, "longitude": 120.9842, "risk_score": 7, "category": "Disruption", "commodity": "Electronics", "reasoning": "Weather-related port closures will delay electronics and component shipments.", "article_snippet": "Typhoon forces closure of Manila port; shipping lanes suspended for 48h.", "source_url": "https://example.com/manila-typhoon", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Railway Union Protest Blocks Freight", "location": "Hamburg, Germany", "latitude": 53.5511, "longitude": 9.9937, "risk_score": 6, "category": "Disruption", "commodity": "Auto Parts", "reasoning": "Rail blockades in Germany affect inland distribution of auto and industrial parts.", "article_snippet": "Protest action blocks key rail lines; automotive supply chain impacted.", "source_url": "https://example.com/hamburg-rail", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Customs System Outage Delays Clearance", "location": "Felixstowe, UK", "latitude": 51.9617, "longitude": 1.3513, "risk_score": 5, "category": "Disruption", "commodity": "Retail Goods", "reasoning": "IT outage at major UK port causes clearance delays; expected short-term.", "article_snippet": "Customs system failure at Felixstowe leads to container backlog.", "source_url": "https://example.com/felixstowe", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Chip Fab Contamination Halts Production", "location": "Hsinchu, Taiwan", "latitude": 24.8138, "longitude": 120.9675, "risk_score": 9, "category": "Manufacturing", "commodity": "Semiconductors", "reasoning": "Fab contamination can cause multi-week shutdowns and ripple through electronics supply.", "article_snippet": "Major semiconductor fab in Hsinchu halts production due to contamination incident.", "source_url": "https://example.com/hsinchu-fab", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Foxconn Factory Power Outage", "location": "Zhengzhou, China", "latitude": 34.7466, "longitude": 113.6253, "risk_score": 7, "category": "Manufacturing", "commodity": "Consumer Electronics", "reasoning": "Power issues at key assembly site risk smartphone and device delivery delays.", "article_snippet": "Power outage at Foxconn Zhengzhou facility disrupts production lines.", "source_url": "https://example.com/foxconn", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Auto Assembly Line Paused Missing Parts", "location": "Wolfsburg, Germany", "latitude": 52.4227, "longitude": 10.7865, "risk_score": 6, "category": "Manufacturing", "commodity": "Automotive", "reasoning": "Component shortage forces line stoppage; reinforces need for dual sourcing.", "article_snippet": "VW Wolfsburg pauses assembly due to missing components from Asia.", "source_url": "https://example.com/wolfsburg", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Textile Mill Fire Impacts Holiday Orders", "location": "Dhaka, Bangladesh", "latitude": 23.8103, "longitude": 90.4125, "risk_score": 5, "category": "Manufacturing", "commodity": "Textiles", "reasoning": "Fire at single facility; apparel brands may shift orders to other suppliers.", "article_snippet": "Fire at major textile mill in Dhaka raises concerns for holiday apparel supply.", "source_url": "https://example.com/dhaka-textile", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Critical Neon Gas Shortage for Lasers", "location": "Odessa, Ukraine", "latitude": 46.4825, "longitude": 30.7233, "risk_score": 8, "category": "Shortage", "commodity": "Neon Gas", "reasoning": "Neon is critical for chip lithography; shortage from Ukraine affects semiconductor production.", "article_snippet": "Neon gas supply from Ukraine remains constrained; chip makers seek alternatives.", "source_url": "https://example.com/neon-ukraine", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Cocoa Bean Supply Drop Hits Chocolate Makers", "location": "Abidjan, Ivory Coast", "latitude": 5.36, "longitude": -4.0083, "risk_score": 4, "category": "Shortage", "commodity": "Food", "reasoning": "Weather and disease reduce cocoa output; chocolate and confectionery costs to rise.", "article_snippet": "Cocoa harvest in Ivory Coast falls short; chocolate manufacturers warn of price increases.", "source_url": "https://example.com/cocoa", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Lithium Pricing Surge Signals Scarcity", "location": "Antofagasta, Chile", "latitude": -23.6509, "longitude": -70.3975, "risk_score": 6, "category": "Shortage", "commodity": "Lithium", "reasoning": "Lithium demand for EVs outstrips supply; battery and EV production at risk.", "article_snippet": "Lithium prices hit new highs as demand from EV sector continues to grow.", "source_url": "https://example.com/lithium", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "New Sanctions Block Tech Exports", "location": "Moscow, Russia", "latitude": 55.7558, "longitude": 37.6173, "risk_score": 8, "category": "Geopolitical", "commodity": "Technology", "reasoning": "Export controls will disrupt tech supply chains and force redesign of sourcing.", "article_snippet": "Latest sanctions prohibit export of advanced chips and equipment to Russia.", "source_url": "https://example.com/sanctions-tech", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Trade Route Blockade in Red Sea", "location": "Suez, Egypt", "latitude": 29.9668, "longitude": 32.5498, "risk_score": 9, "category": "Geopolitical", "commodity": "Oil/Gas", "reasoning": "Red Sea attacks force rerouting via Cape; longer transit and higher freight costs.", "article_snippet": "Persistent attacks force major carriers to avoid Red Sea; Suez traffic drops.", "source_url": "https://example.com/red-sea", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Rare Earth Export Restrictions Announced", "location": "Beijing, China", "latitude": 39.9042, "longitude": 116.4074, "risk_score": 7, "category": "Geopolitical", "commodity": "Rare Earths", "reasoning": "Export curbs on rare earths affect magnets and EV/high-tech manufacturing globally.", "article_snippet": "China announces new export controls on rare earth elements and processing tech.", "source_url": "https://example.com/rare-earth", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Earthquake Damages Port Infrastructure", "location": "Istanbul, Turkey", "latitude": 41.0082, "longitude": 28.9784, "risk_score": 7, "category": "Disruption", "commodity": "General Cargo", "reasoning": "Port damage from quake disrupts Black Sea and Mediterranean logistics.", "article_snippet": "Strong earthquake causes damage to port facilities; operations partially suspended.", "source_url": "https://example.com/istanbul-quake", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "Flooding Closes Key Highway to Port", "location": "Vancouver, Canada", "latitude": 49.2827, "longitude": -123.1207, "risk_score": 6, "category": "Disruption", "commodity": "Lumber", "reasoning": "Highway closure blocks trucking to port; lumber and grain exports delayed.", "article_snippet": "Flooding on Trans-Canada Highway disrupts cargo movement to Vancouver port.", "source_url": "https://example.com/vancouver-flood", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "RETROSPECTIVE: Unusual Spike in Medical Glove Exports", "location": "Wuhan, China", "latitude": 30.5928, "longitude": 114.3055, "risk_score": 10, "category": "Shortage", "commodity": "Medical Supplies", "reasoning": "Historical signal: Dec 2019 medical supply spikes preceded COVID-19 pandemic.", "article_snippet": "RETROSPECTIVE: Data showed abnormal medical glove and PPE exports from Wuhan in late 2019.", "source_url": "https://example.com/wuhan-retro", "source": "Global News Wire"},
        {"timestamp": ts(), "headline": "RETROSPECTIVE: Ventilator Parts Orders Triple", "location": "Lombardy, Italy", "latitude": 45.4642, "longitude": 9.19, "risk_score": 9, "category": "Shortage", "commodity": "Medical Devices", "reasoning": "Historical signal: Surge in ventilator parts orders preceded severe COVID wave in Italy.", "article_snippet": "RETROSPECTIVE: Ventilator and ICU equipment orders spiked in Lombardy in early 2020.", "source_url": "https://example.com/lombardy-retro", "source": "Global News Wire"},
    ]


@st.cache_data(show_spinner=False)
def generate_mock_data() -> pd.DataFrame:
    """Generate 25 realistic supply chain events for demo (no API keys required)."""
    return pd.DataFrame(_mock_events_template(datetime.now()))
