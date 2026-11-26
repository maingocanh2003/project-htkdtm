"""FR-2.4: Mo hinh AI/NLP phan loai cam xuc danh gia khach hang (Positive, Neutral, Negative) va danh gia tren tap kiem thu."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from .config import MODELS_DIR, SENTIMENT_LABELS

NEGATION_WORDS = {"not", "no", "never", "neither", "nor", "hardly", "barely", "didnt", "didn't", "isnt", "isn't", "wasnt", "wasn't", "dont", "don't"}


def clean_review_text(text: str) -> str:
    """Tien xu ly van ban danh gia va bao toan cum phu dinh (VD: not_safe, no_chip)."""
    if not isinstance(text, str):
        return ""
    normalized = text.lower().strip()
    normalized = re.sub(r"[^a-z0-9'\s\-]", " ", normalized)
    tokens = normalized.split()
    out_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in NEGATION_WORDS and i + 1 < len(tokens):
            out_tokens.append(f"not_{tokens[i + 1]}")
            i += 2
        else:
            out_tokens.append(tok)
            i += 1
    return " ".join(out_tokens)


def combine_review_fields(df: pd.DataFrame) -> pd.Series:
    """Ket hop review_title va review_text thanh van ban dau vao thong nhat."""
    titles = df["review_title"].fillna("") if "review_title" in df.columns else pd.Series("", index=df.index)
    texts = df["review_text"].fillna("")
    return (titles.astype(str) + ". " + texts.astype(str)).apply(clean_review_text)


def _build_vectorizer() -> FeatureUnion:
    """Ket hop dac trung TF-IDF tu (word 1-2 grams) va ky tu (char_wb 3-5 grams)."""
    return FeatureUnion(
        [
            (
                "word_tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=8000,
                    sublinear_tf=True,
                ),
            ),
            (
                "char_tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=3,
                    max_features=8000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _candidate_estimators(random_state: int = 42) -> dict[str, Any]:
    """Danh sach mo hinh ung vien de so sanh va chon mo hinh tot nhat qua Cross-Validation."""
    return {
        "LogisticRegression": LogisticRegression(
            C=2.0,
            max_iter=1500,
            class_weight="balanced",
            random_state=random_state,
        ),
        "CalibratedLinearSVC": CalibratedClassifierCV(
            estimator=LinearSVC(C=1.0, class_weight="balanced", random_state=random_state),
            cv=3,
            method="sigmoid",
        ),
        "ComplementNB": ComplementNB(alpha=0.5),
    }


class CeramicSentimentModel:
    """Pipeline AI/NLP huan luyen, so sanh mo hinh, danh gia kiem thu va du doan cam xuc."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.pipeline: Pipeline | None = None
        self.best_model_name: str = ""
        self.evaluation_report: dict[str, Any] = {}
        self.test_review_ids: list[int] = []

    def train_and_evaluate(
        self,
        labeled_reviews_df: pd.DataFrame,
        label_col: str = "true_sentiment",
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        """Huan luyen, doi chieu 3 thuat toan bang 5-Fold CV va danh gia tren tap kiem thu doc lap."""
        df = labeled_reviews_df[labeled_reviews_df[label_col].isin(SENTIMENT_LABELS)].copy()
        if df.empty:
            raise ValueError(f"Khong co du lieu hop le voi cot nhan '{label_col}'.")

        X_text = combine_review_fields(df)
        y = df[label_col].astype(str)

        train_idx, test_idx = train_test_split(
            df.index,
            test_size=test_size,
            stratify=y,
            random_state=self.random_state,
        )
        X_train, X_test = X_text.loc[train_idx], X_text.loc[test_idx]
        y_train, y_test = y.loc[train_idx], y.loc[test_idx]
        self.test_review_ids = [int(rid) for rid in df.loc[test_idx, "review_id"].tolist()]

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=self.random_state)
        cv_comparison: dict[str, dict[str, float]] = {}
        best_score = -1.0
        best_name = ""
        best_pipeline: Pipeline | None = None

        for name, estimator in _candidate_estimators(self.random_state).items():
            pipe = Pipeline([("features", _build_vectorizer()), ("clf", estimator)])
            scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_macro")
            mean_f1 = float(np.mean(scores))
            std_f1 = float(np.std(scores))
            cv_comparison[name] = {
                "cv_macro_f1_mean": round(mean_f1, 4),
                "cv_macro_f1_std": round(std_f1, 4),
            }
            if mean_f1 > best_score:
                best_score = mean_f1
                best_name = name
                best_pipeline = pipe

        assert best_pipeline is not None
        best_pipeline.fit(X_train, y_train)
        self.pipeline = best_pipeline
        self.best_model_name = best_name

        y_pred = best_pipeline.predict(X_test)
        y_proba = best_pipeline.predict_proba(X_test)
        classes = list(best_pipeline.classes_)
        conf_scores = [round(float(np.max(p)), 4) for p in y_proba]

        labels_order = list(SENTIMENT_LABELS)
        cm = confusion_matrix(y_test, y_pred, labels=labels_order)
        p_cls, r_cls, f1_cls, sup_cls = precision_recall_fscore_support(
            y_test, y_pred, labels=labels_order, zero_division=0
        )
        per_class = {
            lbl: {
                "precision": round(float(p_cls[i]), 4),
                "recall": round(float(r_cls[i]), 4),
                "f1_score": round(float(f1_cls[i]), 4),
                "support": int(sup_cls[i]),
            }
            for i, lbl in enumerate(labels_order)
        }

        test_df = df.loc[test_idx].copy()
        test_df["predicted_sentiment"] = y_pred
        test_df["confidence_score"] = conf_scores
        rating_by_pred = (
            test_df.groupby("predicted_sentiment")["rating_stars"]
            .agg(["count", "mean"])
            .round(2)
            .to_dict(orient="index")
        )

        self.evaluation_report = {
            "selected_model": best_name,
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "classes": classes,
            "cv_model_comparison": cv_comparison,
            "test_metrics": {
                "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
                "macro_f1": round(float(f1_score(y_test, y_pred, average="macro")), 4),
                "weighted_f1": round(float(f1_score(y_test, y_pred, average="weighted")), 4),
                "per_class": per_class,
                "confusion_matrix_labels": labels_order,
                "confusion_matrix": cm.tolist(),
                "classification_report_text": classification_report(
                    y_test, y_pred, labels=labels_order, digits=4, zero_division=0
                ),
            },
            "rating_vs_sentiment_check": rating_by_pred,
        }
        return self.evaluation_report

    def predict(self, reviews_df: pd.DataFrame) -> pd.DataFrame:
        """Du doan sentiment_label va sentiment_score (0.0-1.0) cho danh sach danh gia."""
        if self.pipeline is None:
            raise RuntimeError("Mo hinh chua duoc huan luyen hoac nap tu file.")
        if reviews_df.empty:
            return reviews_df.copy()

        X_text = combine_review_fields(reviews_df)
        preds = self.pipeline.predict(X_text)
        probs = self.pipeline.predict_proba(X_text)
        max_probs = np.clip(np.max(probs, axis=1), 0.0, 1.0).round(4)

        out = reviews_df.copy()
        out["sentiment_label"] = preds
        out["sentiment_score"] = max_probs
        return out

    def save(self, model_dir: Path | None = None) -> tuple[Path, Path]:
        """Luu pipeline da huan luyen (.joblib) va bao cao danh gia (.json)."""
        if self.pipeline is None:
            raise RuntimeError("Khong co mo hinh de luu.")
        target = model_dir or MODELS_DIR
        target.mkdir(parents=True, exist_ok=True)
        model_path = target / "sentiment_pipeline.joblib"
        metrics_path = target / "sentiment_eval_metrics.json"
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "best_model_name": self.best_model_name,
                "test_review_ids": self.test_review_ids,
            },
            model_path,
        )
        metrics_path.write_text(
            json.dumps(self.evaluation_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return model_path, metrics_path

    @classmethod
    def load(cls, model_path: Path | None = None) -> "CeramicSentimentModel":
        """Nap mo hinh cam xuc da luu tu dia."""
        path = model_path or (MODELS_DIR / "sentiment_pipeline.joblib")
        payload = joblib.load(path)
        inst = cls()
        inst.pipeline = payload["pipeline"]
        inst.best_model_name = payload["best_model_name"]
        inst.test_review_ids = payload.get("test_review_ids", [])
        return inst
