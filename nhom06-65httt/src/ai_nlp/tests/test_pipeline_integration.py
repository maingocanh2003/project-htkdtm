"""Kiem thu tich hop toan bo pipeline AI/NLP & xuat ket qua Dashboard BI."""

from __future__ import annotations

import json

from src.ai_nlp.run_pipeline import run_full_analysis


def test_run_full_analysis_sample_pipeline(tmp_path):
    out_dir = tmp_path / "outputs"
    model_dir = tmp_path / "models"
    result = run_full_analysis(
        source="sample",
        save_db=False,
        output_dir=out_dir,
        model_dir=model_dir,
    )
    meta = result["metadata"]
    assert meta["countries_analyzed"] >= 130
    assert meta["products_analyzed"] == 240
    assert meta["reviews_analyzed"] == 600
    assert meta["aspects_extracted"] >= 600
    assert meta["sentiment_model_eval"]["test_metrics"]["accuracy"] >= 0.90
    assert meta["absa_eval"]["joint_aspect_sentiment"]["f1_score"] >= 0.85

    bundle_path = out_dir / "dashboard_analysis_bundle.json"
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert len(bundle["top_10_potential_markets"]) == 10
    assert len(bundle["country_taste_profiles"]) == 5
