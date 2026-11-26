"""Xuat bo du lieu ket qua phan tich KPI, thi hieu va AI/NLP phuc vu Dashboard BI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import OUTPUTS_DIR


def build_sentiment_summary(
    predicted_reviews_df: pd.DataFrame,
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Tong hop KPI danh gia khach hang: avg rating, ty le Positive/Neutral/Negative theo san, quoc gia va dong SP."""
    if predicted_reviews_df.empty or products_df.empty:
        return pd.DataFrame()

    joined = (
        predicted_reviews_df.merge(
            products_df[["market_product_id", "platform_source", "target_country_id", "category_id"]],
            on="market_product_id",
            how="left",
        )
        .merge(
            countries_df[["country_id", "country_code", "country_name"]],
            left_on="target_country_id",
            right_on="country_id",
            how="left",
        )
        .merge(
            categories_df[["category_id", "category_code", "category_name_vi"]],
            on="category_id",
            how="left",
        )
    )

    summary = (
        joined.groupby(
            ["platform_source", "country_code", "country_name", "category_code", "category_name_vi"],
            as_index=False,
        )
        .agg(
            total_reviews=("review_id", "count"),
            avg_rating_score=("rating_stars", "mean"),
            avg_sentiment_confidence=("sentiment_score", "mean"),
            positive_count=("sentiment_label", lambda s: int((s == "Positive").sum())),
            neutral_count=("sentiment_label", lambda s: int((s == "Neutral").sum())),
            negative_count=("sentiment_label", lambda s: int((s == "Negative").sum())),
        )
    )
    summary["positive_sentiment_rate_pct"] = np.where(
        summary["total_reviews"] > 0,
        (summary["positive_count"] / summary["total_reviews"]) * 100.0,
        0.0,
    ).round(2)
    summary["negative_sentiment_rate_pct"] = np.where(
        summary["total_reviews"] > 0,
        (summary["negative_count"] / summary["total_reviews"]) * 100.0,
        0.0,
    ).round(2)
    summary["avg_rating_score"] = summary["avg_rating_score"].round(2)
    summary["avg_sentiment_confidence"] = summary["avg_sentiment_confidence"].round(4)
    return summary.sort_values(["country_code", "total_reviews"], ascending=[True, False]).reset_index(
        drop=True
    )


def build_quality_packaging_notes(aspect_market_summary: pd.DataFrame) -> pd.DataFrame:
    """Tu dong sinh khuyen nghi ky thuat & dong goi tu ty le phan nan theo khia canh cua tung thi truong."""
    if aspect_market_summary.empty:
        return pd.DataFrame()

    advice_map = {
        "Packaging": "Gia co hop carton 2 lop va xop dinh hinh chong soc cho tung san pham.",
        "Glaze Durability": "Kiem soat nhiet do nung va do day lop men chong xuoc, chong ran men.",
        "Heat/Dishwasher": "Dam bao tieu chuan an toan may rua bat va thu soc nhiet lo vi song.",
        "Design & Color": "Ra soat dong nhat mau men va ty le tay cam/mieng san pham theo mau chuan.",
        "Price/Value": "Toi uu quy cach dong bo (set) va bao bi cao cap tuong xung gia ban.",
    }

    complaints = aspect_market_summary[aspect_market_summary["negative_count"] > 0].copy()
    if complaints.empty:
        return pd.DataFrame()

    complaints["recommended_action"] = complaints["aspect_category"].map(
        lambda a: advice_map.get(a, "Kiem tra chat luong truoc khi xuat xuong.")
    )
    complaints["priority_level"] = np.where(
        complaints["complaint_rate_pct"] >= 35.0,
        "High",
        np.where(complaints["complaint_rate_pct"] >= 20.0, "Medium", "Low"),
    )
    return complaints.sort_values(
        ["complaint_rate_pct", "negative_count"], ascending=[False, False]
    ).reset_index(drop=True)


def export_analysis_outputs(
    tables: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Luu toan bo bang ket qua CSV va file tong hop JSON phuc vu Dashboard BI."""
    target = output_dir or OUTPUTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    exported: dict[str, Path] = {}

    for name, df in tables.items():
        if df is None:
            continue
        csv_path = target / f"{name}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        exported[name] = csv_path

    bundle = {
        "metadata": metadata,
        "top_10_potential_markets": tables["market_potential_ranking"]
        .head(10)
        .to_dict(orient="records")
        if not tables["market_potential_ranking"].empty
        else [],
        "country_taste_profiles": tables["taste_country_profiles"].to_dict(orient="records")
        if not tables["taste_country_profiles"].empty
        else [],
        "breakout_keywords": tables["trend_breakout_keywords"].to_dict(orient="records")
        if not tables["trend_breakout_keywords"].empty
        else [],
        "sentiment_summary": tables["nlp_sentiment_summary"].to_dict(orient="records")
        if not tables["nlp_sentiment_summary"].empty
        else [],
        "aspect_market_summary": tables["nlp_aspect_market_summary"].to_dict(orient="records")
        if not tables["nlp_aspect_market_summary"].empty
        else [],
    }
    json_path = target / "dashboard_analysis_bundle.json"
    json_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    exported["dashboard_analysis_bundle"] = json_path
    return exported
