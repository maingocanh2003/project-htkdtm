"""FR-2.5: Trich xuat khia canh san pham duoc khen/che (Aspect-Based Sentiment Analysis - ABSA)."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from .config import ASPECT_CATEGORIES

# Tu dien nhan dien 5 nhom khia canh cot loi trong danh gia gom su
ASPECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Glaze Durability": (
        "glaze", "crazing", "scratch", "scratches", "chip", "chipped", "chipping",
        "flaking", "enamel", "pinhole", "pinholes", "hairline", "glazing", "finish",
    ),
    "Packaging": (
        "packaging", "package", "packed", "box", "double-boxed", "foam", "bubble",
        "sleeve", "sleeves", "mailer", "cardboard", "divider", "dividers", "transit",
        "shipping", "delivery", "arrived", "shattered", "broken", "intact",
    ),
    "Design & Color": (
        "design", "color", "colour", "pattern", "shape", "aesthetic", "minimalist",
        "cobalt", "speckled", "motif", "tones", "earthy", "silhouette", "craftsmanship",
        "artisanal", "hand-painted", "handle", "rim", "wobbles", "asymmetrical", "dull",
    ),
    "Heat/Dishwasher": (
        "dishwasher", "microwave", "oven", "heat", "boiling", "hot", "warm",
        "overheats", "fade", "faded", "top rack", "cycles", "hand-washing", "thermal",
    ),
    "Price/Value": (
        "price", "priced", "value", "money", "worth", "penny", "expensive",
        "overpriced", "cheap", "tag", "cost", "mid-range",
    ),
}

POSITIVE_CUES = (
    "smooth", "scratch-resistant", "glossy", "zero crazing", "zero breakage",
    "no hairline", "no chipping", "not a single chip", "durable", "heirloom",
    "sturdy", "intact", "well-cushioned", "impressive", "secure", "protective",
    "gorgeous", "stunning", "vibrant", "elegant", "love", "elevate", "timeless",
    "balanced", "dishwasher safe", "microwave safe", "oven-ready", "effortlessly",
    "no warping", "great value", "reasonably priced", "worth every penny",
    "wonderfully", "clean", "artisanal",
)

NEGATIVE_CUES = (
    "chipped", "crazing", "scratches", "scratch", "uneven", "pinholes", "rough",
    "flaking", "thin", "broken", "shattered", "cracked", "terrible", "poorly",
    "flimsy", "no padding", "zero foam", "dull", "muddy", "awkwardly", "clumsy",
    "blurry", "wobbles", "smaller than expected", "burning hot", "overheats",
    "not actually dishwasher safe", "not dishwasher safe", "faded", "overpriced",
    "too expensive", "not worth", "mediocre", "minor flaws", "mass-produced",
)

NEUTRAL_CUES = (
    "decent", "acceptable", "neither", "basic", "standard", "could use",
    "okay", "moderately", "prefer hand-washing", "top rack", "fair price",
    "about right", "fairly standard", "just like the listing",
)


def split_clauses(text: str) -> list[str]:
    """Tach van ban danh gia thanh cac menh de nho theo dau cau va lien tu doi lap."""
    if not isinstance(text, str) or not text.strip():
        return []
    parts = re.split(r"[.!?;]+|\b(?:however|but|although|though|yet)\b", text, flags=re.IGNORECASE)
    return [p.strip(" ,:-") for p in parts if p and p.strip(" ,:-")]


def _score_clause_sentiment(clause: str) -> str:
    """Xac dinh cam xuc cap menh de ket hop phu dinh va tu khoa mien gom su."""
    low = clause.lower()

    # Kiem tra cac cum phu dinh tich cuc dac thu truoc (vd: "no breakage", "zero crazing")
    negated_good_patterns = (
        r"\b(no|zero|without|not a single)\s+(crazing|chip|chips|chipping|breakage|hairline|warping|cracking|fading|marks)\b",
        r"\bnothing broke\b",
    )
    pos_score = sum(1 for cue in POSITIVE_CUES if cue in low)
    neg_score = sum(1 for cue in NEGATIVE_CUES if cue in low)
    neu_score = sum(1 for cue in NEUTRAL_CUES if cue in low)

    for pat in negated_good_patterns:
        if re.search(pat, low):
            pos_score += 2
            neg_score = max(0, neg_score - 1)

    if re.search(r"\bnot\s+(actually\s+)?(worth|dishwasher\s+safe|microwave\s+safe|heat\s+safe)\b", low):
        neg_score += 2
        pos_score = max(0, pos_score - 1)

    if pos_score > neg_score and pos_score >= neu_score:
        return "Positive"
    if neg_score > pos_score and neg_score >= neu_score:
        return "Negative"
    if neu_score > 0:
        return "Neutral"
    if pos_score > 0 and neg_score == 0:
        return "Positive"
    if neg_score > 0 and pos_score == 0:
        return "Negative"
    return "Neutral"


def extract_aspects_from_review(
    review_id: int,
    review_text: str,
    fallback_sentiment: str | None = None,
) -> list[dict[str, Any]]:
    """Trich xuat danh sach (aspect_category, aspect_sentiment, extracted_phrase) cho 1 danh gia."""
    clauses = split_clauses(review_text)
    found: dict[str, dict[str, Any]] = {}

    for clause in clauses:
        low = clause.lower()
        clause_sent = _score_clause_sentiment(clause)
        for aspect in ASPECT_CATEGORIES:
            keywords = ASPECT_KEYWORDS[aspect]
            if any(re.search(rf"\b{re.escape(kw)}\b", low) for kw in keywords):
                existing = found.get(aspect)
                if existing is None:
                    found[aspect] = {
                        "review_id": int(review_id),
                        "aspect_category": aspect,
                        "aspect_sentiment": clause_sent,
                        "extracted_phrase": clause[:250],
                    }
                elif existing["aspect_sentiment"] == "Neutral" and clause_sent != "Neutral":
                    found[aspect]["aspect_sentiment"] = clause_sent
                    found[aspect]["extracted_phrase"] = clause[:250]

    # Neu khong khop tu khoa ro rang nhung co fallback_sentiment, gan vao Design & Color mac dinh
    if not found and fallback_sentiment in ("Positive", "Neutral", "Negative") and clauses:
        found["Design & Color"] = {
            "review_id": int(review_id),
            "aspect_category": "Design & Color",
            "aspect_sentiment": fallback_sentiment,
            "extracted_phrase": clauses[0][:250],
        }
    return list(found.values())


def extract_aspects_batch(reviews_df: pd.DataFrame) -> pd.DataFrame:
    """Chay trich xuat khia canh cho toan bo bang product_reviews."""
    rows: list[dict[str, Any]] = []
    for row in reviews_df.itertuples(index=False):
        fallback = getattr(row, "sentiment_label", None)
        rows.extend(
            extract_aspects_from_review(
                review_id=int(row.review_id),
                review_text=str(row.review_text),
                fallback_sentiment=fallback,
            )
        )
    if not rows:
        return pd.DataFrame(
            columns=["review_id", "aspect_category", "aspect_sentiment", "extracted_phrase"]
        )
    return pd.DataFrame(rows)


def _parse_true_aspects(raw: str) -> set[tuple[str, str]]:
    if not isinstance(raw, str) or not raw.strip():
        return set()
    pairs: set[tuple[str, str]] = set()
    for item in raw.split(";"):
        if ":" in item:
            asp, sent = item.split(":", 1)
            pairs.add((asp.strip(), sent.strip()))
    return pairs


def evaluate_aspect_extraction(
    labeled_reviews_df: pd.DataFrame,
    predicted_aspects_df: pd.DataFrame,
    test_review_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Danh gia do chinh xac trich xuat khia canh (Category & Joint Aspect+Sentiment) tren tap kiem thu."""
    eval_df = labeled_reviews_df.copy()
    if test_review_ids:
        eval_df = eval_df[eval_df["review_id"].isin(test_review_ids)]

    pred_by_review: dict[int, set[tuple[str, str]]] = {}
    for r in predicted_aspects_df.itertuples(index=False):
        pred_by_review.setdefault(int(r.review_id), set()).add(
            (str(r.aspect_category), str(r.aspect_sentiment))
        )

    cat_tp = cat_fp = cat_fn = 0
    joint_tp = joint_fp = joint_fn = 0
    per_aspect_counts: dict[str, dict[str, int]] = {
        a: {"tp": 0, "fp": 0, "fn": 0} for a in ASPECT_CATEGORIES
    }

    for r in eval_df.itertuples(index=False):
        true_pairs = _parse_true_aspects(getattr(r, "true_aspects", ""))
        pred_pairs = pred_by_review.get(int(r.review_id), set())

        true_cats = {a for a, _ in true_pairs}
        pred_cats = {a for a, _ in pred_pairs}

        cat_tp += len(true_cats & pred_cats)
        cat_fp += len(pred_cats - true_cats)
        cat_fn += len(true_cats - pred_cats)

        joint_tp += len(true_pairs & pred_pairs)
        joint_fp += len(pred_pairs - true_pairs)
        joint_fn += len(true_pairs - pred_pairs)

        for asp in ASPECT_CATEGORIES:
            in_true = asp in true_cats
            in_pred = asp in pred_cats
            if in_true and in_pred:
                per_aspect_counts[asp]["tp"] += 1
            elif in_pred and not in_true:
                per_aspect_counts[asp]["fp"] += 1
            elif in_true and not in_pred:
                per_aspect_counts[asp]["fn"] += 1

    def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * rec) / (p + rec) if (p + rec) > 0 else 0.0
        return {"precision": round(p, 4), "recall": round(rec, 4), "f1_score": round(f1, 4)}

    per_aspect_metrics = {
        asp: {**_prf(c["tp"], c["fp"], c["fn"]), "support": c["tp"] + c["fn"]}
        for asp, c in per_aspect_counts.items()
    }

    return {
        "evaluated_reviews": int(len(eval_df)),
        "aspect_category_detection": _prf(cat_tp, cat_fp, cat_fn),
        "joint_aspect_sentiment": _prf(joint_tp, joint_fp, joint_fn),
        "per_aspect_category": per_aspect_metrics,
    }


def summarize_aspects_for_market(
    aspects_df: pd.DataFrame,
    reviews_df: pd.DataFrame,
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Tong hop ty le khen/che theo tung khia canh, quoc gia va dong san pham."""
    if aspects_df.empty or reviews_df.empty or products_df.empty:
        return pd.DataFrame()

    joined = (
        aspects_df.merge(
            reviews_df[["review_id", "market_product_id", "rating_stars"]],
            on="review_id",
            how="left",
        )
        .merge(
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
            ["country_code", "country_name", "category_code", "category_name_vi", "aspect_category"],
            as_index=False,
        )
        .agg(
            mention_count=("review_id", "count"),
            positive_count=("aspect_sentiment", lambda s: int((s == "Positive").sum())),
            neutral_count=("aspect_sentiment", lambda s: int((s == "Neutral").sum())),
            negative_count=("aspect_sentiment", lambda s: int((s == "Negative").sum())),
            avg_rating_stars=("rating_stars", "mean"),
        )
    )
    summary["positive_rate_pct"] = np.where(
        summary["mention_count"] > 0,
        (summary["positive_count"] / summary["mention_count"]) * 100.0,
        0.0,
    ).round(2)
    summary["complaint_rate_pct"] = np.where(
        summary["mention_count"] > 0,
        (summary["negative_count"] / summary["mention_count"]) * 100.0,
        0.0,
    ).round(2)
    summary["avg_rating_stars"] = summary["avg_rating_stars"].round(2)
    return summary.sort_values(
        ["country_code", "complaint_rate_pct", "mention_count"], ascending=[True, False, False]
    ).reset_index(drop=True)
