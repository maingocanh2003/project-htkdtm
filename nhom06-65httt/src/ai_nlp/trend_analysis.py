"""FR-2.2: Phan tich xu huong tim kiem 52 tuan, tinh mua vu, 51 bang/vung va tu khoa but pha."""

from __future__ import annotations

import numpy as np
import pandas as pd


def analyze_weekly_trends(
    search_trends_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Phan tich chuoi thoi gian 52 tuan Google Trends, MA(4), mua vu va do doc xu huong."""
    if search_trends_df.empty:
        return {
            "weekly_series": pd.DataFrame(),
            "category_trajectory": pd.DataFrame(),
            "seasonality_by_quarter": pd.DataFrame(),
        }

    national = search_trends_df[search_trends_df["region_id"].isna()].copy()
    if national.empty:
        national = search_trends_df.copy()

    national["week_start_date"] = pd.to_datetime(national["week_start_date"])
    national["quarter"] = national["week_start_date"].dt.quarter
    national = national.sort_values(["country_id", "category_id", "week_number"]).reset_index(drop=True)

    national["ma_4w"] = (
        national.groupby(["country_id", "category_id"])["interest_score"]
        .transform(lambda s: s.rolling(window=4, min_periods=1).mean())
        .round(2)
    )

    weekly_series = national.merge(
        countries_df[["country_id", "country_code", "country_name"]], on="country_id", how="left"
    ).merge(
        categories_df[["category_id", "category_code", "category_name_vi", "category_name_en"]],
        on="category_id",
        how="left",
    )

    trajectory_rows = []
    for (cid, cat_id), grp in weekly_series.groupby(["country_id", "category_id"]):
        grp = grp.sort_values("week_number")
        scores = grp["interest_score"].to_numpy(dtype=float)
        weeks = grp["week_number"].to_numpy(dtype=float)

        slope = float(np.polyfit(weeks, scores, 1)[0]) if len(scores) >= 2 and np.ptp(weeks) > 0 else 0.0
        half = max(len(scores) // 2, 1)
        h1_mean = float(np.mean(scores[:half]))
        h2_mean = float(np.mean(scores[half:])) if len(scores) > half else h1_mean
        h2_vs_h1 = ((h2_mean - h1_mean) / h1_mean * 100.0) if h1_mean > 0 else 0.0

        peak_idx = int(np.argmax(scores))
        if slope >= 0.25 or h2_vs_h1 >= 10.0:
            direction = "Strong Uptrend"
        elif slope <= -0.25 or h2_vs_h1 <= -10.0:
            direction = "Cooling"
        else:
            direction = "Seasonal Stable"

        first_row = grp.iloc[0]
        trajectory_rows.append(
            {
                "country_id": int(cid),
                "country_code": first_row["country_code"],
                "country_name": first_row["country_name"],
                "category_id": int(cat_id),
                "category_code": first_row["category_code"],
                "category_name_vi": first_row["category_name_vi"],
                "search_term": first_row["search_term"],
                "avg_interest_score": round(float(np.mean(scores)), 2),
                "max_interest_score": int(np.max(scores)),
                "min_interest_score": int(np.min(scores)),
                "peak_week_number": int(weeks[peak_idx]),
                "trend_slope_per_week": round(slope, 4),
                "h2_vs_h1_change_pct": round(h2_vs_h1, 2),
                "trend_direction": direction,
            }
        )

    trajectory_df = pd.DataFrame(trajectory_rows).sort_values(
        ["avg_interest_score", "h2_vs_h1_change_pct"], ascending=[False, False]
    ).reset_index(drop=True)

    seasonality = (
        weekly_series.groupby(
            ["country_code", "country_name", "category_code", "category_name_vi", "quarter"],
            as_index=False,
        )["interest_score"]
        .mean()
        .rename(columns={"interest_score": "quarter_avg_interest"})
    )
    annual_avg = seasonality.groupby(["country_code", "category_code"])[
        "quarter_avg_interest"
    ].transform("mean")
    seasonality["seasonality_index"] = np.where(
        annual_avg > 0, (seasonality["quarter_avg_interest"] / annual_avg) * 100.0, 100.0
    ).round(2)
    seasonality["quarter_avg_interest"] = seasonality["quarter_avg_interest"].round(2)

    return {
        "weekly_series": weekly_series,
        "category_trajectory": trajectory_df,
        "seasonality_by_quarter": seasonality,
    }


def analyze_regional_distribution(
    search_trends_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    market_regions_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Phan tich phan bo muc do quan tam theo 51 bang/vung lanh tho."""
    regional = search_trends_df[search_trends_df["region_id"].notna()].copy()
    if regional.empty or market_regions_df.empty:
        return pd.DataFrame()

    regional["region_id"] = regional["region_id"].astype(int)
    merged = (
        regional.merge(
            market_regions_df[["region_id", "region_code", "region_name"]],
            on="region_id",
            how="left",
        )
        .merge(countries_df[["country_id", "country_code", "country_name"]], on="country_id", how="left")
        .merge(
            categories_df[["category_id", "category_code", "category_name_vi"]],
            on="category_id",
            how="left",
        )
    )

    summary = (
        merged.groupby(
            ["country_code", "country_name", "region_code", "region_name"], as_index=False
        )
        .agg(
            avg_interest_score=("interest_score", "mean"),
            max_interest_score=("interest_score", "max"),
            categories_tracked=("category_code", "nunique"),
        )
        .sort_values(["country_code", "avg_interest_score"], ascending=[True, False])
        .reset_index(drop=True)
    )
    summary["avg_interest_score"] = summary["avg_interest_score"].round(2)
    summary["region_rank_in_country"] = (
        summary.groupby("country_code")["avg_interest_score"].rank(method="dense", ascending=False).astype(int)
    )
    return summary


def analyze_breakout_keywords(
    trending_keywords_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Xep hang tu khoa but pha (+140% den +5300%) va thong ke theo nhom thuoc tinh."""
    if trending_keywords_df.empty:
        return {"ranked_keywords": pd.DataFrame(), "attribute_momentum": pd.DataFrame()}

    ranked = (
        trending_keywords_df.merge(
            countries_df[["country_id", "country_code", "country_name"]], on="country_id", how="left"
        )
        .merge(
            categories_df[["category_id", "category_code", "category_name_vi"]],
            on="category_id",
            how="left",
        )
        .sort_values("growth_pct", ascending=False)
        .reset_index(drop=True)
    )
    ranked["keyword_rank"] = ranked.index + 1

    attr_momentum = (
        ranked.groupby("related_attribute_type", as_index=False)
        .agg(
            keyword_count=("keyword_id", "count"),
            avg_growth_pct=("growth_pct", "mean"),
            max_growth_pct=("growth_pct", "max"),
            breakout_count=("trend_classification", lambda s: int((s == "Breakout").sum())),
        )
        .sort_values("avg_growth_pct", ascending=False)
        .reset_index(drop=True)
    )
    attr_momentum["avg_growth_pct"] = attr_momentum["avg_growth_pct"].round(2)

    return {
        "ranked_keywords": ranked,
        "attribute_momentum": attr_momentum,
    }
