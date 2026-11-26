"""FR-2.1: Phan tich quy mo, toc do tang truong, thi phan va xep hang tiem nang thi truong."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .config import KEY_MARKET_CODES


def _minmax_scale(series: pd.Series) -> pd.Series:
    """Chuan hoa gia tri ve thang [0, 100]; tra ve 50.0 neu tat ca bang nhau."""
    if series.empty:
        return series
    s_min = float(series.min())
    s_max = float(series.max())
    if np.isclose(s_max, s_min):
        return pd.Series(50.0, index=series.index)
    return ((series - s_min) / (s_max - s_min)) * 100.0


def compute_country_yearly_metrics(
    trade_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    trade_flow: str = "Import",
) -> pd.DataFrame:
    """Tong hop 14 chi tieu thuong mai theo tung quoc gia va nam, tinh thi phan va YoY."""
    if trade_df.empty:
        return pd.DataFrame()

    filtered = trade_df[trade_df["trade_flow"].str.lower() == trade_flow.lower()].copy()
    if filtered.empty:
        filtered = trade_df.copy()

    grouped = (
        filtered.groupby(["partner_country_id", "year"], as_index=False)
        .agg(
            trade_value_usd=("trade_value_usd", "sum"),
            fob_value_usd=("fob_value_usd", "sum"),
            cif_value_usd=("cif_value_usd", "sum"),
            net_weight_kg=("net_weight_kg", "sum"),
            qty_amount=("qty_amount", "sum"),
            hs_code_count=("hs_code", "nunique"),
        )
        .sort_values(["partner_country_id", "year"])
    )

    year_total = grouped.groupby("year")["trade_value_usd"].transform("sum")
    grouped["market_share_pct"] = np.where(
        year_total > 0, (grouped["trade_value_usd"] / year_total) * 100.0, 0.0
    ).round(2)

    grouped["prev_trade_value_usd"] = grouped.groupby("partner_country_id")["trade_value_usd"].shift(1)
    grouped["yoy_growth_rate"] = np.where(
        grouped["prev_trade_value_usd"].notna() & (grouped["prev_trade_value_usd"] > 0),
        ((grouped["trade_value_usd"] - grouped["prev_trade_value_usd"]) / grouped["prev_trade_value_usd"])
        * 100.0,
        np.nan,
    ).round(2)
    grouped["usd_per_kg"] = np.where(
        grouped["net_weight_kg"] > 0, grouped["trade_value_usd"] / grouped["net_weight_kg"], 0.0
    ).round(2)

    merged = grouped.merge(
        countries_df[
            ["country_id", "country_code", "country_name", "region_continent", "is_key_market"]
        ],
        left_on="partner_country_id",
        right_on="country_id",
        how="left",
    ).drop(columns=["country_id", "prev_trade_value_usd"])

    return merged.sort_values(["year", "trade_value_usd"], ascending=[True, False]).reset_index(
        drop=True
    )


def compute_market_potential_ranking(
    trade_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    search_trends_df: pd.DataFrame | None = None,
    trade_flow: str = "Import",
) -> pd.DataFrame:
    """Tinh CAGR, diem tiem nang thi truong (0-100) va xep hang toan bo quoc gia."""
    yearly = compute_country_yearly_metrics(trade_df, countries_df, trade_flow=trade_flow)
    if yearly.empty:
        return pd.DataFrame()

    first_year = int(yearly["year"].min())
    latest_year = int(yearly["year"].max())
    n_years = max(latest_year - first_year, 1)

    start_vals = (
        yearly[yearly["year"] == first_year][["partner_country_id", "trade_value_usd"]]
        .rename(columns={"trade_value_usd": "start_trade_value_usd"})
    )
    latest_rows = yearly[yearly["year"] == latest_year].copy()
    agg_totals = yearly.groupby("partner_country_id", as_index=False).agg(
        cumulative_trade_value_usd=("trade_value_usd", "sum"),
        cumulative_net_weight_kg=("net_weight_kg", "sum"),
        avg_yoy_growth_pct=("yoy_growth_rate", "mean"),
    )

    ranked = (
        latest_rows.merge(start_vals, on="partner_country_id", how="left")
        .merge(agg_totals, on="partner_country_id", how="left")
    )
    ranked["cagr_pct"] = np.where(
        (ranked["start_trade_value_usd"] > 0) & (latest_year > first_year),
        ((ranked["trade_value_usd"] / ranked["start_trade_value_usd"]) ** (1.0 / n_years) - 1.0)
        * 100.0,
        ranked["avg_yoy_growth_pct"].fillna(0.0),
    ).round(2)

    if search_trends_df is not None and not search_trends_df.empty:
        nat_trends = search_trends_df[search_trends_df["region_id"].isna()]
        if nat_trends.empty:
            nat_trends = search_trends_df
        trend_scores = nat_trends.groupby("country_id", as_index=False).agg(
            avg_search_interest=("interest_score", "mean")
        )
        ranked = ranked.merge(
            trend_scores, left_on="partner_country_id", right_on="country_id", how="left"
        ).drop(columns=["country_id"])
    else:
        ranked["avg_search_interest"] = np.nan

    ranked["avg_search_interest"] = ranked["avg_search_interest"].fillna(
        ranked["avg_search_interest"].median() if ranked["avg_search_interest"].notna().any() else 50.0
    ).round(2)

    scale_score = _minmax_scale(np.log1p(ranked["trade_value_usd"].clip(lower=0)))
    growth_basis = ranked["cagr_pct"].fillna(0.0).clip(lower=-30.0, upper=60.0)
    growth_score = _minmax_scale(growth_basis)
    demand_score = _minmax_scale(ranked["avg_search_interest"])

    ranked["market_potential_score"] = (
        0.45 * scale_score + 0.35 * growth_score + 0.20 * demand_score
    ).round(2)

    def _classify_tier(row: pd.Series) -> str:
        if row["market_potential_score"] >= 75:
            return "Tier 1 - High Potential"
        if row["market_potential_score"] >= 55:
            return "Tier 2 - Growing"
        if row["cagr_pct"] < 0:
            return "Saturated / Declining"
        return "Tier 3 - Emerging"

    ranked["market_tier"] = ranked.apply(_classify_tier, axis=1)
    ranked = ranked.sort_values(
        ["market_potential_score", "trade_value_usd"], ascending=[False, False]
    ).reset_index(drop=True)
    ranked["potential_rank"] = ranked.index + 1

    cols = [
        "potential_rank",
        "partner_country_id",
        "country_code",
        "country_name",
        "region_continent",
        "is_key_market",
        "year",
        "trade_value_usd",
        "fob_value_usd",
        "cif_value_usd",
        "net_weight_kg",
        "usd_per_kg",
        "market_share_pct",
        "yoy_growth_rate",
        "cagr_pct",
        "avg_search_interest",
        "cumulative_trade_value_usd",
        "market_potential_score",
        "market_tier",
    ]
    return ranked[[c for c in cols if c in ranked.columns]]


def compare_key_markets(
    trade_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    country_codes: Iterable[str] = KEY_MARKET_CODES,
) -> dict[str, pd.DataFrame]:
    """So sanh chi tiet nhom thi truong trong diem va co cau theo ma HS (6911, 6912, 6913)."""
    codes = set(country_codes)
    key_ranking = ranking_df[ranking_df["country_code"].isin(codes)].reset_index(drop=True)

    latest_year = int(trade_df["year"].max())
    latest_hs = trade_df[
        (trade_df["year"] == latest_year) & (trade_df["trade_flow"].str.lower() == "import")
    ].merge(
        countries_df[["country_id", "country_code", "country_name"]],
        left_on="partner_country_id",
        right_on="country_id",
        how="left",
    )
    key_hs = latest_hs[latest_hs["country_code"].isin(codes)].copy()
    if not key_hs.empty:
        country_tot = key_hs.groupby("country_code")["trade_value_usd"].transform("sum")
        key_hs["hs_share_within_country_pct"] = np.where(
            country_tot > 0, (key_hs["trade_value_usd"] / country_tot) * 100.0, 0.0
        ).round(2)
        key_hs = key_hs[
            [
                "country_code",
                "country_name",
                "hs_code",
                "cmd_desc",
                "trade_value_usd",
                "net_weight_kg",
                "yoy_growth_rate",
                "hs_share_within_country_pct",
            ]
        ].sort_values(["country_code", "trade_value_usd"], ascending=[True, False])

    return {
        "key_markets_summary": key_ranking,
        "key_markets_hs_breakdown": key_hs.reset_index(drop=True),
    }
