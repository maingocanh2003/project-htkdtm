"""Kiem thu don vi cho phan tich thi hieu 5 nhom thuoc tinh, cong nang va phan khuc gia (FR-2.3)."""

from __future__ import annotations

from src.ai_nlp.db_connector import load_sample_dataset
from src.ai_nlp.taste_analysis import (
    analyze_attribute_preferences,
    analyze_functional_features,
    analyze_price_distribution,
    build_country_taste_profiles,
)


def test_attribute_preferences_covers_all_5_groups_and_price():
    ds = load_sample_dataset()
    attr = analyze_attribute_preferences(ds.market_products, ds.countries, ds.product_categories)
    assert set(attr["attribute_group"].unique()) == {
        "category",
        "color",
        "shape",
        "material",
        "style",
        "price_segment",
    }
    sums = attr.groupby(["country_code", "attribute_group"])["attribute_share_pct"].sum()
    assert ((sums >= 99.5) & (sums <= 100.5)).all()


def test_country_taste_profiles_and_features():
    ds = load_sample_dataset()
    profiles = build_country_taste_profiles(ds.market_products, ds.countries, ds.product_categories)
    assert len(profiles) == 5
    assert {"top_category", "top_colors", "top_material", "top_style", "dishwasher_safe_pct"}.issubset(
        profiles.columns
    )
    features = analyze_functional_features(ds.market_products, ds.countries, ds.product_categories)
    assert not features.empty
    prices = analyze_price_distribution(ds.market_products, ds.countries, ds.product_categories)
    assert (prices["max_price_usd"] >= prices["min_price_usd"]).all()
