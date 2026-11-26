"""Ket noi PostgreSQL (OLTP & Star Schema) va nap du lieu benchmark cho phan he AI/NLP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .config import SAMPLE_DATA_DIR, DatabaseConfig

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:  # pragma: no cover - fallback khi chua cai psycopg2
    psycopg2 = None
    execute_values = None


@dataclass
class AnalysisDataset:
    """Tap DataFrame dau vao dung chung cho phan tich thi truong, xu huong, thi hieu va AI/NLP."""

    countries: pd.DataFrame
    market_regions: pd.DataFrame
    product_categories: pd.DataFrame
    trade_statistics: pd.DataFrame
    search_trends: pd.DataFrame
    trending_keywords: pd.DataFrame
    market_products: pd.DataFrame
    product_reviews: pd.DataFrame
    customers: pd.DataFrame | None = None
    source_name: str = "sample"


class PostgresConnector:
    """Quan ly truy van doc tu OLTP va ghi ket qua AI/NLP xuong PostgreSQL."""

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig.from_env()

    def connect(self) -> Any:
        """Mo ket noi toi PostgreSQL ceramic_bi_db."""
        if psycopg2 is None:
            raise RuntimeError(
                "Chua cai dat psycopg2-binary. Hay chay: pip install -r requirements.txt"
            )
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.dbname,
            user=self.config.user,
            password=self.config.password,
            options=f"-c search_path={self.config.schema}",
        )

    def load_analysis_dataset(self) -> AnalysisDataset:
        """Doc toan bo bang phan tich thi truong, xu huong, san pham va danh gia tu PostgreSQL."""
        queries = {
            "countries": "SELECT * FROM countries ORDER BY country_id",
            "market_regions": "SELECT * FROM market_regions ORDER BY region_id",
            "product_categories": "SELECT * FROM product_categories ORDER BY category_id",
            "trade_statistics": "SELECT * FROM trade_statistics ORDER BY trade_id",
            "search_trends": "SELECT * FROM search_trends ORDER BY trend_id",
            "trending_keywords": "SELECT * FROM trending_keywords ORDER BY keyword_id",
            "market_products": "SELECT * FROM market_products ORDER BY market_product_id",
            "customers": "SELECT * FROM customers ORDER BY customer_id",
            "product_reviews": "SELECT * FROM product_reviews ORDER BY review_id",
        }
        frames: dict[str, pd.DataFrame] = {}
        with self.connect() as conn:
            for name, sql in queries.items():
                frames[name] = pd.read_sql_query(sql, conn)
        return AnalysisDataset(source_name="postgresql", **frames)

    def save_review_predictions(self, predictions_df: pd.DataFrame) -> int:
        """Cap nhat cot sentiment_label va sentiment_score vao bang OLTP product_reviews."""
        if predictions_df.empty:
            return 0
        required = {"review_id", "sentiment_label", "sentiment_score"}
        missing = required - set(predictions_df.columns)
        if missing:
            raise ValueError(f"Thieu cot bat buoc khi cap nhat product_reviews: {sorted(missing)}")

        rows = [
            (str(r.sentiment_label), float(r.sentiment_score), int(r.review_id))
            for r in predictions_df[["sentiment_label", "sentiment_score", "review_id"]].itertuples(index=False)
        ]
        sql = """
            UPDATE product_reviews
            SET sentiment_label = data.sentiment_label,
                sentiment_score = data.sentiment_score
            FROM (VALUES %s) AS data(sentiment_label, sentiment_score, review_id)
            WHERE product_reviews.review_id = data.review_id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, rows, page_size=500)
            conn.commit()
        return len(rows)

    def save_review_aspects(self, aspects_df: pd.DataFrame) -> int:
        """Luu ket qua trich xuat khia canh khen/che vao bang OLTP review_aspects."""
        if aspects_df.empty:
            return 0
        required = {"review_id", "aspect_category", "aspect_sentiment", "extracted_phrase"}
        missing = required - set(aspects_df.columns)
        if missing:
            raise ValueError(f"Thieu cot bat buoc khi luu review_aspects: {sorted(missing)}")

        review_ids = sorted({int(rid) for rid in aspects_df["review_id"].unique()})
        rows = [
            (
                int(r.review_id),
                str(r.aspect_category),
                str(r.aspect_sentiment),
                str(r.extracted_phrase)[:250],
            )
            for r in aspects_df[["review_id", "aspect_category", "aspect_sentiment", "extracted_phrase"]].itertuples(index=False)
        ]
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM review_aspects WHERE review_id = ANY(%s)", (review_ids,))
                execute_values(
                    cur,
                    """
                    INSERT INTO review_aspects (review_id, aspect_category, aspect_sentiment, extracted_phrase)
                    VALUES %s
                    """,
                    rows,
                    page_size=500,
                )
            conn.commit()
        return len(rows)

    def sync_star_schema_reviews(self) -> int:
        """Dong bo du lieu AI/NLP tu OLTP sang dim_sentiment_aspect va fact_customer_review."""
        sql_dim_time = """
            INSERT INTO dim_time (full_date, year, quarter, month, week_of_year, period_label)
            SELECT DISTINCT
                COALESCE(pr.review_date, CURRENT_DATE) AS full_date,
                EXTRACT(YEAR FROM COALESCE(pr.review_date, CURRENT_DATE))::INT AS year,
                EXTRACT(QUARTER FROM COALESCE(pr.review_date, CURRENT_DATE))::INT AS quarter,
                EXTRACT(MONTH FROM COALESCE(pr.review_date, CURRENT_DATE))::INT AS month,
                EXTRACT(WEEK FROM COALESCE(pr.review_date, CURRENT_DATE))::INT AS week_of_year,
                TO_CHAR(COALESCE(pr.review_date, CURRENT_DATE), 'IYYY-"W"IW') AS period_label
            FROM product_reviews pr
            ON CONFLICT (full_date) DO NOTHING;
        """
        sql_dim_aspect = """
            INSERT INTO dim_sentiment_aspect (
                platform_source, sentiment_label, aspect_category, aspect_sentiment, is_verified_purchase
            )
            SELECT DISTINCT
                mp.platform_source,
                pr.sentiment_label,
                ra.aspect_category,
                ra.aspect_sentiment,
                COALESCE(c.verified_purchase, TRUE)
            FROM review_aspects ra
            JOIN product_reviews pr ON pr.review_id = ra.review_id
            JOIN market_products mp ON mp.market_product_id = pr.market_product_id
            LEFT JOIN customers c ON c.customer_id = pr.customer_id
            WHERE pr.sentiment_label IS NOT NULL
            ON CONFLICT (platform_source, sentiment_label, aspect_category, aspect_sentiment, is_verified_purchase)
            DO NOTHING;
        """
        sql_fact = """
            TRUNCATE TABLE fact_customer_review RESTART IDENTITY;
            INSERT INTO fact_customer_review (
                time_key, market_key, product_key, aspect_key,
                rating_stars, sentiment_score, market_price_usd,
                review_count, positive_review_flag, negative_review_flag
            )
            SELECT
                dt.time_key,
                dm.market_key,
                dp.product_key,
                dsa.aspect_key,
                pr.rating_stars,
                pr.sentiment_score,
                mp.price_usd,
                1 AS review_count,
                CASE WHEN ra.aspect_sentiment = 'Positive' THEN 1 ELSE 0 END AS positive_review_flag,
                CASE WHEN ra.aspect_sentiment = 'Negative' THEN 1 ELSE 0 END AS negative_review_flag
            FROM review_aspects ra
            JOIN product_reviews pr ON pr.review_id = ra.review_id
            JOIN market_products mp ON mp.market_product_id = pr.market_product_id
            LEFT JOIN customers c ON c.customer_id = pr.customer_id
            JOIN dim_time dt ON dt.full_date = COALESCE(pr.review_date, CURRENT_DATE)
            JOIN dim_market dm ON dm.source_country_id = mp.target_country_id AND dm.state_region_code = 'ALL'
            JOIN dim_product dp ON dp.source_product_id = mp.market_product_id AND dp.product_origin = 'International'
            JOIN dim_sentiment_aspect dsa
              ON dsa.platform_source = mp.platform_source
             AND dsa.sentiment_label = pr.sentiment_label
             AND dsa.aspect_category = ra.aspect_category
             AND dsa.aspect_sentiment = ra.aspect_sentiment
             AND dsa.is_verified_purchase = COALESCE(c.verified_purchase, TRUE);
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_dim_time)
                cur.execute(sql_dim_aspect)
                cur.execute(sql_fact)
                cur.execute("SELECT COUNT(*) FROM fact_customer_review")
                inserted = int(cur.fetchone()[0])
            conn.commit()
        return inserted


def load_sample_dataset(sample_dir: Path | None = None) -> AnalysisDataset:
    """Doc bo du lieu benchmark chuan hoa schema ERD phuc vu train/test va chay doc lap."""
    folder = sample_dir or SAMPLE_DATA_DIR
    return AnalysisDataset(
        countries=pd.read_csv(folder / "countries.csv"),
        market_regions=pd.read_csv(folder / "market_regions.csv"),
        product_categories=pd.read_csv(folder / "product_categories.csv"),
        trade_statistics=pd.read_csv(folder / "trade_statistics.csv"),
        search_trends=pd.read_csv(folder / "search_trends.csv", parse_dates=["week_start_date"]),
        trending_keywords=pd.read_csv(folder / "trending_keywords.csv"),
        market_products=pd.read_csv(folder / "market_products.csv"),
        product_reviews=pd.read_csv(folder / "product_reviews_labeled.csv", parse_dates=["review_date"]),
        customers=None,
        source_name="sample_benchmark",
    )
