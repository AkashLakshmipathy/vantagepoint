"""
VantagePoint — configuration and constants.
Gemini 3 Hackathon (https://gemini3.devpost.com)
"""

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# Optional: paste API keys here for local run only. Do NOT commit real keys to a public repo.
# Prefer using .env (gitignored) or Streamlit Cloud Secrets instead.
GEMINI_API_KEY = ""   # e.g. "AIzaSy..."
NEWSAPI_API_KEY = ""  # e.g. "abc123..."

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GEMINI_MODEL = "gemini-3-flash-preview"
GDELT_KEYWORDS = "port strike OR factory OR shortage OR cement OR steel OR infrastructure OR supply chain"
MAX_GDELT_RECORDS = 25  # Lower to reduce rate-limit risk; GDELT can return 429

# NewsAPI.org fallback when GDELT is rate-limited or empty (optional; set NEWSAPI_API_KEY)
NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"
NEWSAPI_PAGE_SIZE = 50   # fetch more, then filter by relevance
NEWSAPI_KEYWORDS = '"supply chain" OR logistics OR "shipping" OR freight OR "port" OR "cargo" OR "shortage" OR "supply shortage" OR "factory" OR "disruption" OR "visibility"'
NEWSAPI_SORT_BY = "relevance"  # prefer relevance over publishedAt for better targeting
# Keywords used to score/filter NewsAPI results (must match at least one to keep)
NEWSAPI_RELEVANCE_KEYWORDS = [
    "supply chain", "logistics", "shipping", "freight", "cargo", "port", "shortage",
    "disruption", "strike", "factory", "manufacturing", "inventory", "shipment",
    "supplier", "procurement", "warehouse", "distribution", "export", "import",
    "container", "rail", "trucking", "delivery", "outage", "closure", "backlog",
]
NEWSAPI_MIN_RELEVANCE = 1  # keep only articles with at least this many keyword matches

# RSS feeds for logistics/supply chain news (no key required)
RSS_FEEDS = [
    "https://feeds.feedburner.com/logisticsmgmt/latest",
    "https://theloadstar.com/feed/",
]
MAX_RSS_ENTRIES_PER_FEED = 15

# ---------------------------------------------------------------------------
# UI (CSS)
# ---------------------------------------------------------------------------
PAGE_TITLE = "VantagePoint | Supply Chain Intelligence"
PAGE_ICON = "🌐"

CUSTOM_CSS = """
<style>
    .vantage-header {
        font-size: 2rem;
        font-weight: 700;
        color: #0ea5e9;
        margin-bottom: 0.25rem;
    }
    .vantage-tagline {
        color: #64748b;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 1rem; border-radius: 10px; border: 1px solid #334155; }
    .risk-high { color: #ef4444; font-weight: bold; }
    .risk-med { color: #f59e0b; font-weight: bold; }
    .risk-low { color: #22c55e; font-weight: bold; }
    .event-detail-box { background: #1e293b; padding: 1rem; border-radius: 8px; border-left: 4px solid #0ea5e9; margin: 0.5rem 0; }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #0ea5e9, #06b6d4); }
</style>
"""
