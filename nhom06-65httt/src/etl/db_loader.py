"""D16 — PostgreSQL Database Loader for ceramic_bi_db.

Loads the cleaned, integrated dataset from ``nhom06-65httt/data/integrated/*.csv``
into PostgreSQL (``ceramic_bi_db``):
1. The 13 OLTP tables defined in ``src/database/01_init_oltp_erd_schema.sql``
2. The 8 OLAP Star Schema tables defined in ``src/database/02_init_olap_star_schema.sql``
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    ISOLATION_LEVEL_AUTOCOMMIT = None
    execute_values = None


_TABLE_LOAD_ORDER: Tuple[Tuple[str, str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    (
        "countries",
        "countries.csv",
        ("country_id", "country_code", "country_name", "region_continent", "currency_code", "is_key_market"),
        ("int", "str", "str", "str", "str", "bool"),
    ),
    (
        "market_regions",
        "market_regions.csv",
        ("region_id", "country_id", "region_code", "region_name"),
        ("int", "int", "str", "str"),
    ),
    (
        "product_categories",
        "product_categories.csv",
        ("category_id", "category_code", "category_name_vi", "category_name_en", "hs_code_mapping"),
        ("int", "str", "str", "str", "str"),
    ),
    (
        "trade_statistics",
        "trade_statistics.csv",
        (
            "trade_id",
            "reporter_country_id",
            "partner_country_id",
            "year",
            "trade_flow",
            "hs_code",
            "cmd_desc",
            "trade_value_usd",
            "fob_value_usd",
            "cif_value_usd",
            "net_weight_kg",
            "qty_unit",
            "qty_amount",
            "market_share_pct",
            "yoy_growth_rate",
            "data_source",
        ),
        (
            "int",
            "int",
            "int",
            "int",
            "str",
            "str",
            "str",
            "float",
            "float",
            "float",
            "float",
            "str",
            "float",
            "float",
            "float",
            "str",
        ),
    ),
    (
        "search_trends",
        "search_trends.csv",
        (
            "trend_id",
            "country_id",
            "region_id",
            "category_id",
            "search_term",
            "week_start_date",
            "week_number",
            "interest_score",
        ),
        ("int", "int", "int", "int", "str", "str", "int", "int"),
    ),
    (
        "trending_keywords",
        "trending_keywords.csv",
        (
            "keyword_id",
            "country_id",
            "category_id",
            "keyword_text",
            "related_attribute_type",
            "growth_pct",
            "trend_classification",
            "recorded_period",
        ),
        ("int", "int", "int", "str", "str", "float", "str", "str"),
    ),
    (
        "market_products",
        "market_products.csv",
        (
            "market_product_id",
            "external_sku",
            "platform_source",
            "target_country_id",
            "category_id",
            "product_name",
            "price_usd",
            "price_segment",
            "color",
            "shape",
            "material",
            "style",
            "is_dishwasher_safe",
            "is_microwave_safe",
            "avg_rating",
            "review_count",
            "image_url",
            "product_url",
        ),
        (
            "int",
            "str",
            "str",
            "int",
            "int",
            "str",
            "float",
            "str",
            "str",
            "str",
            "str",
            "str",
            "bool",
            "bool",
            "float",
            "int",
            "str",
            "str",
        ),
    ),
    (
        "customers",
        "customers.csv",
        (
            "customer_id",
            "external_reviewer_id",
            "reviewer_name",
            "country_id",
            "platform_source",
            "verified_purchase",
        ),
        ("int", "str", "str", "int", "str", "bool"),
    ),
    (
        "product_reviews",
        "product_reviews.csv",
        (
            "review_id",
            "market_product_id",
            "customer_id",
            "rating_stars",
            "review_title",
            "review_text",
            "review_date",
            "sentiment_label",
            "sentiment_score",
        ),
        ("int", "int", "int", "int", "str", "str", "str", "str", "float"),
    ),
    (
        "suppliers",
        "suppliers.csv",
        (
            "supplier_id",
            "supplier_code",
            "supplier_name",
            "address",
            "hotline",
            "website_url",
            "specialization",
            "min_monthly_capacity",
            "max_monthly_capacity",
            "avg_lead_time_days",
            "total_catalog_items",
            "reliability_rating",
        ),
        ("int", "str", "str", "str", "str", "str", "str", "int", "int", "int", "int", "float"),
    ),
    (
        "supplier_products",
        "supplier_products.csv",
        (
            "supplier_product_id",
            "supplier_id",
            "category_id",
            "product_code",
            "product_name",
            "price_vnd",
            "price_usd_equiv",
            "color",
            "shape",
            "material",
            "style",
            "is_dishwasher_safe",
            "is_heat_resistant",
            "min_order_qty",
            "image_url",
            "product_url",
        ),
        (
            "int",
            "int",
            "int",
            "str",
            "str",
            "float",
            "float",
            "str",
            "str",
            "str",
            "str",
            "bool",
            "bool",
            "int",
            "str",
            "str",
        ),
    ),
)


def _cast_value(raw: str, kind: str) -> Any:
    val = raw.strip() if isinstance(raw, str) else ""
    if val == "":
        return None
    if kind == "int":
        return int(float(val))
    if kind == "float":
        return float(val)
    if kind == "bool":
        return val.lower() in {"true", "1", "yes", "t"}
    return val


def _read_typed_rows(
    csv_path: Path,
    columns: Sequence[str],
    types: Sequence[str],
) -> List[Tuple[Any, ...]]:
    rows: List[Tuple[Any, ...]] = []
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                tuple(_cast_value(row.get(col, ""), kind) for col, kind in zip(columns, types))
            )
    return rows


def load_postgres_database(
    integrated_dir: Path,
    sql_dir: Path,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
) -> Dict[str, int]:
    """Create database ceramic_bi_db (if needed), initialize 21 tables, and load all rows."""
    if psycopg2 is None or execute_values is None:
        raise RuntimeError("psycopg2-binary is not installed")

    # 1. Connect to default 'postgres' database to create ceramic_bi_db if absent
    admin_conn = psycopg2.connect(
        host=host, port=port, dbname="postgres", user=user, password=password
    )
    admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with admin_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{dbname}" ENCODING \'UTF8\'')
    admin_conn.close()

    # 2. Connect to target database and run DDL scripts 01 & 02
    conn = psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    )
    counts: Dict[str, int] = {}
    with conn:
        with conn.cursor() as cur:
            oltp_sql = (sql_dir / "01_init_oltp_erd_schema.sql").read_text(encoding="utf-8")
            olap_sql = (sql_dir / "02_init_olap_star_schema.sql").read_text(encoding="utf-8")
            cur.execute(oltp_sql)
            cur.execute(olap_sql)

            for table_name, filename, columns, types in _TABLE_LOAD_ORDER:
                rows = _read_typed_rows(integrated_dir / filename, columns, types)
                if not rows:
                    counts[table_name] = 0
                    continue
                col_list = ", ".join(columns)
                execute_values(
                    cur,
                    f"INSERT INTO {table_name} ({col_list}) VALUES %s",
                    rows,
                    page_size=1000,
                )
                pk_col = columns[0]
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', '{pk_col}'), "
                    f"(SELECT COALESCE(MAX({pk_col}), 1) FROM {table_name}))"
                )
                counts[table_name] = len(rows)

            # Populate Star Schema Dimensions & Fact
            cur.execute(
                """
                INSERT INTO dim_market (
                    source_country_id, country_code, country_name, region_continent,
                    state_region_code, state_region_name, currency_code, is_key_market
                )
                SELECT country_id, country_code, country_name, region_continent,
                       'ALL', 'National', currency_code, is_key_market
                FROM countries
                ON CONFLICT DO NOTHING;

                INSERT INTO dim_market (
                    source_country_id, country_code, country_name, region_continent,
                    state_region_code, state_region_name, currency_code, is_key_market
                )
                SELECT c.country_id, c.country_code, c.country_name, c.region_continent,
                       mr.region_code, mr.region_name, c.currency_code, c.is_key_market
                FROM market_regions mr
                JOIN countries c ON c.country_id = mr.country_id
                ON CONFLICT DO NOTHING;

                INSERT INTO dim_supplier (
                    source_supplier_id, supplier_code, supplier_name, address,
                    specialization, min_monthly_capacity, max_monthly_capacity,
                    avg_lead_time_days, reliability_rating
                )
                SELECT supplier_id, supplier_code, supplier_name, address,
                       specialization, min_monthly_capacity, max_monthly_capacity,
                       avg_lead_time_days, reliability_rating
                FROM suppliers
                ON CONFLICT DO NOTHING;

                INSERT INTO dim_product (
                    source_product_id, product_origin, category_code, category_name_vi,
                    category_name_en, hs_code, product_name, color, shape, material,
                    style, is_dishwasher_safe, is_heat_resistant, price_segment
                )
                SELECT category_id, 'Category_Level', category_code, category_name_vi,
                       category_name_en, hs_code_mapping, category_name_en,
                       NULL, NULL, NULL, NULL, FALSE, FALSE, NULL
                FROM product_categories;

                INSERT INTO dim_product (
                    source_product_id, product_origin, category_code, category_name_vi,
                    category_name_en, hs_code, product_name, color, shape, material,
                    style, is_dishwasher_safe, is_heat_resistant, price_segment
                )
                SELECT mp.market_product_id, 'International', pc.category_code, pc.category_name_vi,
                       pc.category_name_en, pc.hs_code_mapping, mp.product_name, mp.color, mp.shape,
                       mp.material, mp.style, mp.is_dishwasher_safe, mp.is_microwave_safe, mp.price_segment
                FROM market_products mp
                JOIN product_categories pc ON pc.category_id = mp.category_id;

                INSERT INTO dim_product (
                    source_product_id, product_origin, category_code, category_name_vi,
                    category_name_en, hs_code, product_name, color, shape, material,
                    style, is_dishwasher_safe, is_heat_resistant, price_segment
                )
                SELECT sp.supplier_product_id, 'Domestic', pc.category_code, pc.category_name_vi,
                       pc.category_name_en, pc.hs_code_mapping, sp.product_name, sp.color, sp.shape,
                       sp.material, sp.style, sp.is_dishwasher_safe, sp.is_heat_resistant, NULL
                FROM supplier_products sp
                JOIN product_categories pc ON pc.category_id = sp.category_id;

                INSERT INTO dim_time (full_date, year, quarter, month, week_of_year, period_label)
                SELECT DISTINCT
                    MAKE_DATE(year, 1, 1), year, 1, 1, 1, year::TEXT
                FROM trade_statistics
                ON CONFLICT (full_date) DO NOTHING;

                INSERT INTO dim_time (full_date, year, quarter, month, week_of_year, period_label)
                SELECT DISTINCT
                    week_start_date::DATE,
                    EXTRACT(YEAR FROM week_start_date::DATE)::INT,
                    EXTRACT(QUARTER FROM week_start_date::DATE)::INT,
                    EXTRACT(MONTH FROM week_start_date::DATE)::INT,
                    COALESCE(week_number, 1),
                    TO_CHAR(week_start_date::DATE, 'IYYY-"W"IW')
                FROM search_trends
                ON CONFLICT (full_date) DO NOTHING;

                INSERT INTO fact_market_demand (
                    time_key, market_key, product_key, trade_flow,
                    trade_value_usd, fob_value_usd, cif_value_usd, net_weight_kg, qty_amount
                )
                SELECT
                    dt.time_key,
                    dm.market_key,
                    dp.product_key,
                    ts.trade_flow,
                    ts.trade_value_usd,
                    COALESCE(ts.fob_value_usd, 0),
                    COALESCE(ts.cif_value_usd, 0),
                    COALESCE(ts.net_weight_kg, 0),
                    COALESCE(ts.qty_amount, 0)
                FROM trade_statistics ts
                JOIN dim_time dt ON dt.full_date = MAKE_DATE(ts.year, 1, 1)
                JOIN dim_market dm ON dm.source_country_id = ts.partner_country_id AND dm.state_region_code = 'ALL'
                JOIN dim_product dp ON dp.product_origin = 'Category_Level'
                    AND dp.source_product_id = (
                        CASE ts.hs_code
                            WHEN '6911' THEN 1
                            WHEN '6912' THEN 3
                            ELSE 4
                        END
                    );
                """
            )
            for olap_table in ("dim_time", "dim_market", "dim_product", "dim_supplier", "fact_market_demand"):
                cur.execute(f"SELECT COUNT(*) FROM {olap_table}")
                counts[olap_table] = int(cur.fetchone()[0])

    conn.close()
    return counts


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Load integrated ETL dataset into PostgreSQL ceramic_bi_db."
    )
    parser.add_argument(
        "--integrated",
        type=Path,
        default=project_root / "data" / "integrated",
        help="Path to integrated CSV dataset folder",
    )
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.getenv("DB_NAME", "ceramic_bi_db"))
    parser.add_argument("--user", default=os.getenv("DB_USER", "postgres"))
    parser.add_argument("--password", default=os.getenv("DB_PASSWORD", "postgres"))
    args = parser.parse_args()

    print(f"=== Loading PostgreSQL Database ({args.host}:{args.port}/{args.dbname}) ===")
    pg_counts = load_postgres_database(
        integrated_dir=args.integrated,
        sql_dir=project_root / "src" / "database",
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )
    for tbl, cnt in pg_counts.items():
        print(f"  - {tbl:<24} : {cnt:>7,} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
