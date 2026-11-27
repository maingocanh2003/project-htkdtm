"""Kiem thu bo trich xuat khia canh khen/che ABSA va danh gia F1 tren tap kiem thu (FR-2.5)."""

from __future__ import annotations

from src.ai_nlp.aspect_extractor import (
    evaluate_aspect_extraction,
    extract_aspects_batch,
    extract_aspects_from_review,
    summarize_aspects_for_market,
)
from src.ai_nlp.db_connector import load_sample_dataset


def test_extract_aspects_handles_mixed_sentiment_review():
    text = (
        "The ceramic glaze is super smooth and scratch-resistant. "
        "However, arrived with a broken handle because the outer box had almost no padding."
    )
    extracted = extract_aspects_from_review(review_id=1, review_text=text)
    by_cat = {item["aspect_category"]: item["aspect_sentiment"] for item in extracted}
    assert by_cat.get("Glaze Durability") == "Positive"
    assert by_cat.get("Packaging") == "Negative"


def test_aspect_extraction_achieves_high_f1_on_benchmark():
    ds = load_sample_dataset()
    aspects_df = extract_aspects_batch(ds.product_reviews)
    metrics = evaluate_aspect_extraction(ds.product_reviews, aspects_df)
    assert metrics["aspect_category_detection"]["f1_score"] >= 0.90
    assert metrics["joint_aspect_sentiment"]["f1_score"] >= 0.85

    summary = summarize_aspects_for_market(
        aspects_df,
        ds.product_reviews,
        ds.market_products,
        ds.countries,
        ds.product_categories,
    )
    assert not summary.empty
    assert (summary["positive_rate_pct"] + summary["complaint_rate_pct"] <= 100.1).all()
