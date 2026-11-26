"""FR-2.3: Phan tich thi hieu tieu dung theo 5 nhom thuoc tinh san pham, cong nang va phan khuc gia."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import classify_price_segment


ATTRIBUTE_COLUMNS = {
    "category": "category_name_vi",
    "color": "color",
    "shape": "shape",
    "material": "material",
    "style": "style",
    "price_segment": "price_segment",
}


def prepare_market_products(
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Chuan hoa va gop thong tin quoc gia, danh muc cho bang market_products."""
    if products_df.empty:
        return pd.DataFrame()

    df = products_df.copy()
    if "price_segment" not in df.columns or df["price_segment"].isna().any():
        df["price_segment"] = df["price_usd"].astype(float).apply(classify_price_segment)

    df = df.merge(
        countries_df[["country_id", "country_code", "country_name"]],
        left_on="target_country_id",
        right_on="country_id",
        how="left",
    ).merge(
        categories_df[["category_id", "category_code", "category_name_vi", "category_name_en"]],
        on="category_id",
        how="left",
    )
    return df


def analyze_attribute_preferences(
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Thong ke tan suat, ty trong (%), gia ban TB va diem sao theo 5 nhom thuoc tinh & phan khuc gia."""
    df = prepare_market_products(products_df, countries_df, categories_df)
    if df.empty:
        return pd.DataFrame()

    records: list[pd.DataFrame] = []
    for attr_group, col_name in ATTRIBUTE_COLUMNS.items():
        clean = df[df[col_name].notna()].copy()
        if clean.empty:
            continue

        grouped = (
            clean.groupby(["country_code", "country_name", col_name], as_index=False)
            .agg(
                product_count=("market_product_id", "count"),
                avg_market_price_usd=("price_usd", "mean"),
                avg_rating_score=("avg_rating", "mean"),
                total_reviews=("review_count", "sum"),
            )
            .rename(columns={col_name: "attribute_value"})
        )
        country_totals = grouped.groupby("country_code")["product_count"].transform("sum")
        grouped["attribute_share_pct"] = np.where(
            country_totals > 0, (grouped["product_count"] / country_totals) * 100.0, 0.0
        ).round(2)
        grouped["attribute_group"] = attr_group
        grouped["avg_market_price_usd"] = grouped["avg_market_price_usd"].round(2)
        grouped["avg_rating_score"] = grouped["avg_rating_score"].round(2)
        records.append(grouped)

    if not records:
        return pd.DataFrame()

    result = pd.concat(records, ignore_index=True)
    result = result.sort_values(
        ["country_code", "attribute_group", "attribute_share_pct", "avg_rating_score"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)
    return result[
        [
            "country_code",
            "country_name",
            "attribute_group",
            "attribute_value",
            "product_count",
            "attribute_share_pct",
            "avg_market_price_usd",
            "avg_rating_score",
            "total_reviews",
        ]
    ]


def analyze_functional_features(
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Thong ke ty le yeu cau cong nang (an toan may rua bat, chiu nhiet/lo vi song) theo thi truong."""
    df = prepare_market_products(products_df, countries_df, categories_df)
    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby(["country_code", "country_name", "category_code", "category_name_vi"], as_index=False)
        .agg(
            product_count=("market_product_id", "count"),
            dishwasher_safe_pct=("is_dishwasher_safe", lambda s: round(float(s.astype(bool).mean()) * 100.0, 2)),
            heat_resistant_pct=("is_microwave_safe", lambda s: round(float(s.astype(bool).mean()) * 100.0, 2)),
            avg_market_price_usd=("price_usd", "mean"),
            avg_rating_score=("avg_rating", "mean"),
        )
        .sort_values(["country_code", "product_count"], ascending=[True, False])
        .reset_index(drop=True)
    )
    summary["avg_market_price_usd"] = summary["avg_market_price_usd"].round(2)
    summary["avg_rating_score"] = summary["avg_rating_score"].round(2)
    return summary


def analyze_price_distribution(
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Phan tich phan bo gia ban quoc te (Min, Q1, Median, Mean, Q3, Max) theo quoc gia & dong san pham."""
    df = prepare_market_products(products_df, countries_df, categories_df)
    if df.empty:
        return pd.DataFrame()

    stats = (
        df.groupby(["country_code", "country_name", "category_code", "category_name_vi"], as_index=False)
        .agg(
            product_count=("market_product_id", "count"),
            min_price_usd=("price_usd", "min"),
            p25_price_usd=("price_usd", lambda s: float(np.percentile(s, 25))),
            median_price_usd=("price_usd", "median"),
            mean_price_usd=("price_usd", "mean"),
            p75_price_usd=("price_usd", lambda s: float(np.percentile(s, 75))),
            max_price_usd=("price_usd", "max"),
        )
        .sort_values(["country_code", "mean_price_usd"], ascending=[True, False])
        .reset_index(drop=True)
    )
    for col in (
        "min_price_usd",
        "p25_price_usd",
        "median_price_usd",
        "mean_price_usd",
        "p75_price_usd",
        "max_price_usd",
    ):
        stats[col] = stats[col].round(2)
    return stats


def build_country_taste_profiles(
    products_df: pd.DataFrame,
    countries_df: pd.DataFrame,
    categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """Tong hop ho so thi hieu dac trung cua tung quoc gia (Top dong SP, mau sac, hinh dang, chat lieu, phong cach, tam gia)."""
    df = prepare_market_products(products_df, countries_df, categories_df)
    if df.empty:
        return pd.DataFrame()

    attr_df = analyze_attribute_preferences(products_df, countries_df, categories_df)
    profiles = []

    for (code, name), grp in df.groupby(["country_code", "country_name"]):
        c_attrs = attr_df[attr_df["country_code"] == code]

        def _top_values(group_name: str, k: int = 1) -> str:
            sub = c_attrs[c_attrs["attribute_group"] == group_name].head(k)
            if sub.empty:
                return "N/A"
            return ", ".join(
                f"{r.attribute_value} ({r.attribute_share_pct:.1f}%)" for r in sub.itertuples(index=False)
            )

        profiles.append(
            {
                "country_code": code,
                "country_name": name,
                "sample_products": int(len(grp)),
                "top_category": _top_values("category", 1),
                "top_colors": _top_values("color", 2),
                "top_shape": _top_values("shape", 1),
                "top_material": _top_values("material", 1),
                "top_style": _top_values("style", 1),
                "dominant_price_segment": _top_values("price_segment", 1),
                "avg_market_price_usd": round(float(grp["price_usd"].mean()), 2),
                "dishwasher_safe_pct": round(float(grp["is_dishwasher_safe"].astype(bool).mean()) * 100.0, 2),
                "heat_resistant_pct": round(float(grp["is_microwave_safe"].astype(bool).mean()) * 100.0, 2),
                "avg_rating_score": round(float(grp["avg_rating"].mean()), 2),
            }
        )

    return pd.DataFrame(profiles).sort_values("sample_products", ascending=False).reset_index(drop=True)
