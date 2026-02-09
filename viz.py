"""
VantagePoint — visualizations: map, construction radar, health gauge.
"""

import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def get_risk_color(risk_score: int) -> list:
    """RGB + alpha for map: Green (1-3), Yellow (4-6), Red (7-10)."""
    if risk_score >= 7:
        return [239, 68, 68, 180]
    if risk_score >= 4:
        return [245, 158, 11, 180]
    return [34, 197, 94, 180]


def create_map_visualization(df: pd.DataFrame):
    """3D pydeck map with risk-colored markers. Uses free tiles (no Mapbox key)."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        return None
    df = df.copy()
    df["color"] = df["risk_score"].apply(get_risk_color)
    df["radius"] = (df["risk_score"] * 30000).astype(int)

    layer = pdk.Layer(
        "ScatterplotLayer",
        df,
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.85,
        stroked=True,
        filled=True,
        radius_min_pixels=6,
        radius_max_pixels=50,
    )

    view_state = pdk.ViewState(
        latitude=25,
        longitude=20,
        zoom=1.4,
        pitch=45,
    )

    tooltip = {
        "html": "<b>{headline}</b><br/>Risk: {risk_score}/10<br/>Location: {location}",
        "style": {"backgroundColor": "#0f172a", "color": "#e2e8f0"},
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    )


def create_construction_radar(df: pd.DataFrame, top_n: int = 10) -> go.Figure | None:
    """Bar chart of top N destinations receiving construction-related materials."""
    if df.empty:
        return None
    construction = df[df["category"] == "Construction"]
    if construction.empty:
        construction = df
    dest_counts = construction["location"].value_counts().head(top_n).reset_index()
    dest_counts.columns = ["Destination", "Count"]
    fig = px.bar(
        dest_counts,
        x="Count",
        y="Destination",
        orientation="h",
        color="Count",
        color_continuous_scale="Teal",
        title="Top Destinations (Construction Material Flows)",
    )
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0), showlegend=False, yaxis={"categoryorder": "total ascending"})
    return fig


def render_health_gauge(health: int) -> None:
    """Render 0-100 health gauge in sidebar."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=health,
        number={"suffix": "/100"},
        domain={"x": [0, 1], "y": [0, 1]},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#0ea5e9"},
            "steps": [
                {"range": [0, 40], "color": "#1e293b"},
                {"range": [40, 70], "color": "#334155"},
                {"range": [70, 100], "color": "#0f172a"},
            ],
            "threshold": {
                "line": {"color": "#22c55e", "width": 4},
                "thickness": 0.75,
                "value": health,
            },
        },
        title={"text": "Global Health Index"},
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e2e8f0"})
    st.plotly_chart(fig, use_container_width=True)
