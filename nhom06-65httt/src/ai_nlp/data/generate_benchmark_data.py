"""Tao bo du lieu benchmark chuan schema ERD phuc vu huan luyen va kiem thu doc lap phan he AI/NLP.

Luu y: Day la bo du lieu mau/benchmark mo phong dung cau truc 13 bang OLTP
(src/database/01_init_oltp_erd_schema.sql) de kiem thu mo hinh AI/NLP va
pipeline phan tich thi truong khi chua ket noi du lieu ETL thuc te trong PostgreSQL.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import SAMPLE_DATA_DIR, classify_price_segment


COUNTRIES_BASE = [
    ("USA", "United States", "North America", "USD", True),
    ("JPN", "Japan", "East Asia", "JPY", True),
    ("DEU", "Germany", "Europe", "EUR", True),
    ("FRA", "France", "Europe", "EUR", True),
    ("GBR", "United Kingdom", "Europe", "GBP", True),
    ("AUS", "Australia", "Oceania", "AUD", True),
    ("CAN", "Canada", "North America", "CAD", True),
    ("KOR", "South Korea", "East Asia", "KRW", True),
    ("CHN", "China", "East Asia", "CNY", True),
    ("IND", "India", "South Asia", "INR", True),
    ("NLD", "Netherlands", "Europe", "EUR", False),
    ("ITA", "Italy", "Europe", "EUR", False),
    ("ESP", "Spain", "Europe", "EUR", False),
    ("BEL", "Belgium", "Europe", "EUR", False),
    ("CHE", "Switzerland", "Europe", "CHF", False),
    ("SWE", "Sweden", "Europe", "SEK", False),
    ("NOR", "Norway", "Europe", "NOK", False),
    ("DNK", "Denmark", "Europe", "DKK", False),
    ("POL", "Poland", "Europe", "PLN", False),
    ("AUT", "Austria", "Europe", "EUR", False),
    ("SGP", "Singapore", "Southeast Asia", "SGD", False),
    ("THA", "Thailand", "Southeast Asia", "THB", False),
    ("MYS", "Malaysia", "Southeast Asia", "MYR", False),
    ("IDN", "Indonesia", "Southeast Asia", "IDR", False),
    ("PHL", "Philippines", "Southeast Asia", "PHP", False),
    ("ARE", "United Arab Emirates", "Middle East", "AED", False),
    ("SAU", "Saudi Arabia", "Middle East", "SAR", False),
    ("BRA", "Brazil", "South America", "BRL", False),
    ("MEX", "Mexico", "North America", "MXN", False),
    ("NZL", "New Zealand", "Oceania", "NZD", False),
]

US_51_REGIONS = [
    ("US-AL", "Alabama"), ("US-AK", "Alaska"), ("US-AZ", "Arizona"), ("US-AR", "Arkansas"),
    ("US-CA", "California"), ("US-CO", "Colorado"), ("US-CT", "Connecticut"), ("US-DE", "Delaware"),
    ("US-DC", "District of Columbia"), ("US-FL", "Florida"), ("US-GA", "Georgia"), ("US-HI", "Hawaii"),
    ("US-ID", "Idaho"), ("US-IL", "Illinois"), ("US-IN", "Indiana"), ("US-IA", "Iowa"),
    ("US-KS", "Kansas"), ("US-KY", "Kentucky"), ("US-LA", "Louisiana"), ("US-ME", "Maine"),
    ("US-MD", "Maryland"), ("US-MA", "Massachusetts"), ("US-MI", "Michigan"), ("US-MN", "Minnesota"),
    ("US-MS", "Mississippi"), ("US-MO", "Missouri"), ("US-MT", "Montana"), ("US-NE", "Nebraska"),
    ("US-NV", "Nevada"), ("US-NH", "New Hampshire"), ("US-NJ", "New Jersey"), ("US-NM", "New Mexico"),
    ("US-NY", "New York"), ("US-NC", "North Carolina"), ("US-ND", "North Dakota"), ("US-OH", "Ohio"),
    ("US-OK", "Oklahoma"), ("US-OR", "Oregon"), ("US-PA", "Pennsylvania"), ("US-RI", "Rhode Island"),
    ("US-SC", "South Carolina"), ("US-SD", "South Dakota"), ("US-TN", "Tennessee"), ("US-TX", "Texas"),
    ("US-UT", "Utah"), ("US-VT", "Vermont"), ("US-VA", "Virginia"), ("US-WA", "Washington"),
    ("US-WV", "West Virginia"), ("US-WI", "Wisconsin"), ("US-WY", "Wyoming"),
]

ASPECT_SENTENCE_BANK = {
    "Glaze Durability": {
        "Positive": [
            "The ceramic glaze is super smooth and scratch-resistant after daily use.",
            "Thick glossy glaze finish with zero crazing or chipping.",
            "Glaze quality feels durable and holds up wonderfully without knife marks.",
            "Rich celadon glaze looks heirloom-grade and shows no hairline cracks.",
            "Very sturdy enamel coating, not a single chip after months of washing.",
        ],
        "Negative": [
            "The glaze chipped along the rim after only two weeks of gentle use.",
            "Noticeable crazing and dark cutlery scratches appeared on the glaze quickly.",
            "Uneven glaze finish with tiny pinholes and rough spots on the bottom.",
            "Glaze started flaking off near the handle after a few washes.",
            "Surface glaze feels thin and scratches way too easily.",
        ],
        "Neutral": [
            "The glaze finish is decent for the price though slightly matte in spots.",
            "Glaze is acceptable, neither exceptional nor flawed.",
        ],
    },
    "Packaging": {
        "Positive": [
            "Double-boxed with thick molded foam, every piece arrived completely intact.",
            "Packaging was impressive and well-cushioned so nothing broke in transit.",
            "Individually wrapped in bubble sleeves inside a sturdy shipping box.",
            "Super secure protective packaging, zero breakage even after long shipping.",
        ],
        "Negative": [
            "Arrived with a broken handle because the outer box had almost no padding.",
            "Terrible packaging, two plates shattered during delivery due to thin cardboard.",
            "Zero foam dividers inside so the teapot lid cracked in transit.",
            "Poorly packed box resulted in a chipped spout upon arrival.",
            "Fragile ceramic shipped in a flimsy mailer and arrived broken in pieces.",
        ],
        "Neutral": [
            "Packaging was basic cardboard with paper wrap but arrived undamaged.",
            "Standard shipping box, could use slightly better corner protection.",
        ],
    },
    "Design & Color": {
        "Positive": [
            "Gorgeous minimalist aesthetic and the natural speckled white color looks stunning.",
            "Love the vibrant cobalt blue pattern and clean modern silhouette.",
            "Elegant organic shape and warm earthy brown tones elevate my dining table.",
            "Craftsmanship and hand-painted floral motif look truly artisanal.",
            "Timeless round form and balanced proportions fit our kitchen decor nicely.",
        ],
        "Negative": [
            "The color looked dull and muddy compared to the bright photos online.",
            "Awkwardly shaped handle and uneven rim make the mug feel clumsy.",
            "Design looks mass-produced and the pattern print is blurry.",
            "Size is smaller than expected and the asymmetrical shape wobbles slightly.",
        ],
        "Neutral": [
            "Simple classic design and neutral color, looks just like the listing.",
            "Traditional styling is okay, fairly standard shape and tone.",
        ],
    },
    "Heat/Dishwasher": {
        "Positive": [
            "Truly dishwasher safe and stays cool enough to handle out of the microwave.",
            "Retains tea heat well and goes straight into the dishwasher without fading.",
            "Microwave safe and oven-ready stoneware that handles hot soup effortlessly.",
            "No warping or cracking after repeated high-heat dishwasher cycles.",
        ],
        "Negative": [
            "Got burning hot in the microwave even though the listing claimed heat safe.",
            "Not actually dishwasher safe, the gold trim faded after three cycles.",
            "Cracked right down the middle when I poured boiling water for tea.",
            "Handle overheats in the microwave and makes it hard to lift safely.",
        ],
        "Neutral": [
            "Holds heat moderately well; I prefer hand-washing just to be safe.",
            "Works fine in the dishwasher on the top rack.",
        ],
    },
    "Price/Value": {
        "Positive": [
            "Great value for money, feels much more expensive than what I paid.",
            "Reasonably priced handmade set that punches well above its price tag.",
            "Worth every penny for an authentic ceramic tableware collection.",
        ],
        "Negative": [
            "Overpriced for the thin ceramic quality you actually receive.",
            "Too expensive considering the minor flaws and basic finish.",
            "Not worth the premium price tag given the mediocre craftsmanship.",
        ],
        "Neutral": [
            "Fair price for an everyday ceramic set.",
            "Priced about right for mid-range imported tableware.",
        ],
    },
}


def build_countries_df() -> pd.DataFrame:
    """Tao 135 quoc gia (30 quoc gia chinh + 105 quoc gia bo sung theo chuan UN Comtrade)."""
    rows = []
    for idx, (code, name, cont, curr, is_key) in enumerate(COUNTRIES_BASE, start=1):
        rows.append(
            {
                "country_id": idx,
                "country_code": code,
                "country_name": name,
                "region_continent": cont,
                "currency_code": curr,
                "is_key_market": is_key,
            }
        )
    continents = ["Europe", "Asia", "Africa", "South America", "Oceania", "North America"]
    for i in range(len(COUNTRIES_BASE) + 1, 136):
        rows.append(
            {
                "country_id": i,
                "country_code": f"C{i:02d}",
                "country_name": f"Partner Market {i:03d}",
                "region_continent": continents[i % len(continents)],
                "currency_code": "USD",
                "is_key_market": False,
            }
        )
    return pd.DataFrame(rows)


def build_regions_df() -> pd.DataFrame:
    """Tao 51 bang/vung Hoa Ky + cac vung dai dien cho thi truong trong diem."""
    rows = []
    rid = 1
    for code, name in US_51_REGIONS:
        rows.append({"region_id": rid, "country_id": 1, "region_code": code, "region_name": name})
        rid += 1
    extra = [
        (2, "JP-13", "Tokyo"), (2, "JP-27", "Osaka"), (2, "JP-26", "Kyoto"),
        (3, "DE-BY", "Bavaria"), (3, "DE-BE", "Berlin"), (4, "FR-IDF", "Ile-de-France"),
    ]
    for cid, code, name in extra:
        rows.append({"region_id": rid, "country_id": cid, "region_code": code, "region_name": name})
        rid += 1
    return pd.DataFrame(rows)


def build_categories_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category_id": 1, "category_code": "TEA_SET", "category_name_vi": "Bộ ấm chén", "category_name_en": "Ceramic Tea Set", "hs_code_mapping": "6911"},
            {"category_id": 2, "category_code": "MUG_CUP", "category_name_vi": "Ly cốc sứ", "category_name_en": "Ceramic Mug & Cup", "hs_code_mapping": "6911"},
            {"category_id": 3, "category_code": "DINNERWARE", "category_name_vi": "Bát đĩa bàn ăn", "category_name_en": "Dinnerware Set", "hs_code_mapping": "6912"},
            {"category_id": 4, "category_code": "VASE_DECOR", "category_name_vi": "Lọ hoa mỹ nghệ", "category_name_en": "Decorative Vase", "hs_code_mapping": "6913"},
        ]
    )


def build_trade_statistics_df(countries_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Sinh du lieu giao thuong 2021-2023 cho 135 quoc gia voi 14 chi tieu UN Comtrade."""
    key_scales = {
        "USA": (420_000_000, 0.14),
        "JPN": (185_000_000, 0.09),
        "DEU": (165_000_000, 0.11),
        "FRA": (118_000_000, 0.08),
        "GBR": (130_000_000, 0.07),
        "AUS": (76_000_000, 0.12),
        "CAN": (84_000_000, 0.10),
        "KOR": (95_000_000, 0.13),
        "CHN": (210_000_000, 0.04),
        "IND": (68_000_000, 0.16),
    }
    hs_list = [
        ("6911", "Porcelain or china tableware and kitchenware"),
        ("6912", "Ceramic tableware, kitchenware other than porcelain"),
        ("6913", "Statuettes and other ornamental ceramic articles"),
    ]
    rows = []
    tid = 1
    for c in countries_df.itertuples(index=False):
        base_val, growth_bias = key_scales.get(
            c.country_code, (float(rng.uniform(1_500_000, 32_000_000)), float(rng.uniform(-0.04, 0.15)))
        )
        for hs_code, cmd_desc in hs_list:
            hs_weight = {"6911": 0.45, "6912": 0.35, "6913": 0.20}[hs_code]
            prev_val = None
            for year in (2021, 2022, 2023):
                yearly_factor = 1.0 if year == 2021 else (1.0 + growth_bias + float(rng.normal(0, 0.02)))
                val = max(100_000.0, (prev_val or base_val * hs_weight) * yearly_factor)
                fob = round(val * 0.94, 2)
                cif = round(val, 2)
                weight = round(val / float(rng.uniform(3.4, 5.2)), 2)
                yoy = None if prev_val is None else round(((val - prev_val) / prev_val) * 100.0, 2)
                rows.append(
                    {
                        "trade_id": tid,
                        "reporter_country_id": 1,
                        "partner_country_id": c.country_id,
                        "year": year,
                        "trade_flow": "Import",
                        "hs_code": hs_code,
                        "cmd_desc": cmd_desc,
                        "trade_value_usd": round(val, 2),
                        "fob_value_usd": fob,
                        "cif_value_usd": cif,
                        "net_weight_kg": weight,
                        "qty_unit": "kg",
                        "qty_amount": weight,
                        "market_share_pct": 0.0,
                        "yoy_growth_rate": yoy,
                        "data_source": "UN Comtrade" if tid % 2 == 1 else "ITC Trade Map",
                    }
                )
                prev_val = val
                tid += 1
    df = pd.DataFrame(rows)
    year_totals = df.groupby("year")["trade_value_usd"].transform("sum")
    df["market_share_pct"] = ((df["trade_value_usd"] / year_totals) * 100.0).round(2)
    return df


def build_search_trends_df(regions_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Sinh chuoi 52 tuan Google Trends cho 4 nhom san pham & 51 bang Hoa Ky."""
    rows = []
    tid = 1
    start = date(2023, 1, 2)
    cat_terms = {
        1: ("ceramic tea set", 58),
        2: ("handmade ceramic mug", 74),
        3: ("minimalist stoneware dinnerware", 68),
        4: ("artisan ceramic vase", 64),
    }
    country_mult = {1: 1.05, 2: 0.95, 3: 0.92, 4: 0.88, 5: 0.90}
    for cid, mult in country_mult.items():
        for cat_id, (term, base) in cat_terms.items():
            for w in range(1, 53):
                wk_date = start + timedelta(weeks=w - 1)
                seasonal = 14 * np.sin((w - 38) / 52.0 * 2 * np.pi) + (12 if w >= 44 else 0)
                score = int(np.clip(round(base * mult + seasonal + rng.normal(0, 4)), 5, 100))
                rows.append(
                    {
                        "trend_id": tid,
                        "country_id": cid,
                        "region_id": None,
                        "category_id": cat_id,
                        "search_term": term,
                        "week_start_date": wk_date.isoformat(),
                        "week_number": w,
                        "interest_score": score,
                    }
                )
                tid += 1

    # Phan bo 51 bang/vung Hoa Ky trong giai doan cao diem Q4
    us_regions = regions_df[regions_df["country_id"] == 1]
    high_states = {"US-CA", "US-NY", "US-TX", "US-WA", "US-FL", "US-MA", "US-OR", "US-CO"}
    for reg in us_regions.itertuples(index=False):
        for cat_id, (term, base) in cat_terms.items():
            state_boost = 15 if reg.region_code in high_states else 0
            score = int(np.clip(round(base + state_boost + rng.normal(0, 7)), 15, 100))
            rows.append(
                {
                    "trend_id": tid,
                    "country_id": 1,
                    "region_id": reg.region_id,
                    "category_id": cat_id,
                    "search_term": term,
                    "week_start_date": "2023-11-20",
                    "week_number": 47,
                    "interest_score": score,
                }
            )
            tid += 1
    return pd.DataFrame(rows)


def build_trending_keywords_df() -> pd.DataFrame:
    """Sinh danh muc tu khoa but pha tu +140% den +5300%."""
    data = [
        (1, 4, "wabi sabi ceramic vase", "style", 5300.0, "Breakout"),
        (1, 3, "speckled stoneware dinnerware", "material", 1850.0, "Breakout"),
        (1, 2, "dishwasher safe ceramic mug", "feature", 640.0, "Rising"),
        (1, 4, "matte white organic vase", "color", 420.0, "Rising"),
        (2, 1, "minimalist natural clay tea set", "style", 2400.0, "Breakout"),
        (2, 3, "japanese earth tone ceramic bowl", "color", 980.0, "Breakout"),
        (2, 1, "handcrafted celadon teapot", "material", 350.0, "Rising"),
        (3, 3, "functional round porcelain dinner set", "shape", 520.0, "Rising"),
        (3, 2, "heat resistant porcelain coffee cup", "feature", 310.0, "Rising"),
        (4, 4, "artisan terracotta table vase", "material", 760.0, "Rising"),
        (4, 1, "cobalt blue ceramic tea service", "color", 210.0, "Rising"),
        (5, 2, "handmade rustic stoneware mug", "style", 145.0, "Rising"),
    ]
    return pd.DataFrame(
        [
            {
                "keyword_id": idx,
                "country_id": cid,
                "category_id": cat,
                "keyword_text": kw,
                "related_attribute_type": attr,
                "growth_pct": growth,
                "trend_classification": cls,
                "recorded_period": "Last 12 Months",
            }
            for idx, (cid, cat, kw, attr, growth, cls) in enumerate(data, start=1)
        ]
    )


def build_market_products_df(rng: np.random.Generator) -> pd.DataFrame:
    """Sinh 240 san pham quoc te tren Etsy/Amazon mang dac trung thi hieu tung thi truong."""
    market_profiles = {
        1: {  # USA: Da sac/Trang, Hien dai/Thu cong, Do trang tri & Gia dung, an toan may rua bat
            "cats": [3, 4, 2, 1],
            "colors": ["Multicolor", "White", "Natural Beige", "Cobalt Blue"],
            "shapes": ["Round", "Organic Artistic", "Oval", "Square"],
            "materials": ["Stoneware", "Porcelain", "Earthenware"],
            "styles": ["Modern", "Handmade Rustic", "Minimalist", "Traditional"],
            "price_range": (24, 95),
            "dw_prob": 0.85,
        },
        2: {  # Japan: Toi gian, Mau tu nhien, Bo am chen & Bat dia
            "cats": [1, 3, 2, 4],
            "colors": ["Natural Beige", "White", "Brown", "Celadon Green"],
            "shapes": ["Round", "Organic Artistic", "Oval"],
            "materials": ["Stoneware", "Porcelain", "Crackle Glaze"],
            "styles": ["Minimalist", "Handmade Rustic", "Traditional"],
            "price_range": (28, 110),
            "dw_prob": 0.65,
        },
        3: {  # Germany: Thiet ke don gian, Tinh ung dung cao, Do gia dung
            "cats": [3, 2, 4, 1],
            "colors": ["White", "Natural Beige", "Cobalt Blue", "Gray"],
            "shapes": ["Round", "Square", "Oval"],
            "materials": ["Porcelain", "Stoneware"],
            "styles": ["Minimalist", "Modern"],
            "price_range": (22, 85),
            "dw_prob": 0.92,
        },
        4: {  # France: Thu cong nghe thuat, Lo hoa & Am chen
            "cats": [4, 1, 3, 2],
            "colors": ["White", "Cobalt Blue", "Natural Beige", "Multicolor"],
            "shapes": ["Organic Artistic", "Oval", "Round"],
            "materials": ["Porcelain", "Earthenware", "Crackle Glaze"],
            "styles": ["Handmade Rustic", "Traditional", "Modern"],
            "price_range": (30, 120),
            "dw_prob": 0.72,
        },
        5: {  # UK
            "cats": [2, 1, 3, 4],
            "colors": ["Cobalt Blue", "White", "Natural Beige"],
            "shapes": ["Round", "Oval"],
            "materials": ["Porcelain", "Stoneware"],
            "styles": ["Traditional", "Minimalist", "Modern"],
            "price_range": (18, 78),
            "dw_prob": 0.80,
        },
    }
    cat_names = {1: "Tea Set", 2: "Ceramic Mug", 3: "Dinnerware Set", 4: "Decorative Vase"}
    rows = []
    pid = 1
    for cid, prof in market_profiles.items():
        for i in range(48):
            cat_id = prof["cats"][i % len(prof["cats"])]
            color = prof["colors"][int(rng.integers(0, len(prof["colors"])))]
            shape = prof["shapes"][int(rng.integers(0, len(prof["shapes"])))]
            material = prof["materials"][int(rng.integers(0, len(prof["materials"])))]
            style = prof["styles"][int(rng.integers(0, len(prof["styles"])))]
            price = round(float(rng.uniform(*prof["price_range"])), 2)
            platform = "Etsy" if (style in ("Handmade Rustic", "Traditional") or i % 2 == 0) else "Amazon"
            dw_safe = bool(rng.random() < prof["dw_prob"])
            mw_safe = bool(rng.random() < 0.82)
            rows.append(
                {
                    "market_product_id": pid,
                    "external_sku": f"{platform[:3].upper()}-{cid}-{pid:04d}",
                    "platform_source": platform,
                    "target_country_id": cid,
                    "category_id": cat_id,
                    "product_name": f"{style} {color} {material} {cat_names[cat_id]} #{pid}",
                    "price_usd": price,
                    "price_segment": classify_price_segment(price),
                    "color": color,
                    "shape": shape,
                    "material": material,
                    "style": style,
                    "is_dishwasher_safe": dw_safe,
                    "is_microwave_safe": mw_safe,
                    "avg_rating": round(float(rng.uniform(3.4, 4.95)), 2),
                    "review_count": int(rng.integers(15, 260)),
                    "image_url": f"https://example.com/images/{pid}.jpg",
                    "product_url": f"https://example.com/products/{pid}",
                }
            )
            pid += 1
    return pd.DataFrame(rows)


def build_reviews_df(products_df: pd.DataFrame, py_rng: random.Random) -> pd.DataFrame:
    """Sinh 600 danh gia khach hang da dang voi nhan chuan sentiment & aspects de train/test AI/NLP."""
    rows = []
    rid = 1
    base_date = date(2023, 1, 10)
    aspects = list(ASPECT_SENTENCE_BANK.keys())

    for idx in range(600):
        prod = products_df.iloc[idx % len(products_df)]
        # Phan bo: 55% Positive, 20% Neutral, 25% Negative
        bucket = idx % 20
        if bucket < 11:
            sentiment = "Positive"
            stars = py_rng.choice([4, 5, 5])
            chosen_aspects = py_rng.sample(aspects, k=py_rng.choice([1, 2]))
            aspect_pairs = []
            parts = []
            for asp in chosen_aspects:
                sent_a = "Positive"
                parts.append(py_rng.choice(ASPECT_SENTENCE_BANK[asp][sent_a]))
                aspect_pairs.append(f"{asp}:{sent_a}")
            title = py_rng.choice([
                "Gorgeous ceramic quality!",
                "Love the glaze and safe packaging",
                "Exceeded expectations for daily use",
                "Beautiful craftsmanship and value",
            ])
        elif bucket < 15:
            sentiment = "Neutral"
            stars = 3
            asp1, asp2 = py_rng.sample(aspects, k=2)
            # Mix positive + negative or neutral phrasing
            if idx % 2 == 0:
                s1 = py_rng.choice(ASPECT_SENTENCE_BANK[asp1]["Positive"])
                s2 = py_rng.choice(ASPECT_SENTENCE_BANK[asp2]["Negative"])
                parts = [s1, "However,", s2[0].lower() + s2[1:]]
                aspect_pairs = [f"{asp1}:Positive", f"{asp2}:Negative"]
            else:
                parts = [py_rng.choice(ASPECT_SENTENCE_BANK[asp1]["Neutral"])]
                aspect_pairs = [f"{asp1}:Neutral"]
            title = py_rng.choice([
                "Nice design but mixed experience",
                "Okay overall, some pros and cons",
                "Decent ceramic piece for the price",
            ])
        else:
            sentiment = "Negative"
            stars = py_rng.choice([1, 2, 2])
            chosen_aspects = py_rng.sample(aspects, k=py_rng.choice([1, 2]))
            aspect_pairs = []
            parts = []
            for asp in chosen_aspects:
                sent_a = "Negative"
                parts.append(py_rng.choice(ASPECT_SENTENCE_BANK[asp][sent_a]))
                aspect_pairs.append(f"{asp}:{sent_a}")
            title = py_rng.choice([
                "Arrived damaged due to poor packaging",
                "Disappointed with glaze durability",
                "Not dishwasher safe as advertised",
                "Cracked quickly, would not recommend",
            ])

        review_date = (base_date + timedelta(days=(idx * 3) % 350)).isoformat()
        rows.append(
            {
                "review_id": rid,
                "market_product_id": int(prod["market_product_id"]),
                "customer_id": (rid % 180) + 1,
                "rating_stars": int(stars),
                "review_title": title,
                "review_text": " ".join(parts),
                "review_date": review_date,
                "sentiment_label": None,
                "sentiment_score": None,
                "true_sentiment": sentiment,
                "true_aspects": ";".join(aspect_pairs),
            }
        )
        rid += 1
    return pd.DataFrame(rows)


def generate_all_sample_files(output_dir: Path | None = None, seed: int = 42) -> dict[str, Path]:
    """Sinh toan bo 8 file CSV benchmark theo dung schema ERD."""
    target_dir = output_dir or SAMPLE_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)

    countries_df = build_countries_df()
    regions_df = build_regions_df()
    categories_df = build_categories_df()
    trade_df = build_trade_statistics_df(countries_df, rng)
    trends_df = build_search_trends_df(regions_df, rng)
    keywords_df = build_trending_keywords_df()
    products_df = build_market_products_df(rng)
    reviews_df = build_reviews_df(products_df, py_rng)

    outputs = {
        "countries.csv": countries_df,
        "market_regions.csv": regions_df,
        "product_categories.csv": categories_df,
        "trade_statistics.csv": trade_df,
        "search_trends.csv": trends_df,
        "trending_keywords.csv": keywords_df,
        "market_products.csv": products_df,
        "product_reviews_labeled.csv": reviews_df,
    }
    written: dict[str, Path] = {}
    for filename, df in outputs.items():
        path = target_dir / filename
        df.to_csv(path, index=False, encoding="utf-8")
        written[filename] = path
    return written


if __name__ == "__main__":
    files = generate_all_sample_files()
    for name, path in files.items():
        print(f"Generated {name} -> {path}")
