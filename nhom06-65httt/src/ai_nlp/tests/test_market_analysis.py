"""Kiem thu don vi cho phan tich quy mo, tang truong YoY/CAGR va tiem nang thi truong (FR-2.1)."""

from __future__ import annotations

import pandas as pd

from src.ai_nlp.db_connector import load_sample_dataset
from src.ai_nlp.market_analysis import (
    compare_key_markets,
    compute_country_yearly_metrics,
    compute_market_potential_ranking,
)


def test_yearly_metrics_computes_yoy_and_market_share():
    ds = load_sample_dataset()
    yearly = compute_country_yearly_metrics(ds.trade_statistics, ds.countries)
    assert not yearly.empty
    assert {"market_share_pct", "yoy_growth_rate", "usd_per_kg"}.issubset(yearly.columns)
    for _, grp in yearly.groupby("year"):
        assert 99.0 <= grp["market_share_pct"].sum() <= 101.0


def test_market_potential_ranking_covers_over_130_countries():
    ds = load_sample_dataset()
    ranked = compute_market_potential_ranking(ds.trade_statistics, ds.countries, ds.search_trends)
    assert len(ranked) >= 130
    assert ranked["potential_rank"].iloc[0] == 1
    assert ranked["market_potential_score"].between(0, 100).all()
    assert ranked["country_code"].iloc[0] in {"USA", "CHN", "JPN", "DEU", "IND"}


def test_compare_key_markets_returns_hs_breakdown():
    ds = load_sample_dataset()
    ranked = compute_market_potential_ranking(ds.trade_statistics, ds.countries, ds.search_trends)
    comp = compare_key_markets(ds.trade_statistics, ds.countries, ranked)
    assert not comp["key_markets_summary"].empty
    assert set(comp["key_markets_hs_breakdown"]["hs_code"].unique()) == {"6911", "6912", "6913"}
