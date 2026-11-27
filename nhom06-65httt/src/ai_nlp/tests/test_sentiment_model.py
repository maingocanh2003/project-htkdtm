"""Kiem thu mo hinh AI/NLP phan loai cam xuc danh gia khach hang (FR-2.4)."""

from __future__ import annotations

import pandas as pd

from src.ai_nlp.config import SENTIMENT_LABELS
from src.ai_nlp.db_connector import load_sample_dataset
from src.ai_nlp.sentiment_model import CeramicSentimentModel, clean_review_text


def test_clean_review_text_preserves_negation_bigrams():
    cleaned = clean_review_text("Not dishwasher safe! No chipping at all.")
    assert "not_dishwasher" in cleaned
    assert "not_chipping" in cleaned


def test_sentiment_model_trains_evaluates_and_predicts_high_f1(tmp_path):
    ds = load_sample_dataset()
    model = CeramicSentimentModel(random_state=42)
    report = model.train_and_evaluate(ds.product_reviews, label_col="true_sentiment", test_size=0.2)

    assert report["selected_model"] in {"LogisticRegression", "CalibratedLinearSVC", "ComplementNB"}
    assert report["test_metrics"]["accuracy"] >= 0.90
    assert report["test_metrics"]["macro_f1"] >= 0.88
    assert len(report["test_metrics"]["confusion_matrix"]) == 3

    preds = model.predict(ds.product_reviews.head(15))
    assert set(preds["sentiment_label"].unique()).issubset(set(SENTIMENT_LABELS))
    assert preds["sentiment_score"].between(0.0, 1.0).all()

    model_path, metrics_path = model.save(tmp_path)
    assert model_path.exists() and metrics_path.exists()
    reloaded = CeramicSentimentModel.load(model_path)
    reloaded_preds = reloaded.predict(
        pd.DataFrame(
            [
                {
                    "review_id": 9999,
                    "review_title": "Broken lid",
                    "review_text": "Terrible packaging, arrived shattered in transit.",
                }
            ]
        )
    )
    assert reloaded_preds.iloc[0]["sentiment_label"] == "Negative"
