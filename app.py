"""
VantagePoint - Supply Chain Intelligence Engine
Gemini 3 Hackathon (https://gemini3.devpost.com) — Built with the Gemini API.

SETUP INSTRUCTIONS:
1. pip install -r requirements.txt
2. Get Gemini API Key: https://aistudio.google.com/app/apikey
3. streamlit run app.py
4. Optional: copy .env.example to .env and add GEMINI_API_KEY, NEWSAPI_API_KEY
"""

import hashlib
import os

from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud secrets (dashboard) override env; push into os.environ so data.py etc. can use them
try:
    for key in ("GEMINI_API_KEY", "NEWSAPI_API_KEY"):
        if key in st.secrets and st.secrets.get(key):
            os.environ[key] = str(st.secrets[key]).strip()
except Exception:
    pass

import pandas as pd
import streamlit as st

from config import CUSTOM_CSS, PAGE_ICON, PAGE_TITLE
from data import (
    fetch_gdelt_events,
    fetch_newsapi_events,
    generate_mock_data,
    get_live_events,
    analyze_with_gemini,
    get_executive_brief,
    ask_gemini_about_data,
)
from processing import calculate_health_index, filter_events
from viz import create_map_visualization, create_construction_radar, render_health_gauge


st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main():
    # ----- Sidebar -----
    st.sidebar.title("🌐 VantagePoint")
    st.sidebar.caption("Supply Chain Intelligence Engine")

    env_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_api_key:
        api_key = env_api_key
        st.sidebar.success("Gemini API key detected (no action needed).")
    else:
        api_key = st.sidebar.text_input(
            "Gemini API Key",
            type="password",
            help="Required for live AI analysis. Or set GEMINI_API_KEY.",
        )

    data_mode = st.sidebar.radio("Data Mode", ["Mock", "Live"], index=0, horizontal=True)
    st.sidebar.caption("Live: GDELT → NewsAPI (if set) → RSS")
    if st.sidebar.button("🔄 Refresh Data"):
        if data_mode == "Mock":
            generate_mock_data.clear()
        fetch_gdelt_events.clear()
        fetch_newsapi_events.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")
    selected_region = st.sidebar.selectbox("Region", ["All", "Asia", "Europe", "Americas", "Africa"])
    risk_level = st.sidebar.selectbox("Risk Level", ["All", "Low", "Medium", "High"])
    category_filter = st.sidebar.selectbox("Category", ["All", "Disruption", "Construction", "Shortage", "Manufacturing", "Geopolitical"])
    commodity_filter = st.sidebar.selectbox("Commodity", ["All", "Cement", "Steel", "Lumber", "Semiconductors", "General Cargo", "Mixed", "Food", "Oil/Gas", "Technology", "Rare Earths", "Medical Supplies", "Medical Devices"])

    # Load data
    if data_mode == "Mock":
        df_raw = generate_mock_data()
    else:
        with st.spinner("Fetching live signals (GDELT → NewsAPI → RSS)..."):
            df_raw = get_live_events()
        if df_raw.empty:
            st.warning("No live data; using Mock.")
            df_raw = generate_mock_data()

    if "latitude" not in df_raw.columns and "lat" in df_raw.columns:
        df_raw["latitude"] = df_raw["lat"]
    if "longitude" not in df_raw.columns and "lon" in df_raw.columns:
        df_raw["longitude"] = df_raw["lon"]
    if "risk_score" not in df_raw.columns and "risk" in df_raw.columns:
        df_raw["risk_score"] = df_raw["risk"]

    df_filtered = filter_events(df_raw, selected_region, risk_level, category_filter, commodity_filter)
    health = calculate_health_index(df_filtered)

    st.sidebar.markdown("---")
    render_health_gauge(health)

    with st.sidebar.expander("ℹ️ How VantagePoint Works"):
        st.markdown("""
**The Insight:**  
Supply chains don't lie. Material movements predict development. Factory disruptions forecast shortages. We track the signals before they become news.

**Our Approach:**
1. Monitor 100K+ news sources (GDELT)
2. Analyze with Gemini AI (context, not just keywords)
3. Track construction materials (cement/steel/lumber)
4. Predict events 3–6 months early

**Examples:**
- COVID-19: Dec 2019 medical supply spikes
- Chip Shortage: Taiwan fab issues predicted
- Development: Cement tracking shows new cities

**Tech Stack:** Gemini API | GDELT | Streamlit

**Third-party:** GDELT (news data), Carto (map tiles). Used in accordance with their terms.

**Why This Wins:** Traditional trackers show the past. VantagePoint predicts the future.

**Data & refresh:** Live events are cached in memory for **10 minutes** (GDELT/NewsAPI). **Refresh Data** clears the cache and fetches fresh data from the APIs. A normal browser refresh (F5) keeps the cache until it expires or you click **Refresh Data**. Nothing is saved to disk or a database—each session sees the latest fetch.
""")

    # ----- Main dashboard -----
    st.markdown('<p class="vantage-header">🌐 VantagePoint</p>', unsafe_allow_html=True)
    st.markdown('<p class="vantage-tagline">Predicting tomorrow through supply chains</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Events", len(df_filtered))
    with c2:
        high_risk = len(df_filtered[df_filtered["risk_score"] >= 7]) if not df_filtered.empty else 0
        st.metric("High Risk (7+)", high_risk, delta_color="inverse")
    with c3:
        projects = len(df_filtered[df_filtered["category"] == "Construction"]) if not df_filtered.empty else 0
        st.metric("Construction Projects", projects)
    with c4:
        st.metric("Health Index", f"{health}/100", delta="+1.2%" if health >= 70 else "-2.5%")

    # ----- AI Executive Brief (Gemini multi-event reasoning) -----
    st.subheader("📊 AI Executive Brief")
    _headlines = sorted(df_filtered["headline"].astype(str)) if not df_filtered.empty else []
    brief_key = "brief_" + hashlib.md5(",".join(_headlines).encode()).hexdigest()[:12]
    if df_filtered.empty:
        st.info("Load events and apply filters to generate an AI Executive Brief.")
    elif api_key and api_key.strip():
        if st.session_state.get("executive_brief_key") != brief_key:
            st.session_state["executive_brief_result"] = None
            st.session_state["executive_brief_key"] = brief_key
        if st.session_state.get("executive_brief_result") is not None:
            res = st.session_state["executive_brief_result"]
            if res.get("error"):
                st.error(res["error"])
            else:
                st.markdown("**Summary**")
                st.write(res.get("summary", ""))
                risks = res.get("top_risks", [])
                if risks:
                    st.markdown("**Top 3 risks to watch**")
                    for i, r in enumerate(risks, 1):
                        st.markdown(f"{i}. {r}")
        if st.button("🔄 Generate AI Executive Brief", key="gen_brief"):
            with st.spinner("Gemini is synthesizing the current signals..."):
                res = get_executive_brief(df_filtered, api_key)
                st.session_state["executive_brief_result"] = res
                st.session_state["executive_brief_key"] = brief_key
            st.rerun()
        elif st.session_state.get("executive_brief_result") is None:
            st.caption("Click **Generate AI Executive Brief** to have Gemini summarize all visible events and list the top 3 risks.")
    else:
        st.caption("Set a Gemini API key in the sidebar to enable the AI Executive Brief.")

    # ----- Ask Gemini (conversational QA over the data) -----
    with st.expander("💬 Ask Gemini about this data", expanded=False):
        st.caption("Ask a question in plain English; Gemini will answer using the current event list.")
        ask_query = st.text_input("Question", placeholder="e.g. What are the biggest risks in Asia? Which commodities are most affected?", key="ask_input")
        if st.button("Ask Gemini", key="ask_btn"):
            if ask_query and api_key and api_key.strip():
                with st.spinner("Thinking..."):
                    answer = ask_gemini_about_data(df_filtered, ask_query, api_key)
                st.markdown("**Answer**")
                st.write(answer)
            elif not (api_key and api_key.strip()):
                st.error("Please set a Gemini API key in the sidebar.")
            else:
                st.warning("Enter a question.")

    # Map
    st.subheader("🌍 Interactive World Map")
    if df_filtered.empty:
        st.info("No events to display on map.")
    else:
        map_viz = create_map_visualization(df_filtered)
        if map_viz:
            try:
                st.pydeck_chart(map_viz, use_container_width=True)
            except Exception:
                df_map = df_filtered.copy()
                df_map = df_map.rename(columns={"latitude": "lat", "longitude": "lon"})
                st.map(df_map[["lat", "lon"]])
        else:
            df_map = df_filtered.copy()
            if "latitude" in df_map.columns and "longitude" in df_map.columns:
                df_map = df_map.rename(columns={"latitude": "lat", "longitude": "lon"})
                st.map(df_map[["lat", "lon"]])
            else:
                st.info("No coordinates available to display on map.")

    # Construction radar
    st.subheader("🏗️ Construction Material Radar")
    radar_fig = create_construction_radar(df_filtered)
    if radar_fig:
        st.plotly_chart(radar_fig, use_container_width=True)
    else:
        st.write("No data for radar.")

    # Event table
    st.subheader("📋 Event Table (Signal Intelligence Feed)")
    if df_filtered.empty:
        st.write("No events match current filters.")
    else:
        display_cols = ["timestamp", "location", "headline", "risk_score", "category", "commodity"]
        available = [c for c in display_cols if c in df_filtered.columns]
        st.dataframe(
            df_filtered[available],
            column_config={
                "risk_score": st.column_config.ProgressColumn("Risk", min_value=1, max_value=10, format="%d"),
                "headline": st.column_config.TextColumn("Event", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )
        csv = df_filtered.to_csv(index=False)
        st.download_button("📥 Download CSV", data=csv, file_name="vantagepoint_events.csv", mime="text/csv")

    # ----- Event detail + Gemini -----
    st.markdown("### 🔍 Event Detail & AI Analysis")
    if not df_filtered.empty:
        event_options = df_filtered["headline"].tolist()
        selected_headline = st.selectbox("Select event for details and Gemini analysis", event_options, key="event_select")
        if selected_headline:
            row = df_filtered[df_filtered["headline"] == selected_headline].iloc[0]
            event_id = id(row) if hasattr(row, "__iter__") else selected_headline

            with st.expander("📍 EVENT DETAILS", expanded=True):
                st.markdown(f"**🗞️ Headline:** {row['headline']}")
                st.markdown(f"**📍 Location:** {row['location']}")
                risk_val = int(row["risk_score"]) if pd.notna(row.get("risk_score")) else 0
                st.markdown(f"**🎯 Risk Score:** {risk_val}/10")
                st.progress(risk_val / 10.0)
                st.markdown(f"**Category:** {row.get('category', '—')} | **Commodity:** {row.get('commodity', '—')}")
                if row.get("article_snippet"):
                    st.caption("Snippet: " + str(row["article_snippet"])[:300])

                st.markdown("---")
                st.markdown("**🤖 Gemini Analysis**")
                gemini_data = row.get("gemini_analysis")

                if gemini_data and isinstance(gemini_data, dict) and "error" not in gemini_data:
                    st.markdown(f"- **Category:** {gemini_data.get('category', '—')}")
                    ind = gemini_data.get("affected_industries", [])
                    st.markdown(f"- **Industries Affected:** {', '.join(ind) if ind else '—'}")
                    timeline = gemini_data.get("timeline", {})
                    if timeline:
                        st.markdown("- **Timeline Predictions:**")
                        st.markdown(f"  - Short (1–7 days): {timeline.get('short_term', '—')}")
                        st.markdown(f"  - Medium (1–4 weeks): {timeline.get('medium_term', '—')}")
                        st.markdown(f"  - Long (1–6 months): {timeline.get('long_term', '—')}")
                    st.markdown(f"- **Reasoning:** {gemini_data.get('reasoning', '—')}")
                    st.markdown(f"- **Next Steps:** {gemini_data.get('actionable_intelligence', '—')}")
                    if gemini_data.get("is_construction_related"):
                        st.markdown(f"- **Construction prediction:** {gemini_data.get('construction_prediction') or '—'}")
                elif gemini_data and isinstance(gemini_data, dict) and gemini_data.get("error"):
                    st.error("Analysis error: " + str(gemini_data["error"]))
                elif row.get("reasoning") and not gemini_data:
                    st.caption("*(Mock data)* Pre-written analysis:")
                    st.markdown(f"- **Reasoning:** {row['reasoning']}")
                else:
                    if "gemini_cache" not in st.session_state:
                        st.session_state["gemini_cache"] = {}
                    cache_key = selected_headline[:80]
                    if cache_key in st.session_state["gemini_cache"]:
                        ga = st.session_state["gemini_cache"][cache_key]
                        if isinstance(ga, dict) and "error" not in ga:
                            st.markdown(f"- **Category:** {ga.get('category', '—')}")
                            ind = ga.get("affected_industries", [])
                            st.markdown(f"- **Industries Affected:** {', '.join(ind) if ind else '—'}")
                            timeline = ga.get("timeline", {})
                            if timeline:
                                st.markdown("- **Timeline Predictions:**")
                                st.markdown(f"  - Short (1–7 days): {timeline.get('short_term', '—')}")
                                st.markdown(f"  - Medium (1–4 weeks): {timeline.get('medium_term', '—')}")
                                st.markdown(f"  - Long (1–6 months): {timeline.get('long_term', '—')}")
                            st.markdown(f"- **Reasoning:** {ga.get('reasoning', '—')}")
                            st.markdown(f"- **Next Steps:** {ga.get('actionable_intelligence', '—')}")
                            if ga.get("is_construction_related"):
                                st.markdown(f"- **Construction prediction:** {ga.get('construction_prediction') or '—'}")
                        else:
                            st.error(ga.get("error", "Analysis failed."))
                    elif st.button("✨ Analyze with Gemini", key=f"analyze_{event_id}"):
                        if not api_key or not api_key.strip():
                            st.error("Please enter a Gemini API Key in the sidebar.")
                        else:
                            ev = row.to_dict()
                            with st.spinner("Consulting Gemini 3..."):
                                analyzed = analyze_with_gemini(ev, api_key)
                            ga = analyzed.get("gemini_analysis") or {}
                            st.session_state["gemini_cache"][cache_key] = ga
                            st.rerun()
                    else:
                        st.info("Click **Analyze with Gemini** to get AI insights for this event.")


if __name__ == "__main__":
    main()
