"""Cau hinh trung tam cho phan he Phan tich thi truong, thi hieu va AI/NLP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DATA_DIR = DATA_DIR / "sample_benchmark"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"

PRODUCT_CATEGORIES = {
    "TEA_SET": {"vi": "Bộ ấm chén", "en": "Ceramic Tea Set", "hs": "6911"},
    "MUG_CUP": {"vi": "Ly cốc sứ", "en": "Ceramic Mug & Cup", "hs": "6911"},
    "DINNERWARE": {"vi": "Bát đĩa bàn ăn", "en": "Dinnerware Set", "hs": "6912"},
    "VASE_DECOR": {"vi": "Lọ hoa mỹ nghệ", "en": "Decorative Vase", "hs": "6913"},
}

SENTIMENT_LABELS = ("Positive", "Neutral", "Negative")

ASPECT_CATEGORIES = (
    "Glaze Durability",
    "Packaging",
    "Design & Color",
    "Heat/Dishwasher",
    "Price/Value",
)

KEY_MARKET_CODES = ("USA", "JPN", "DEU", "FRA", "GBR", "AUS", "CAN", "IND", "CHN", "KOR")

PRICE_SEGMENT_BOUNDS = (
    ("Budget <$20", 0.0, 20.0),
    ("Mid-range $20-$60", 20.0, 60.0),
    ("Premium >$60", 60.0, float("inf")),
)


def _load_dotenv_if_present(env_path: Path) -> None:
    """Doc bien moi truong tu file .env cuc bo neu ton tai ma khong ghi de env he thong."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class DatabaseConfig:
    """Thong so ket noi toi PostgreSQL ceramic_bi_db."""

    host: str
    port: int
    dbname: str
    user: str
    password: str
    schema: str = "public"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "DatabaseConfig":
        """Khoi tao cau hinh ket noi tu bien moi truong hoac file .env."""
        _load_dotenv_if_present(env_file or (BASE_DIR / ".env"))
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "ceramic_bi_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            schema=os.getenv("DB_SCHEMA", "public"),
        )


def classify_price_segment(price_usd: float) -> str:
    """Phan loai muc gia ban quoc te (USD) theo 3 phan khuc chuan BI."""
    for label, low, high in PRICE_SEGMENT_BOUNDS:
        if low <= price_usd < high:
            return label
    return "Premium >$60"


def ensure_directories() -> None:
    """Dam bao cac thu muc luu tru model va ket qua phan tich ton tai."""
    for folder in (DATA_DIR, SAMPLE_DATA_DIR, MODELS_DIR, OUTPUTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
