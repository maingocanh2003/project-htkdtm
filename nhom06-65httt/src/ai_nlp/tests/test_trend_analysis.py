"""Kiem thu don vi cho phan tich xu huong Google Trends 52 tuan, 51 bang va tu khoa but pha (FR-2.2)."""

from __future__ import annotations

from src.ai_nlp.db_connector import load_sample_dataset
from src.ai_nlp.trend_analysis import (
    analyze_breakout_keywords,
    analyze_regional_distribution,
    analyze_weekly_trends,
)


def test_weekly_trends_52_weeks_and_seasonality():
    ds = load_sample_dataset()
    res = analyze_weekly_trends(ds.search_trends, ds.countries, ds.product_categories)
    assert not res["weekly_series"].empty
    assert res["weekly_series"]["week_number"].nunique() == 52
    assert not res["category_trajectory"].empty
    assert {"trend_slope_per_week", "h2_vs_h1_change_pct", "trend_direction"}.issubset(
        res["category_trajectory"].columns
    )
    assert set(res["seasonality_by_quarter"]["quarter"].unique()) == {1, 2, 3, 4}


def test_regional_distribution_covers_51_us_regions():
    ds = load_sample_dataset()
    reg = analyze_regional_distribution(
        ds.search_trends, ds.countries, ds.market_regions, ds.product_categories
    )
    us_rows = reg[reg["country_code"] == "USA"]
    assert len(us_rows) == 51
    assert us_rows["region_rank_in_country"].min() == 1


def test_breakout_keywords_ranking_and_attribute_momentum():
    ds = load_sample_dataset()
    kw = analyze_breakout_keywords(ds.trending_keywords, ds.countries, ds.product_categories)
    assert not kw["ranked_keywords"].empty
    assert kw["ranked_keywords"]["growth_pct"].iloc[0] >= 5000.0
    assert not kw["attribute_momentum"].empty
