"""Pipeline chay toan bo phan he Phan tich thi truong, thi hieu va AI/NLP (Nguyen The Nguyen)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .aspect_extractor import (
    evaluate_aspect_extraction,
    extract_aspects_batch,
    summarize_aspects_for_market,
)
from .config import MODELS_DIR, OUTPUTS_DIR, ensure_directories
from .dashboard_exporter import (
    build_quality_packaging_notes,
    build_sentiment_summary,
    export_analysis_outputs,
)
from .db_connector import AnalysisDataset, PostgresConnector, load_sample_dataset
from .market_analysis import (
    compare_key_markets,
    compute_country_yearly_metrics,
    compute_market_potential_ranking,
)
from .sentiment_model import CeramicSentimentModel
from .taste_analysis import (
    analyze_attribute_preferences,
    analyze_functional_features,
    analyze_price_distribution,
    build_country_taste_profiles,
)
from .trend_analysis import (
    analyze_breakout_keywords,
    analyze_regional_distribution,
    analyze_weekly_trends,
)


def run_full_analysis(
    source: str = "sample",
    save_db: bool = False,
    output_dir: Path | None = None,
    model_dir: Path | None = None,
) -> dict[str, Any]:
    """Thuc thi tron ven FR-2.1 den FR-2.5 va xuat ket qua cho Dashboard BI."""
    ensure_directories()
    target_out = output_dir or OUTPUTS_DIR
    target_model = model_dir or MODELS_DIR

    connector: PostgresConnector | None = None
    if source == "db":
        connector = PostgresConnector()
        dataset: AnalysisDataset = connector.load_analysis_dataset()
    elif source == "sample":
        dataset = load_sample_dataset()
    else:
        raise ValueError(f"Nguon du lieu khong hop le: {source}. Chon 'sample' hoac 'db'.")

    # 1. FR-2.1: Phan tich quy mo va tiem nang thi truong
    yearly_metrics = compute_country_yearly_metrics(dataset.trade_statistics, dataset.countries)
    market_ranking = compute_market_potential_ranking(
        dataset.trade_statistics, dataset.countries, dataset.search_trends
    )
    key_comp = compare_key_markets(dataset.trade_statistics, dataset.countries, market_ranking)

    # 2. FR-2.2: Phan tich xu huong tim kiem 52 tuan, 51 bang & tu khoa but pha
    weekly_res = analyze_weekly_trends(
        dataset.search_trends, dataset.countries, dataset.product_categories
    )
    regional_trends = analyze_regional_distribution(
        dataset.search_trends,
        dataset.countries,
        dataset.market_regions,
        dataset.product_categories,
    )
    keyword_res = analyze_breakout_keywords(
        dataset.trending_keywords, dataset.countries, dataset.product_categories
    )

    # 3. FR-2.3: Phan tich thi hieu theo 5 nhom thuoc tinh & phan khuc gia
    attr_prefs = analyze_attribute_preferences(
        dataset.market_products, dataset.countries, dataset.product_categories
    )
    country_profiles = build_country_taste_profiles(
        dataset.market_products, dataset.countries, dataset.product_categories
    )
    functional_features = analyze_functional_features(
        dataset.market_products, dataset.countries, dataset.product_categories
    )
    price_dist = analyze_price_distribution(
        dataset.market_products, dataset.countries, dataset.product_categories
    )

    # 4. FR-2.4: Mo hinh AI/NLP phan loai cam xuc danh gia khach hang
    sentiment_model = CeramicSentimentModel(random_state=42)
    sentiment_eval: dict[str, Any] = {}
    if "true_sentiment" in dataset.product_reviews.columns and dataset.product_reviews[
        "true_sentiment"
    ].notna().any():
        sentiment_eval = sentiment_model.train_and_evaluate(
            dataset.product_reviews, label_col="true_sentiment", test_size=0.2
        )
        sentiment_model.save(target_model)
    else:
        model_file = target_model / "sentiment_pipeline.joblib"
        if not model_file.exists():
            # Fallback huan luyen tu bo benchmark chuan neu DB chua co nhan ground truth
            bench = load_sample_dataset()
            sentiment_eval = sentiment_model.train_and_evaluate(
                bench.product_reviews, label_col="true_sentiment", test_size=0.2
            )
            sentiment_model.save(target_model)
        else:
            sentiment_model = CeramicSentimentModel.load(model_file)

    predicted_reviews = sentiment_model.predict(dataset.product_reviews)
    sentiment_summary = build_sentiment_summary(
        predicted_reviews,
        dataset.market_products,
        dataset.countries,
        dataset.product_categories,
    )

    # 5. FR-2.5: Trich xuat khia canh khen/che (ABSA)
    aspects_df = extract_aspects_batch(predicted_reviews)
    absa_eval: dict[str, Any] = {}
    if "true_aspects" in dataset.product_reviews.columns and dataset.product_reviews[
        "true_aspects"
    ].notna().any():
        absa_eval = evaluate_aspect_extraction(
            dataset.product_reviews,
            aspects_df,
            test_review_ids=sentiment_model.test_review_ids or None,
        )
        (target_model / "absa_eval_metrics.json").write_text(
            json.dumps(absa_eval, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    aspect_market_summary = summarize_aspects_for_market(
        aspects_df,
        predicted_reviews,
        dataset.market_products,
        dataset.countries,
        dataset.product_categories,
    )
    quality_notes = build_quality_packaging_notes(aspect_market_summary)

    # 6. Ghi ket qua AI/NLP xuong PostgreSQL neu duoc bat
    db_sync_stats: dict[str, int] = {}
    if save_db:
        if connector is None:
            connector = PostgresConnector()
        db_sync_stats["updated_reviews"] = connector.save_review_predictions(predicted_reviews)
        db_sync_stats["saved_aspects"] = connector.save_review_aspects(aspects_df)
        db_sync_stats["synced_fact_rows"] = connector.sync_star_schema_reviews()

    # 7. Xuat bo du lieu phuc vu Dashboard BI
    pred_cols = [
        c
        for c in (
            "review_id",
            "market_product_id",
            "rating_stars",
            "review_title",
            "review_date",
            "sentiment_label",
            "sentiment_score",
        )
        if c in predicted_reviews.columns
    ]
    tables_to_export = {
        "market_yearly_metrics": yearly_metrics,
        "market_potential_ranking": market_ranking,
        "key_markets_hs_breakdown": key_comp["key_markets_hs_breakdown"],
        "trend_weekly_trajectory": weekly_res["category_trajectory"],
        "trend_seasonality_quarterly": weekly_res["seasonality_by_quarter"],
        "trend_regional_51_states": regional_trends,
        "trend_breakout_keywords": keyword_res["ranked_keywords"],
        "taste_attribute_preferences": attr_prefs,
        "taste_country_profiles": country_profiles,
        "taste_functional_features": functional_features,
        "taste_price_distribution": price_dist,
        "nlp_review_predictions": predicted_reviews[pred_cols],
        "nlp_sentiment_summary": sentiment_summary,
        "nlp_review_aspects": aspects_df,
        "nlp_aspect_market_summary": aspect_market_summary,
        "nlp_aspect_quality_notes": quality_notes,
    }

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_source": dataset.source_name,
        "countries_analyzed": int(market_ranking["country_code"].nunique())
        if not market_ranking.empty
        else 0,
        "products_analyzed": int(len(dataset.market_products)),
        "reviews_analyzed": int(len(predicted_reviews)),
        "aspects_extracted": int(len(aspects_df)),
        "sentiment_model_eval": sentiment_eval,
        "absa_eval": absa_eval,
        "db_sync_stats": db_sync_stats,
    }
    exported = export_analysis_outputs(tables_to_export, metadata, output_dir=target_out)

    return {
        "metadata": metadata,
        "exported_files": {k: str(v) for k, v in exported.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chay phan he Phan tich thi truong, thi hieu va AI/NLP (Nguyen The Nguyen)."
    )
    parser.add_argument(
        "--source",
        choices=["sample", "db"],
        default="sample",
        help="Nguon du lieu dau vao: 'sample' (benchmark offline) hoac 'db' (PostgreSQL ceramic_bi_db).",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Cap nhat sentiment_label, sentiment_score, review_aspects va fact_customer_review vao PostgreSQL.",
    )
    args = parser.parse_args()

    result = run_full_analysis(source=args.source, save_db=args.save_db)
    print(json.dumps(result["metadata"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
