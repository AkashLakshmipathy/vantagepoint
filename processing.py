"""
VantagePoint — data processing: health index, filters.
"""

import pandas as pd


def calculate_health_index(events_df: pd.DataFrame) -> int:
    """Global Supply Chain Health Index 0-100. Higher = healthier."""
    if events_df.empty:
        return 100
    high_risk = len(events_df[events_df["risk_score"] >= 7])
    disruptions = len(events_df[events_df["category"] == "Disruption"])
    health = max(0, 100 - (high_risk * 5) - (disruptions * 3))
    return min(100, health)


def filter_events(
    df: pd.DataFrame,
    region: str,
    risk_level: str,
    category_filter: str,
    commodity_filter: str,
) -> pd.DataFrame:
    """Apply sidebar filters; returns filtered DataFrame."""
    if df.empty:
        return df
    out = df.copy()

    if risk_level == "Low":
        out = out[out["risk_score"] <= 3]
    elif risk_level == "Medium":
        out = out[(out["risk_score"] >= 4) & (out["risk_score"] <= 6)]
    elif risk_level == "High":
        out = out[out["risk_score"] >= 7]

    if region == "Asia":
        out = out[(out["longitude"] >= 60) & (out["longitude"] <= 150)]
    elif region == "Europe":
        out = out[(out["longitude"] >= -20) & (out["longitude"] <= 40) & (out["latitude"] >= 35)]
    elif region == "Americas":
        out = out[(out["longitude"] <= -50) | (out["longitude"] >= -170)]
    elif region == "Africa":
        out = out[(out["latitude"] >= -35) & (out["latitude"] <= 37) & (out["longitude"] >= -20) & (out["longitude"] <= 52)]

    if category_filter != "All":
        out = out[out["category"] == category_filter]
    if commodity_filter != "All":
        out = out[out["commodity"] == commodity_filter]

    return out.reset_index(drop=True)
